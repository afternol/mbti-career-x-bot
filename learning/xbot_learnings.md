# MBTIキャリア Xボット 構築・運用 学習記録

作成日：2026-04-13  
対象アカウント：@careerkentaro  
対象サイト：https://career-kentaro.com/mbti/

---

## 1. 全体アーキテクチャ

```
x_bot/
├── config.py          # 全設定・環境変数の一元管理
├── content.py         # Claudeによるコンテンツ生成
├── poster.py          # Xへの投稿・ログ保存
├── retweeter.py       # 自動RT
├── scheduler.py       # APSchedulerによる定時実行
├── character.md       # キャラクター設定（Claudeへのsystemプロンプト素材）
├── posted_log.json    # 投稿済み履歴（重複防止・履歴参照に使用）
├── rt_log.json        # RT済み履歴
├── register_task.ps1  # Windowsタスクスケジューラ登録スクリプト
├── logs/
│   ├── poster.log     # 投稿・スケジューラの全ログ（実質的に統合ログ）
│   └── retweeter.log  # RTログ
└── learning/
    └── xbot_learnings.md  # 本ファイル
```

---

## 2. X API 設定・制約

### 2-1. 使用プラン
- **Free tier**（無料）
- 月間投稿上限：**1,500件**（write）
- 設計：1日3投稿 × 30日 = 90件/月（余裕を持たせた設計）

### 2-2. Free tierで使えないAPI
| API | 状況 |
|---|---|
| `GET /2/tweets/search/recent` | **使用不可**（401 Unauthorized） |
| `POST /2/tweets` | 使用可 |
| `DELETE /2/tweets/:id` | 使用可 |
| `GET /2/users/:id/tweets` | 使用可 |

→ **キーワード検索RTはFree tierで不可**。特定アカウントのタイムラインRTのみ実装。

### 2-3. 認証方式
- **OAuth 1.0a**（User Context）を使用
- Tweepy v4の `tweepy.Client` に以下4つを渡す：
  - `consumer_key` = API Key
  - `consumer_secret` = API Secret
  - `access_token` = Access Token
  - `access_token_secret` = Access Token Secret
- Bearer Token は検索系APIのみに使用（現在は無効化済み）

### 2-4. Developer Portalで必ず確認すること
```
App Settings → User authentication settings → App permissions
→ 「Read and Write」になっているか確認
```
**重要：パーミッションを変更したら Access Token と Secret を必ず再生成すること。**  
変更前に発行されたトークンは古い権限のまま残る。再生成しないと403エラーが出続ける。

### 2-5. 403エラーのパターンと対処

| エラー内容 | 原因 | 対処 |
|---|---|---|
| `403 Your client app is not configured with the appropriate oauth1 app permissions` | App permissionsがRead only | Developer PortalでRead+Writeに変更し、Access Token再生成 |
| `403 You are not permitted to perform this action.` | Xのスパム検知が特定コンテンツに反応 | コンテンツを再生成してリトライ（最大3回） |
| `402 Payment Required` | Claude APIのクレジット残高不足 | Anthropic Consoleでクレジットをチャージ |
| `401 Unauthorized` | Free tierで使用不可のAPI呼び出し | 該当APIの使用を無効化 |

---

## 3. コンテンツ生成の仕組み

### 3-1. 設計思想
- 静的テンプレートは使わない → **Claude API（claude-sonnet-4-6）で毎回動的生成**
- 理由：固定テンプレートでは2週間程度で全パターンが繰り返されてしまう

### 3-2. コンテンツ種別と配分比率

| 種別 | 内容 | 比率 |
|---|---|---|
| `aruaru` | MBTIタイプ別あるある | 35% |
| `tips` | 適職・キャリアTips | 20% |
| `article_intro` | タイプ別記事紹介（URL付き） | 20% |
| `site_lead` | サイト全体への誘導（URL付き） | 15% |
| `quiz` | 診断クイズ形式 | 10% |

