# MBTI Career X Bot

career-kentaro.com/mbti/ の集客用X自動運用ボット

## セットアップ

### 1. 依存パッケージをインストール
```bash
pip install -r requirements.txt
```

### 2. .env を作成
```bash
cp .env.example .env
```
`.env` を編集して各APIキーを設定する。

**X API の取得場所:** https://developer.twitter.com/en/portal/dashboard
- Free tier で OK（1,500ツイート/月）
- 必要な権限: Read and Write

**Anthropic API（将来のAI生成コンテンツ用）:** https://console.anthropic.com/

### 3. BOT_ACCOUNT_ID の確認方法
```python
import tweepy
client = tweepy.Client(bearer_token="your_bearer_token")
user = client.get_user(username="your_twitter_handle")
print(user.data.id)
```

---

## 使い方

### ドライラン（APIを叩かずに確認）
```bash
python poster.py --dry
python poster.py --dry aruaru   # コンテンツ種類を指定
python retweeter.py --dry
python scheduler.py --once --dry
```

### 1回だけ実行
```bash
python scheduler.py --once
```

### 常駐スケジューラ起動（推奨）
```bash
python scheduler.py
```
投稿スケジュール（`config.py` の `TWEET_HOURS` で変更可）:
- 朝8時  → ツイート投稿 + 自動RT（8:05）
- 昼12時 → ツイート投稿
- 夜20時 → ツイート投稿

---

## コンテンツ種類

| 種別 | 重み | 内容 |
|------|------|------|
| `aruaru` | 45% | MBTI全16タイプのあるある |
| `tips` | 25% | 転職・キャリアTips |
| `site_lead` | 15% | career-kentaro.com への誘導 |
| `quiz` | 15% | 診断クイズ形式 |

---

## 自動RT設定（`config.py` を編集）

```python
# キーワード検索RT
RT_KEYWORDS = ["MBTI 転職", "MBTI 適職", ...]

# 特定アカウントをRT（user_idで指定）
RT_TARGET_ACCOUNTS = ["123456789"]

# 1日のRT上限
RT_DAILY_LIMIT = 10
```

---

## Windows タスクスケジューラで自動起動する場合

1. タスクスケジューラを開く
2. 「基本タスクの作成」→ トリガー: PC起動時
3. プログラム: `python.exe` / 引数: `C:\Users\after\mbti-career\x_bot\scheduler.py`
4. 開始場所: `C:\Users\after\mbti-career\x_bot`

---

## ファイル構成

```
x_bot/
├── config.py          # APIキー・スケジュール設定
├── content.py         # ツイートコンテンツ生成
├── poster.py          # ツイート投稿
├── retweeter.py       # 自動RT
├── scheduler.py       # スケジューラ（メインエントリ）
├── .env               # APIキー（gitignore済み）
├── .env.example       # .envのテンプレート
├── requirements.txt   # 依存パッケージ
├── posted_log.json    # 投稿済みログ（自動生成）
├── rt_log.json        # RT済みログ（自動生成）
└── logs/              # ログファイル（自動生成）
```