### 3-3. キャラクター設定の反映方法

`character.md` を `content.py` 起動時に**丸ごと読み込み**、Claudeへの `system` プロンプトに埋め込む。

```python
_CHAR_MD = (Path(__file__).parent / "character.md").read_text(encoding="utf-8")

CHARACTER_SYSTEM = f"""あなたは「キャリア研たろう」というキャラクターとして...
{_CHAR_MD}
..."""
```

→ character.md を更新するだけで、次回生成から即座にキャラクター設定が反映される。

### 3-4. キャラクター「キャリア研たろう」の核心設定

**コンセプト：温かい分析官**
- 一人称：「ぼく」固定
- 口調：ため口と丁寧語を7:3で混在。軽すぎず堅すぎず
- 投稿の3段構成：①共感 → ②データ・知見 → ③提案
- 必ず入れる視点：「あなたのせいじゃなく環境のせい」
- やらないこと：「頑張ってください」などの精神論、上から目線の断言

### 3-5. 各コンテンツタイプのテーマプール

テーマは固定リストからランダム選択。リストを増やすほど多様性が増す。

- `TIPS_THEMES`：15種（転職ミス、環境ミスマッチ、N/S型の違い、T/F型の違い 等）
- `QUIZ_THEMES`：7種（I/E型の違い、J/P型の違い 等）
- `LEAD_ANGLES`：5種（サイト全体紹介、機能紹介 等）
- `INTRO_ANGLES`：4種（強みの活かし方、消耗しやすい環境 等）

---

## 4. 重複防止の仕組み（2層構造）

### 第1層：MD5ハッシュによる完全一致チェック
```python
# posted_log.json の全エントリからhashを収集
used_hashes = {e["hash"] for e in data if "hash" in e}

# 生成後に照合
h = hashlib.md5(text.strip().encode()).hexdigest()[:12]
if h in used_hashes:
    continue  # 再生成
```

### 第2層：過去履歴をClaudeに渡す（意味的重複の防止）
```python
# 直近30件の投稿テキストをプロンプトに付加
history_ctx = """【過去の投稿履歴（テーマ・フレーズ・導入文の重複を避けること）】
[2026-04-12 article_intro] 【INTJ（戦略家）の適職データ...
[2026-04-13 article_intro] 「ルーティンワークだけど大丈夫？」..."""

full_prompt = f"{prompt}\n\n{history_ctx}"
```

→ 第1層は完全一致のみ防ぐ。第2層はテーマ・フレーズ・導入文の類似を意味的に防ぐ。

---

## 5. X文字数カウントの正確な仕様

Xは独自の**weighted character count**を使用。単純な文字列長ではない。

| 文字種 | カウント |
|---|---|
| 日本語（CJK）文字 | **2カウント** |
| ASCII・英数字 | 1カウント |
| URL（長さ問わず） | **23カウント固定**（t.co短縮後） |
| 絵文字 | 2カウント（多くの場合） |
| 改行 | 1カウント |

**上限：280カウント**  
→ 日本語中心の場合、本文は**110〜120文字程度**が実質的な目安。

実装：
```python
def _x_char_count(text: str) -> int:
    url_re = re.compile(r'https?://\S+')
    text_no_url = url_re.sub('\x00' * 23, text)
    count = 0
    for ch in text_no_url:
        cp = ord(ch)
        if any(s <= cp <= e for s, e in _CJK_RANGES):
            count += 2
        else:
            count += 1
    return count
```

生成後に280超えを検知したら、超過分を明示して**自動で再生成**する。

---

## 6. 投稿スケジューリング

### 6-1. 設計思想
毎日固定時刻に投稿するとBot感が出る → **時間帯ウィンドウ内でランダム**にする。

### 6-2. 時間帯設定
| 枠 | 時間帯 | 理由 |
|---|---|---|
| 朝枠 | 07:00〜10:00 | 通勤・朝の情報収集時間帯 |
| 昼枠 | 11:30〜14:00 | 昼休み |
| 夜枠 | 18:00〜22:30 | 帰宅後・就寝前 |

### 6-3. ランダム化の実装
```python
start_min = slot["start"][0] * 60 + slot["start"][1]
end_min   = slot["end"][0]   * 60 + slot["end"][1]
chosen_min = random.randint(start_min, end_min)
second = random.randint(0, 59)
```
→ 枠内の分・秒レベルまでランダム。翌日のジョブはその日のジョブが完了した後に登録される。

### 6-4. APSchedulerの使い方
```python
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger

scheduler = BlockingScheduler(timezone="Asia/Tokyo")
scheduler.add_job(
    job_func,
    DateTrigger(run_date=run_at),  # 1回限りのトリガー
    id=job_id,
    replace_existing=True,
    misfire_grace_time=600,  # 10分以内なら遅延実行OK
)
scheduler.start()  # ブロッキング（メインスレッドを占有）
```

`DateTrigger` を使い、1回実行のたびに翌日分を再登録する自己再スケジュール方式。

---

## 7. Windowsタスクスケジューラへの登録

### 7-1. 登録方法
```powershell
# 管理者権限のPowerShellで実行
cd C:\Users\after\mbti-career\x_bot
.\register_task.ps1
```

### 7-2. 設定のポイント
```powershell
# pythonw.exe を使う（コンソールウィンドウを表示しない）
$PythonW = "C:\Users\after\AppData\Local\Python\bin\pythonw.exe"

# AtStartup トリガー（PC起動時に自動起動）
$Trigger = New-ScheduledTaskTrigger -AtStartup

# 実行時間制限なし・ネットワーク必須・失敗時3回リトライ
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# RunLevel Highest（管理者権限相当）
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
```

### 7-3. 動作確認コマンド
```powershell
# タスクの状態確認
Get-ScheduledTask -TaskName "MBTICareerXBot" | Get-ScheduledTaskInfo

# プロセス確認
Get-Process -Name pythonw -ErrorAction SilentlyContinue | Select-Object Id, CPU, StartTime

# 結果コード 267009 = 0x41301 = SCHED_S_TASK_RUNNING（実行中）
```

### 7-4. Windowsのエンコーディング問題への対処
```python
# scheduler.py の冒頭に必ず書く
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
```
→ pythonw.exe はコンソールがないため stdout が None になることがある。`hasattr` チェックが必要。

---

## 8. ログの仕組み

### 8-1. なぜすべてposter.logに集まるか
Python の `logging.basicConfig()` は**最初の1回しか効かない**。

`scheduler.py` が `poster.py` をインポートすると、`poster.py` のモジュールレベルコードが先に実行され `basicConfig(poster.log)` が呼ばれる。その後 `scheduler.py` の `basicConfig(scheduler.log)` はno-opになる。

→ 実質的に **poster.log が統合ログ** になる。

### 8-2. ログで分かること・分からないこと
- **分かる**：投稿成功ID・エラー内容・スケジューラ起動時刻
- **分からない**：次回の予定投稿時刻（APSchedulerのメモリ上にのみ存在）

→ 改善余地：スケジューラ起動時に予定時刻をログ出力する。

---

## 9. 自動RT設定

### 9-1. 現状
- Free tierのため**キーワード検索RT（`/2/tweets/search/recent`）は401エラー**で使用不可
- **特定アカウントのタイムラインRT**のみ有効（`/2/users/:id/tweets`）
- 1日上限：3件

### 9-2. RT対象アカウントの追加方法
```python
# config.py
RT_TARGET_ACCOUNTS: list[str] = ["数値のuser_id"]
```
user_idの確認：Developer PortalまたはTwitter ID検索ツールで数値IDを取得する。

---

## 10. 投稿履歴データ（posted_log.json）

```json
[
  {
    "tweet_id": "投稿のID",
    "type": "コンテンツ種別",
    "text": "投稿全文",
    "hash": "MD5ハッシュ12桁",
    "posted_at": "2026-04-13T00:34:11+00:00"
  }
]
```

- 投稿するたびに `poster.py` が自動で追記
- `content.py` が直近30件を読み込み、Claudeへの履歴コンテキストとして渡す
- 重複防止は「ハッシュ完全一致チェック」＋「Claudeへの意味的重複回避指示」の2層

---

## 11. トラブルシューティング早見表

| 症状 | 確認箇所 | 対処 |
|---|---|---|
| 投稿が実行されない | タスクスケジューラの状態 / poster.log | タスクをRestartまたは手動で`python scheduler.py --once`実行 |
| 403 Forbidden（permissions） | Developer Portal → App permissions | Read+Writeに変更し、Access Token再生成 |
| 403 You are not permitted | poster.log | スパム検知。コンテンツ再生成でリトライ（自動対応済み） |
| 402 Payment Required | Anthropic Console | Claude APIクレジットをチャージ |
| 401 Unauthorized（RT） | retweeter.py | Free tierの制限。キーワードRT無効化済み（正常） |
| ログが空 | pythonw.exeのエンコード | PYTHONIOENCODING=utf-8を環境変数に設定済みか確認 |
| 投稿はされたがposted_log未記録 | poster.pyのログ保存部分 | 「投稿成功」ログはあるか確認。なければログ保存でエラー |

---

## 12. 手動操作コマンド集

```bash
# 今すぐ1件投稿（本番）
python x_bot/scheduler.py --once

# 今すぐ1件投稿（テスト・Xには投稿しない）
python x_bot/scheduler.py --once --dry

# コンテンツ生成のみテスト（全種別）
python x_bot/content.py

# 特定種別のコンテンツ生成テスト
python x_bot/content.py aruaru
python x_bot/content.py tips

# スケジューラをフォアグラウンドで起動
python x_bot/scheduler.py

# タスクスケジューラの状態確認（PowerShell）
Get-ScheduledTask -TaskName "MBTICareerXBot" | Get-ScheduledTaskInfo

# タスク再起動（PowerShell）
Restart-ScheduledTask -TaskName "MBTICareerXBot"
```

---

## 14. 2026-04-15 障害対応記録

### 発生した問題
- `scheduler.py` ソースファイルが消失 → ローカルボット完全停止（4/13以降）
- `config.py` に `X_BEARER_TOKEN`, `BOT_ACCOUNT_ID`, `RT_KEYWORDS`, `RT_TARGET_ACCOUNTS`, `RT_DAILY_LIMIT`, `RT_LOG` が未定義 → `retweeter.py` が ImportError

### 修正内容
1. `config.py` に不足変数を追加（`.env` に既に値あり、読み込みコードが欠落していた）
2. `scheduler.py` を再作成（learning doc の設計思想に基づき再実装）

### 再発防止
- `scheduler.py` は重要なコアファイル。削除・移動しない
- `config.py` の変数と `retweeter.py` のimport行は必ず同期を保つ

### ユーザー対応が必要な残タスク
1. X Developer Portal → App Settings → App permissions → **Read and Write** を確認（403 oauth1 エラーの根本原因）
   - 変更後は必ず **Access Token & Secret を再生成** して `.env` を更新
2. 管理者 PowerShell で `.\register_task.ps1` を実行 → Windows タスクスケジューラに再登録

---

## 13. 今後の改善候補

| 優先度 | 内容 |
|---|---|
| 高 | スケジューラ起動時に予定投稿時刻をログ出力 |
| 高 | RT対象アカウントの追加（集客効果のある関連アカウント） |
| 中 | 投稿パフォーマンス（いいね・RT数）の自動取得と記録 |
| 中 | テーマプール（TIPS_THEMES等）の定期的な拡充 |
| 低 | Basic tierへのアップグレードでキーワード検索RTを有効化 |
| 低 | 投稿履歴の可視化ダッシュボード |
