"""
MBTIキャリア X Bot — コンテンツ生成モジュール
Claude API（claude-sonnet-4-6）で毎回動的生成。

コンテンツ種別（12種・config.pyのCONTENT_TYPESで重み付け）：
  1. aruaru        - MBTIタイプ別あるある
  2. tips          - 適職・キャリアTips
  3. site_lead     - サイト誘導
  4. article_intro - タイプ別記事紹介（URL付き）
  5. quiz          - 診断クイズ形式
  6. case_story    - 相談事例風（読者から相談を受けた体）
  7. work_env      - 職場環境ミスマッチ論（職種より環境）
  8. cognitive     - 認知機能（Fe/Fi/Te/Ti/Ne/Ni/Se/Si）解説
  9. pair_compare  - 2タイプ比較（似てるけど違う）
 10. reframe       - 弱みを強みに読み替え
 11. micro_voice   - 短文のぼやき・独り言
 12. myth_buster   - MBTIの誤解を解く
"""
import json
import re
import random
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, SITE_URL

# ── 16タイプデータ ────────────────────────────────────────
_TYPES_FILE = Path(__file__).parent / "types_data.json"
TYPES: dict = json.loads(_TYPES_FILE.read_text(encoding="utf-8"))
TYPE_KEYS: list[str] = list(TYPES.keys())

# ── Claudeクライアント ────────────────────────────────────
_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def type_url(mbti_type: str) -> str:
    return f"{SITE_URL}types/{mbti_type.lower()}/"


# ── X文字数カウント（CJK=2, URL=23, その他=1） ─────────────
_CJK_RANGES = [
    (0x1100, 0x115F), (0x2E80, 0x303F), (0x3040, 0x33FF),
    (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xA000, 0xA4CF),
    (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0xFE10, 0xFE1F),
    (0xFE30, 0xFE6F), (0xFF00, 0xFFEF), (0x1B000, 0x1B0FF),
    (0x1F200, 0x1F2FF), (0x20000, 0x2A6DF), (0x2A700, 0x2CEAF),
]

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


# ══════════════════════════════════════════════════════════
# ランダム化部品（全ジェネレータで使い回す）
# ══════════════════════════════════════════════════════════

# トーン（語り口の温度感）
TONES = [
    "やわらかく寄り添う感じ。共感のフレーズを多めに",
    "淡々と事実を述べるが、最後だけ温度を上げる",
    "少しくだけて、友達に話すような口調",
    "データ・分析寄りで、観察結果を共有する感じ",
    "短文を重ねてリズム良く、テンポで読ませる",
    "問いかけから入って、相手に考えさせる",
    "ちょっと自虐や驚きを混ぜて、人間味を出す",
    "結論ファーストでズバッと言い切り、その後で理由を添える",
]

# 構造パターン（投稿全体の流れ）
STRUCTURES = [
    "共感（あるある的な一文）→ 解説 → やわらかい提案",
    "問いかけ → 答え → 短い補足",
    "結論先出し → 根拠 → 一言まとめ",
    "意外な事実 → 説明 → 「だから〜ですよ」と着地",
    "ミニエピソード（先日〜があった等）→ そこから得られた気づき",
    "対比（AとB）→ 違いの理由 → 実用Tips",
    "誤解の指摘 → 正しい捉え方 → 行動提案",
    "観察した傾向 → データ的な裏付け → コメント",
]

# ハッシュタグプール（ジャンル別）
HASHTAG_BASE      = ["#MBTI", "#性格診断", "#適職診断"]
HASHTAG_CAREER    = ["#転職", "#キャリア", "#仕事", "#働き方", "#適職", "#キャリアチェンジ"]
HASHTAG_PERSONAL  = ["#自己分析", "#自己理解", "#内向型", "#外向型"]
HASHTAG_SITUATION = ["#職場", "#上司", "#部下", "#人間関係", "#コミュニケーション"]

def _random_hashtags(extra: list[str] | None = None, n: int = 2) -> str:
    """ハッシュタグを n〜n+1 個ランダム選択（重複なし）"""
    pool = HASHTAG_BASE + HASHTAG_CAREER + HASHTAG_PERSONAL + HASHTAG_SITUATION
    if extra:
        pool = extra + pool
    count = random.randint(n, n + 1)
    chosen: list[str] = []
    for tag in pool:
        if tag in chosen:
            continue
    sample_count = min(count, len(set(pool)))
    chosen = random.sample(list(dict.fromkeys(pool)), sample_count)
    return " ".join(chosen)

# 絵文字の有無（過剰使用を避けるため70%は無し）
def _maybe_emoji_hint() -> str:
    if random.random() < 0.3:
        emoji = random.choice(["🔍", "💬", "📌", "🌱", "🧭"])
        return f"絵文字を1つだけ使う場合は {emoji} を文中に自然に。使わなくてもOK"
    return "絵文字は使わない"

# 共通ルール
COMMON_RULES = """
- X文字数上限：280カウント以内（日本語1文字=2カウント、URL=23カウント固定、改行=1カウント）
  → 日本語だけで書くなら最大130文字が絶対上限。本文は90〜110文字が目安。
- URLは1件まで。ハッシュタグは2〜3個まで。
- 「キャリア研たろうです」などの自己紹介は不要。
- **や*によるMarkdown強調記法は絶対に使わない（Xでは装飾されずAI臭が出る）。
- 改行を使って読みやすくする。1行に詰め込みすぎない。
- 出力はツイート本文のみ。「以下が〜」「ツイート：」などの前置きは一切不要。
"""

# キャラ設定
_CHAR_MD = (Path(__file__).parent / "character.md").read_text(encoding="utf-8")

CHARACTER_SYSTEM = f"""あなたは「キャリア研たろう」というキャラクターとしてXに投稿するツイートを書きます。
以下のキャラクター設定を厳密に守ってください。

{_CHAR_MD}

---

【投稿の追加ルール】{COMMON_RULES}"""


def _flavor_block(tone: str | None = None, structure: str | None = None) -> str:
    """各ジェネレータのpromptに差し込む共通のランダム指示"""
    t = tone or random.choice(TONES)
    s = structure or random.choice(STRUCTURES)
    return (
        f"【今回のトーン】{t}\n"
        f"【今回の構造】{s}\n"
        f"【絵文字】{_maybe_emoji_hint()}\n"
    )


# ── 過去ツイート履歴 ─────────────────────────────────────
def _build_history_context(recent_tweets: list[str]) -> str:
    if not recent_tweets:
        return ""
    lines = ["【過去の投稿履歴（テーマ・フレーズ・導入文の重複を避けること）】"]
    for text in recent_tweets[:30]:
        lines.append(f"- {text[:80].replace(chr(10), ' ')}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# 1. あるあるツイート
# ══════════════════════════════════════════════════════════
ARUARU_INTROS = [
    "「{type}（{nick}）あるある言っていいですか」から始める",
    "「これ、{type}あるあるだと思うんですけど」から始める",
    "「{type}の人、こういうことありませんか」から始める",
    "「{type}（{nick}）の話なんですけど」と前置きから入る",
    "いきなりシーン描写から始め、最後に「これ{type}あるあるです」と種明かしする",
    "「ぼくの観察だと、{type}の人って〜」から始める",
    "「{type}さん、心当たりありませんか」と問いかけから入る",
    "「{nick}タイプの{type}さん、これわかります？」とニックネーム呼びから入る",
    "「先日{type}の方と話してて思ったんですが」と聞いた話風で入る",
    "短い1行のセリフから始め、改行して「〜って{type}だけ？」と続ける",
]
ARUARU_SCENES = [
    "職場での会議・打ち合わせシーン",
    "上司・部下とのやりとり",
    "転職活動・面接の場面",
    "プライベート（休日・買い物・人付き合い）",
    "メール・チャットでのコミュニケーション",
    "新人時代の戸惑い",
    "残業・締切前の追い込み",
    "ランチ・飲み会など雑談の場",
    "在宅・リモートワーク特有のあるある",
    "プレゼン・発表前後の心理",
]

def make_aruaru_tweet(mbti_type: str | None = None) -> str:
    if mbti_type is None:
        mbti_type = random.choice(TYPE_KEYS)
    data   = TYPES[mbti_type]
    nick   = data["nickname"]
    sample = random.choice(data["aruaru"])["text"]
    intro  = random.choice(ARUARU_INTROS).format(type=mbti_type, nick=nick)
    scene  = random.choice(ARUARU_SCENES)
    tags   = _random_hashtags(extra=[f"#{mbti_type}"])

    prompt = f"""{mbti_type}（{nick}）のあるあるツイートを1件作成してください。

【参考データ（サイトの既存内容・そのまま使わないこと）】
タイプの特徴：{data['tagline']}
あるある例：{sample}

【今回の導入方針】{intro}
【今回のシーン】{scene}（このシーンに即した具体的な行動・心理を描写）

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 2. キャリアTipsツイート
# ══════════════════════════════════════════════════════════
TIPS_THEMES = [
    "転職活動でやりがちなミスと、MBTIを使った改善策",
    "「仕事が合わない」と感じる本当の原因（職種より職場環境）",
    "N型とS型で、向いてる職場環境の違い",
    "T型とF型で、消耗しやすい仕事の違い",
    "年収を上げるための転職タイミング",
    "「石の上にも3年」が合わない人のタイプ傾向",
    "転職エージェントの正しい使い方・選び方",
    "30代転職で差がつく「成果の見せ方」",
    "内向型（I型）が活きる職場環境の特徴",
    "外向型（E型）が消耗する職場環境の特徴",
    "MBTIの認知機能と仕事の向き不向きの関係",
    "J型とP型で、向いてる業務スタイルの違い",
    "キャリアチェンジと職場環境チェンジ、どちらを選ぶべきか",
    "自分の市場価値を正しく知る方法",
    "20代・30代・40代、転職成功のポイントの違い",
    "副業を始めるべきタイプ・避けたほうがいいタイプ",
    "リモートワークで成果を出しやすいタイプの特徴",
    "「やりたいこと」より「向いてること」で選ぶ転職",
    "上司ガチャに当たったときの立ち回り方",
    "面接で自分の弱みを話すときのMBTI別アプローチ",
    "「もう辞めたい」と思ったときに一度立ち止まる視点",
    "新卒3年以内の離職を考えるときの判断軸",
    "管理職に向いてるタイプ・向いてないタイプの境界",
    "「成長できる環境」の見極め方（タイプ別）",
    "自己PRで使うべき言葉と避けるべき言葉（タイプ別）",
    "残業が苦にならない人・極端に消耗する人の差",
    "「裁量がある仕事」が向いてるかどうかの判断軸",
    "数字文化の職場が合うタイプ・合わないタイプ",
    "クリエイティブ職に向いてるタイプの誤解",
    "営業職の中でも、向き不向きが分かれる要因",
]

def make_tips_tweet() -> str:
    theme = random.choice(TIPS_THEMES)
    tags  = _random_hashtags()
    prompt = f"""以下のテーマでキャリア・転職のTipsツイートを1件作成してください。

【テーマ】{theme}

【書き方】
- データや具体的な数字・傾向を盛り込む（断定しすぎず「〜という傾向」程度）
- 「ぼくのデータだと〜」「ぼくが見てきた中では〜」など一人称で語る
- 「あなたのせいじゃなく環境のせい」という視点を必要に応じて入れる

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 3. サイト誘導ツイート
# ══════════════════════════════════════════════════════════
LEAD_ANGLES = [
    "サイト全体の紹介（向いてる仕事・向いてない仕事・消耗する職場環境がわかる）",
    "向いてない仕事・消耗する職場環境の診断機能の紹介",
    "認知機能ベースの分析という差別化ポイントの紹介",
    "転職エージェント推薦機能の紹介",
    "MBTIあるあるの流れからサイトへの自然な誘導",
    "「自分のタイプの活かし方がわからない人へ」という入り口",
    "「仕事辞めたい」と思っている人に向けた紹介",
    "新卒・若手向けに、最初のキャリア選びの参考として紹介",
]

def make_site_lead_tweet() -> str:
    angle     = random.choice(LEAD_ANGLES)
    rand_type = random.choice(TYPE_KEYS)
    rand_nick = TYPES[rand_type]["nickname"]
    tags      = _random_hashtags()
    prompt = f"""以下の切り口でcareer-kentaro.comのMBTI適職診断サイトへの誘導ツイートを1件作成してください。

【切り口】{angle}
【サイトURL】{SITE_URL}
【タイプ例（使っても使わなくてもOK）】{rand_type}（{rand_nick}）

【書き方】
- URLを必ず1件含める
- 押しつけがましくなく、自然に「見てみようかな」と思わせる文体
- 宣伝色を出しすぎない。共感→「こういう人はこのサイト見るといいですよ」の流れ

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 4. 記事紹介ツイート
# ══════════════════════════════════════════════════════════
INTRO_ANGLES = [
    "このタイプの強みと、それが活きる仕事の紹介",
    "このタイプが消耗しやすい職場環境の警告",
    "「仕事が合わないかも」と感じやすいパターンの紹介",
    "向いてない仕事ワーストの紹介と理由",
    "このタイプの認知機能から見える適職傾向",
    "意外と向いてる職種の紹介（一般的なイメージとのズレ）",
    "このタイプが転職時に気をつけるべきポイント",
]

def make_article_intro_tweet() -> str:
    mbti_type = random.choice(TYPE_KEYS)
    data      = TYPES[mbti_type]
    nick      = data["nickname"]
    tagline   = data["tagline"]
    angle     = random.choice(INTRO_ANGLES)
    page_url  = type_url(mbti_type)
    tags      = _random_hashtags(extra=[f"#{mbti_type}"])

    prompt = f"""以下のMBTIタイプのページ紹介ツイートを1件作成してください。

【タイプ】{mbti_type}（{nick}）
【タイプの特徴】{tagline}
【紹介の切り口】{angle}
【ページURL】{page_url}

【書き方】
- URLを必ず含める
- {mbti_type}の人に「自分のことだ」と思わせる具体的な内容
- 抽象論ではなく、行動・職場・感情の描写を1つは入れる

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 5. 診断クイズ形式ツイート
# ══════════════════════════════════════════════════════════
QUIZ_THEMES = [
    "仕事でエネルギーが出る場面（I型/E型の違い）",
    "ミスをしたときの思考パターン（T型/F型の違い）",
    "理想の働き方（J型/P型の違い）",
    "得意な業務スタイル（N型/S型の違い）",
    "向いてる上司のタイプ（NT型/NF型/ST型/SF型）",
    "転職を考えるきっかけ（タイプ別の違い）",
    "仕事で一番ストレスを感じる場面（タイプ別）",
    "プレゼン直前にすること（タイプ別）",
    "新しい仕事を覚えるときの順序（タイプ別）",
    "「やる気が出ない」ときの回復方法（タイプ別）",
]
QUIZ_OPENERS = [
    "「ちょっと聞いてもいいですか？」から始める",
    "「これ、自分どっちか考えてみてください」から始める",
    "「気になってる質問があるんですが」から始める",
    "「2択クイズです」とシンプルに切り出す",
]

def make_quiz_tweet() -> str:
    theme  = random.choice(QUIZ_THEMES)
    opener = random.choice(QUIZ_OPENERS)
    tags   = _random_hashtags()
    prompt = f"""以下のテーマでMBTI診断クイズ形式のツイートを1件作成してください。

【テーマ】{theme}
【サイトURL】{SITE_URL}
【今回の切り出し方】{opener}

【書き方】
- A/Bの2択を提示する
- 結果（どのタイプ傾向か）を簡潔に解説する
- URLを末尾に含める

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 6. 相談事例風（case_story）
# ══════════════════════════════════════════════════════════
CASE_OPENERS = [
    "「先日、こんな相談を受けました」から始める",
    "「最近多い相談なんですが」から始める",
    "「これ、よくある相談です」と切り出す",
    "「30代の方からこんな話を聞いて」と具体的な属性を出す",
    "「20代の◯◯さんからの相談」みたいな匿名事例風で入る",
]
CASE_SITUATIONS = [
    "「今の仕事が向いてない気がする、辞めるべきか」という相談",
    "「上司と相性が悪くて疲弊している」という相談",
    "「やりたい仕事がわからない」という相談",
    "「転職するべきか、もう少し続けるべきか」という相談",
    "「同僚と比べて成果が出ない」という悩み",
    "「リモートワークで孤独を感じる」という悩み",
    "「異動先の文化が合わない」という相談",
    "「副業を始めたほうがいいか」という相談",
    "「年収はいいけど消耗している」という相談",
    "「人と話す仕事が辛い」という相談",
]

def make_case_story_tweet() -> str:
    opener    = random.choice(CASE_OPENERS)
    situation = random.choice(CASE_SITUATIONS)
    sample_t  = random.choice(TYPE_KEYS)
    tags      = _random_hashtags()
    prompt = f"""相談事例風のツイートを1件作成してください。

【今回の切り出し方】{opener}
【相談内容】{situation}
【参考タイプ（具体性を出すために言及してもOK）】{sample_t}（{TYPES[sample_t]['nickname']}）

【書き方】
- 相談者の悩みを1〜2行で要約
- ぼくの返答（MBTI×環境の視点）を簡潔に
- 「あなたのせいじゃなく環境のせい」のニュアンスを入れる
- 個人特定にならないよう抽象度を保つ

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 7. 職場環境ミスマッチ論（work_env）
# ══════════════════════════════════════════════════════════
WORK_ENV_AXES = [
    "裁量がある vs ない（マイクロマネジメントの有無）",
    "数字文化 vs 関係文化（評価軸の違い）",
    "成果主義 vs 年功序列",
    "リモート中心 vs 出社中心",
    "ベンチャー的スピード vs 大企業的調整",
    "個人プレー中心 vs チームプレー中心",
    "ロジック重視文化 vs 空気重視文化",
    "変化が多い vs 安定している",
    "縦割り組織 vs フラット組織",
    "短期成果重視 vs 長期育成重視",
]

def make_work_env_tweet() -> str:
    axis = random.choice(WORK_ENV_AXES)
    tags = _random_hashtags()
    prompt = f"""「職種ではなく職場環境がミスマッチ」というテーマで1件作成してください。

【今回の切り口】{axis} という軸でのミスマッチを解説

【書き方】
- 同じ職種でも、この軸で合う・合わないが分かれることを示す
- MBTIのどのタイプがどちら寄りに向いてるかを軽く言及（断定しすぎない）
- 「向いてないのではなく環境が合っていないだけ」という結論に着地

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 8. 認知機能解説（cognitive）
# ══════════════════════════════════════════════════════════
COGNITIVE_FUNCTIONS = [
    ("Ni", "内向的直観", "未来予測・本質を1つの像として捉える", "INTJ/INFJ"),
    ("Ne", "外向的直観", "可能性を広げて連想する・アイデア発散", "ENTP/ENFP/INTP/INFP"),
    ("Si", "内向的感覚", "過去の経験と比較する・安定感を重視", "ISTJ/ISFJ/ESTJ/ESFJ"),
    ("Se", "外向的感覚", "今この瞬間の刺激・行動の素早さ", "ESTP/ESFP/ISTP/ISFP"),
    ("Ti", "内向的思考", "内的な論理整合性・分析の深さ", "INTP/ISTP/ENTP/ESTP"),
    ("Te", "外向的思考", "外部の効率・成果・体系化", "ENTJ/ESTJ/INTJ/ISTJ"),
    ("Fi", "内向的感情", "内的な価値観・自分の信念に忠実", "INFP/ISFP/ENFP/ESFP"),
    ("Fe", "外向的感情", "場の調和・他者の感情への共鳴", "ENFJ/ESFJ/INFJ/ISFJ"),
]

def make_cognitive_tweet() -> str:
    code, name, gist, users = random.choice(COGNITIVE_FUNCTIONS)
    tags = _random_hashtags(extra=["#認知機能"])
    prompt = f"""認知機能の解説ツイートを1件作成してください。

【今回の機能】{code}（{name}）
【ざっくり】{gist}
【主に使うタイプ例】{users}

【書き方】
- 専門用語を噛み砕いて説明（「{code}って聞き慣れないですけど〜」みたいに）
- 「この機能が強い人は、こういう仕事で力を発揮しやすい」という実用面に必ず触れる
- 1ツイート内に詰め込みすぎない。1つの観点に絞る

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 9. 2タイプ比較（pair_compare）
# ══════════════════════════════════════════════════════════
COMPARE_PAIRS = [
    ("INTJ", "ENTJ"), ("INTP", "ENTP"), ("INFJ", "INFP"), ("ENFJ", "ENFP"),
    ("ISTJ", "ISFJ"), ("ESTJ", "ESFJ"), ("ISTP", "ISFP"), ("ESTP", "ESFP"),
    ("INTJ", "INFJ"), ("INTP", "INFP"), ("ENTJ", "ESTJ"), ("ENFP", "ESFP"),
    ("ISTJ", "INTJ"), ("ISFJ", "INFJ"), ("ESTP", "ENTP"), ("ESFJ", "ENFJ"),
]

def make_pair_compare_tweet() -> str:
    t1, t2 = random.choice(COMPARE_PAIRS)
    n1, n2 = TYPES[t1]["nickname"], TYPES[t2]["nickname"]
    tags   = _random_hashtags(extra=[f"#{t1}", f"#{t2}"])
    prompt = f"""似ているけど違う2タイプの比較ツイートを1件作成してください。

【比較対象】{t1}（{n1}） vs {t2}（{n2}）

【書き方】
- 「似てるけどここが違う」というポイントを1つに絞る
- 行動・職場での反応・キャリア選択の差など、具体的な場面で対比
- どちらが優れているという書き方は絶対にしない

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 10. 弱みを強みに読み替え（reframe）
# ══════════════════════════════════════════════════════════
REFRAME_THEMES = [
    "「考えすぎる」と言われる人の強み",
    "「優柔不断」と言われる人の本当の力",
    "「空気を読みすぎる」と言われる人の活かし方",
    "「マイペース」と言われる人が向いてる環境",
    "「飽きっぽい」と言われる人の市場価値",
    "「人見知り」と言われる人の仕事での強み",
    "「真面目すぎる」と言われる人の活躍場面",
    "「理屈っぽい」と言われる人の役割",
    "「感情的」と言われる人が活きる職場",
    "「行動が遅い」と言われる人の慎重さの価値",
    "「目立ちたがり」と言われる人の戦力性",
    "「冷たい」と言われる人の判断力",
]

def make_reframe_tweet() -> str:
    theme = random.choice(REFRAME_THEMES)
    tags  = _random_hashtags()
    prompt = f"""「弱みと言われがちな特性を強みに読み替える」ツイートを1件作成してください。

【今回のテーマ】{theme}

【書き方】
- まず「〜って言われたことありませんか」と共感から入る
- それがどういう場面・職場で武器になるかを示す
- MBTIタイプ名を出す場合は具体的に（複数OK）
- 「直すべき欠点ではなく、活かす環境を選ぶ話」というトーン

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 11. 短文のぼやき（micro_voice）
# ══════════════════════════════════════════════════════════
MICRO_THEMES = [
    "ふと思ったこと（仕事観について）",
    "最近の相談で感じたこと",
    "MBTI診断についての小さな違和感",
    "「向いてる仕事」という言葉への補足",
    "転職活動で大事だと思う1つのこと",
    "性格診断との付き合い方",
    "「自分らしく働く」って何だろうという問い",
    "市場価値という言葉の使われ方への一言",
]

def make_micro_voice_tweet() -> str:
    theme = random.choice(MICRO_THEMES)
    tags  = _random_hashtags(n=1)
    prompt = f"""短文の独り言・ぼやき系ツイートを1件作成してください。

【今回の話題】{theme}

【書き方】
- 全体で60〜80文字程度の短さ（日本語換算）
- 結論や説得を目的にしない。ぽつりと言う感じ
- 改行を活かしてリズムを作る
- ハッシュタグは1〜2個でOK（少なめ）

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 12. MBTI誤解の訂正（myth_buster）
# ══════════════════════════════════════════════════════════
MYTHS = [
    "「I型は人と話せない」という誤解",
    "「E型は常に元気」という誤解",
    "「T型は冷たい」という誤解",
    "「F型は論理が苦手」という誤解",
    "「J型は柔軟性がない」という誤解",
    "「P型はだらしない」という誤解",
    "「N型は地に足がついていない」という誤解",
    "「S型はクリエイティブじゃない」という誤解",
    "「MBTIは血液型占いと同じ」という誤解",
    "「タイプで人の優劣が決まる」という誤解",
    "「タイプは一生変わらない」という誤解",
    "「自分のタイプの典型例と違う＝診断が間違い」という誤解",
]

def make_myth_buster_tweet() -> str:
    myth = random.choice(MYTHS)
    tags = _random_hashtags()
    prompt = f"""MBTIにまつわる誤解を解くツイートを1件作成してください。

【今回扱う誤解】{myth}

【書き方】
- 「〜って思われがちなんですが」から本題に入る形が自然
- 誤解が生まれる理由にも軽く触れる
- 正しい捉え方を1〜2行で示す
- 攻撃的にならず、やわらかく訂正する

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 13. 上司・部下の相性（boss_subordinate）
# ══════════════════════════════════════════════════════════
BOSS_SUB_SCENES = [
    "細かく管理してくる上司への対処法（被管理側の視点）",
    "指示があいまいな上司への対応（タイプ別）",
    "感情の起伏が激しい上司への向き合い方",
    "数字しか見ない上司との関係づくり",
    "報連相を細かく求める上司・求めない上司の差",
    "部下が動かないとき、タイプ別に効くアプローチ",
    "部下のモチベを下げる上司のNG行動",
    "上司と相性が悪いと感じたときに本当に見るべきこと",
    "1on1で上司・部下それぞれが意識したいこと",
    "「優秀だけど怖い上司」が出す本当のサイン",
]

def make_boss_subordinate_tweet() -> str:
    scene = random.choice(BOSS_SUB_SCENES)
    tags  = _random_hashtags(extra=["#上司", "#部下"])
    prompt = f"""上司・部下の相性に関するツイートを1件作成してください。

【今回のテーマ】{scene}

【書き方】
- MBTIの軸（T/F, J/P など）でなぜ相性が出るかを軽く言及
- 具体的な行動・セリフ・場面を1つ入れる
- 「相性が悪い＝どちらかが悪い」ではなく、認知の違いの話に着地

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 14. 面接シーン（interview_scene）
# ══════════════════════════════════════════════════════════
INTERVIEW_SCENES = [
    "面接で「自分の弱み」を聞かれたときのタイプ別正解",
    "緊張で頭が真っ白になりがちなタイプ・対策",
    "面接官に「論理的でない」と思われやすいタイプの誤解",
    "面接で空気を読みすぎて自分を出せないタイプの対処",
    "「志望動機」を語るときに本音をどこまで出すか",
    "面接官が無表情で焦るタイプ・気にならないタイプ",
    "「逆質問」で印象を上げるタイプ別アプローチ",
    "オンライン面接で評価が下がりやすいタイプの傾向",
    "圧迫面接で力を発揮できるタイプ・苦手なタイプ",
    "最終面接で落ちる人がやりがちなタイプ別ミス",
]

def make_interview_scene_tweet() -> str:
    scene = random.choice(INTERVIEW_SCENES)
    tags  = _random_hashtags(extra=["#面接", "#転職"])
    prompt = f"""面接シーンに関するツイートを1件作成してください。

【今回のテーマ】{scene}

【書き方】
- 面接という限定的な場面に絞った具体的な話
- タイプ別の対処法・心構えを必ず添える
- 「面接で評価される人＝優秀な人」ではないという視点を持つ

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 15. 退職を考えるサイン（resignation_signs）
# ══════════════════════════════════════════════════════════
RESIGN_SIGNS = [
    "「日曜の夜が来るのが怖い」と感じ始めたとき",
    "通勤中に動悸がするようになったとき",
    "仕事のミスが急に増えてきたとき",
    "同僚との会話が減って、孤独感が強まったとき",
    "休日も仕事のことを考え続けるようになったとき",
    "「3年は続けろ」という言葉が苦しくなったとき",
    "目標が立てられなくなったとき",
    "尊敬していた先輩・同僚が次々辞めていくとき",
    "やる気が出ないのを「自分のせい」と責め始めたとき",
    "給料明細を見ても何も感じなくなったとき",
]

def make_resignation_signs_tweet() -> str:
    sign = random.choice(RESIGN_SIGNS)
    tags = _random_hashtags()
    prompt = f"""退職を考えるべきサインに関するツイートを1件作成してください。

【今回扱うサイン】{sign}

【書き方】
- このサインがどのタイプに出やすいかを軽く言及
- 「すぐ辞めろ」ではなく「立ち止まって見直そう」のトーン
- 自分を責めなくていい、という視点を必ず入れる

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 16. ストレス対処・回復方法（stress_recovery）
# ══════════════════════════════════════════════════════════
STRESS_AXES = [
    "I型のストレス回復は「一人時間」、E型は「人との会話」",
    "N型は「未来の話」で回復、S型は「目の前の作業」で回復",
    "T型は「分析・整理」で回復、F型は「気持ちを聞いてもらう」で回復",
    "J型は「予定を立て直す」で回復、P型は「予定をなくす」で回復",
    "ストレスが頂点に達したときに現れる「グリップ」現象",
    "タイプ別の「燃え尽き」の兆候と回復の入口",
    "週末の過ごし方で消耗が決まる、タイプ別の正解",
    "睡眠だけでは回復しないタイプの特徴と必要なケア",
]

def make_stress_recovery_tweet() -> str:
    axis = random.choice(STRESS_AXES)
    tags = _random_hashtags(extra=["#ストレス"])
    prompt = f"""ストレス対処・回復方法に関するツイートを1件作成してください。

【今回の切り口】{axis}

【書き方】
- 具体的な行動レベルで提案する（抽象論で終わらない）
- 「自分にとっての回復」と「他人にとっての回復」が違うことを示す
- 押しつけがましくならない

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 17. チーム内での役割（team_role）
# ══════════════════════════════════════════════════════════
TEAM_ROLES = [
    "アイデアを出す人、形にする人、推進する人、調整する人",
    "ENTPやENFPが起点になりやすい場面",
    "ISTJやISFJが場を支えている見えない貢献",
    "INTJやINFJが孤立しがちなチーム構造と対処",
    "ESTPやESFPが空気を変える瞬間",
    "ENFJやESFJの調和役としての消耗ポイント",
    "INTPやISTPの観察力が活きるタイミング",
    "INFPやISFPの「らしさ」が武器になる場面",
]

def make_team_role_tweet() -> str:
    role = random.choice(TEAM_ROLES)
    tags = _random_hashtags(extra=["#チームビルディング"])
    prompt = f"""チーム内での役割傾向に関するツイートを1件作成してください。

【今回の切り口】{role}

【書き方】
- 「目立つ役割が偉い」という構図にしない
- それぞれの貢献の質が違うだけ、というトーン
- 自分の役割が見えると消耗が減るという示唆

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 18. 副業との相性（side_job）
# ══════════════════════════════════════════════════════════
SIDE_JOB_THEMES = [
    "副業が向いてるタイプ・向いてないタイプの差",
    "副業を始める前に確認したい、タイプ別の落とし穴",
    "「本業＋副業」で消耗するタイプの特徴",
    "副業で結果を出しやすい人の共通点",
    "副業の選び方：本業の補完 vs 全く違う領域",
    "クリエイティブ系副業に向いてるタイプ",
    "コツコツ系副業（ライティング・データ入力）が向くタイプ",
    "対人系副業（コーチング・コンサル）が向くタイプ",
]

def make_side_job_tweet() -> str:
    theme = random.choice(SIDE_JOB_THEMES)
    tags  = _random_hashtags(extra=["#副業"])
    prompt = f"""副業との相性に関するツイートを1件作成してください。

【今回のテーマ】{theme}

【書き方】
- 「副業すべき」ではなく「向き不向きがある」というトーン
- 具体的な副業ジャンルを最低1つは挙げる
- 本業の安定が前提という視点を欠かさない

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 19. お金・年収との向き合い方（money_view）
# ══════════════════════════════════════════════════════════
MONEY_THEMES = [
    "「年収が上がっても幸福度が上がらない人」のタイプ傾向",
    "お金で動けるタイプ・お金では動かないタイプの違い",
    "年収交渉が得意なタイプ・苦手なタイプ",
    "「やりがい」と「年収」の天秤、タイプ別の最適解",
    "お金の話を職場で出すことの心理的ハードルとタイプ",
    "貯金志向と投資志向、タイプ別の傾向",
    "「年収を上げる転職」が向いてないタイプの特徴",
]

def make_money_view_tweet() -> str:
    theme = random.choice(MONEY_THEMES)
    tags  = _random_hashtags(extra=["#年収"])
    prompt = f"""お金・年収との向き合い方に関するツイートを1件作成してください。

【今回のテーマ】{theme}

【書き方】
- 年収の高低を価値判断にしない
- お金で動けない人を「意識が低い」と評価しない
- タイプ別の価値観の違いとして提示する

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 20. 年代別キャリア論（growth_phase）
# ══════════════════════════════════════════════════════════
PHASE_THEMES = [
    "20代の転職で気をつけたい「逃げグセ」の見極め",
    "30代の転職で武器になる「再現性」の言語化",
    "40代の転職で評価される「巻き込み力」の正体",
    "20代後半に多い「このままでいいのか」迷子の処方箋",
    "30代前半の「責任が増えてきた」消耗パターン",
    "30代後半の「キャリアの折り返し」感覚への対処",
    "40代の「役職定年」を見据えたタイプ別準備",
    "新卒3年目に多い「自分の市場価値が見えない」不安",
]

def make_growth_phase_tweet() -> str:
    theme = random.choice(PHASE_THEMES)
    tags  = _random_hashtags()
    prompt = f"""年代別キャリア論のツイートを1件作成してください。

【今回のテーマ】{theme}

【書き方】
- 年齢を「制約」ではなく「タイミング」として扱う
- タイプ別に効くアプローチを最低1つ
- 「焦らなくていい」のトーンを基本に

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 21. 業界別の向き不向き（industry_fit）
# ══════════════════════════════════════════════════════════
INDUSTRIES = [
    ("IT・ソフトウェア", "論理重視・変化が早い"),
    ("金融・銀行", "正確性重視・縦割り傾向"),
    ("コンサル", "問題解決志向・短期成果"),
    ("広告・マーケ", "発想力・トレンド感覚"),
    ("メーカー（製造）", "プロセス重視・チーム協働"),
    ("商社", "対人折衝・グローバル"),
    ("不動産", "営業力・対面コミュ"),
    ("教育", "対人ケア・長期育成"),
    ("医療・福祉", "共感力・体力"),
    ("行政・公務員", "ルール遵守・安定志向"),
    ("スタートアップ", "高速試行・曖昧耐性"),
    ("クリエイティブ職", "個性発揮・締切耐性"),
]

def make_industry_fit_tweet() -> str:
    industry, traits = random.choice(INDUSTRIES)
    tags = _random_hashtags(extra=["#業界研究"])
    prompt = f"""業界別の向き不向きに関するツイートを1件作成してください。

【今回扱う業界】{industry}（特徴：{traits}）

【書き方】
- この業界に向いてる傾向のあるタイプを具体的に
- 「この業界に向いてない＝劣ってる」ではなく「環境が合わない」という整理
- 同じ業界内でも会社差が大きいことに軽く触れる

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 22. リモートワーク適性（remote_work）
# ══════════════════════════════════════════════════════════
REMOTE_THEMES = [
    "リモートで成果が上がるタイプ・下がるタイプの差",
    "在宅で孤独を感じやすいタイプの特徴と対処",
    "出社派・リモート派、それぞれが消耗する理由",
    "ハイブリッド勤務でストレスが増えるタイプ",
    "リモートで評価されにくいタイプの傾向と打開策",
    "リモートで集中が持続するタイプの環境設計",
    "在宅勤務で家族・同居人と揉めやすいタイプ",
]

def make_remote_work_tweet() -> str:
    theme = random.choice(REMOTE_THEMES)
    tags  = _random_hashtags(extra=["#リモートワーク", "#在宅勤務"])
    prompt = f"""リモートワーク適性に関するツイートを1件作成してください。

【今回のテーマ】{theme}

【書き方】
- リモート/出社のどちらが優れてるという話にしない
- タイプ別の合う・合わないという整理
- 自分に合った働き方を選ぶ視点を促す

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 23. マネジメント・管理職向け（management_style）
# ══════════════════════════════════════════════════════════
MGMT_THEMES = [
    "部下が育つマネジメントスタイル、タイプ別の正解",
    "「叱る」のが苦手なマネージャーの対処法",
    "細かく見るマネジメントが向いてるタイプ・任せるべきタイプ",
    "1on1で何を話せばいいか分からないとき",
    "プレイヤー時代に優秀だった人がマネージャーで詰む理由",
    "メンバーのモチベを「上げよう」とするから失敗する話",
    "タイプ別、評価フィードバックの伝え方",
    "管理職向き・管理職向かないタイプの本当の見分け方",
]

def make_management_style_tweet() -> str:
    theme = random.choice(MGMT_THEMES)
    tags  = _random_hashtags(extra=["#マネジメント", "#管理職"])
    prompt = f"""マネジメント・管理職向けのツイートを1件作成してください。

【今回のテーマ】{theme}

【書き方】
- 上から目線にならない（管理職経験者でも初心者でも読める）
- タイプ別の具体的な行動指針を最低1つ
- 「正解の管理職像」を押しつけない

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 24. 対話形式（dialogue）
# ══════════════════════════════════════════════════════════
DIALOGUE_SCENARIOS = [
    "20代相談者「今の会社、辞めるべきですか」への返答",
    "30代相談者「やりたいことが分からない」への返答",
    "新卒相談者「自分に合う仕事が分からない」への返答",
    "管理職相談者「部下が動いてくれない」への返答",
    "相談者「MBTIで決めていいんですか」への返答",
    "相談者「3年は続けるべき、本当ですか」への返答",
    "相談者「向いてないけど続けたほうがいい？」への返答",
    "相談者「自分のタイプが嫌いです」への返答",
]

def make_dialogue_tweet() -> str:
    scenario = random.choice(DIALOGUE_SCENARIOS)
    tags     = _random_hashtags()
    prompt = f"""対話形式のツイートを1件作成してください。

【今回のシナリオ】{scenario}

【書き方】
- 「相談者：〜」「ぼく：〜」のような2行対話の形にする
- 質問は1〜2行、返答は3〜4行
- 返答は決めつけず、考える材料を渡す形
- 必要なら最後に短い補足

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 25. リスト形式（list_format）
# ══════════════════════════════════════════════════════════
LIST_THEMES = [
    "向いてる職場の見極めポイント3つ",
    "転職で失敗しやすい人の特徴3つ",
    "INTJが消耗する職場の条件3つ",
    "ENFPが活きる仕事の条件3つ",
    "「成長できる職場」のサイン3つ",
    "「合わない上司」のサイン3つ",
    "適職を見つけるための問い3つ",
    "面接で印象が良くなる行動3つ",
    "新卒3年以内に身につけたい力3つ",
    "30代の転職で武器になる経験3つ",
]

def make_list_format_tweet() -> str:
    theme = random.choice(LIST_THEMES)
    tags  = _random_hashtags()
    prompt = f"""リスト形式のツイートを1件作成してください。

【今回のテーマ】{theme}

【書き方】
- 「・」または「①②③」「1. 2. 3.」などで3つ並列に提示
- 各項目は1行で簡潔に
- リストの前に1行、後ろに1行の補足を添える
- 箇条書きだけで終わらず、人間味のあるコメントで締める

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 26. 一般論への反論（counter_argument）
# ══════════════════════════════════════════════════════════
COUNTER_THEMES = [
    "「やりたいことを仕事にすべき」への違和感",
    "「3年は続けるべき」という常識への異論",
    "「好きを仕事に」が機能しないケース",
    "「人と関わる仕事は誰でもできる」という誤解",
    "「内向型は営業に向かない」への反論",
    "「年収こそ全て」というロジックの落とし穴",
    "「成長環境がベスト」とは限らない話",
    "「自分に厳しく」が裏目に出る人の特徴",
    "「メンタルが弱い」と言われがちな人の本当の強さ",
    "「向いてないなら辞めるべき」への補足",
]

def make_counter_argument_tweet() -> str:
    theme = random.choice(COUNTER_THEMES)
    tags  = _random_hashtags()
    prompt = f"""一般論への反論・違和感を示すツイートを1件作成してください。

【今回のテーマ】{theme}

【書き方】
- 「〜って言われがちですが」から入ると自然
- 否定で終わらず、代わりの視点を必ず示す
- 攻撃的・断罪的にならない。柔らかく反論

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 27. 隠れた強み3選（type_strength_3）
# ══════════════════════════════════════════════════════════

def make_type_strength_3_tweet() -> str:
    mbti_type = random.choice(TYPE_KEYS)
    data      = TYPES[mbti_type]
    nick      = data["nickname"]
    tags      = _random_hashtags(extra=[f"#{mbti_type}"])
    prompt = f"""{mbti_type}（{nick}）の「本人が気づきにくい隠れた強み」を3つ挙げるツイートを1件作成してください。

【タイプ】{mbti_type}（{nick}）
【タイプの特徴】{data['tagline']}

【書き方】
- ありきたりな「優しい」「真面目」ではなく、職場で役立つ具体的な強み
- 「・」または「1. 2. 3.」で3つ並列に示す
- 各項目は1行で簡潔に
- 最後に「もっと自分を頼っていいですよ」的なやわらかい一言

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 28. 合わない会社のサイン（bad_company_signs）
# ══════════════════════════════════════════════════════════
BAD_COMPANY_SIGNS = [
    "面接で社員の表情が硬い・誰も笑わない",
    "「うちは家族みたいな会社」を強調する違和感",
    "募集要項に「やる気重視」しか書いていない",
    "口コミに「上司次第」というワードが多い",
    "離職率を聞いても明言を避ける",
    "残業時間の質問にトーンが変わる",
    "「成長できる環境」しか強みがない",
    "オフィスツアーで現場を見せたがらない",
    "面接官が現場の人間を出さない",
    "内定承諾の即決を強く迫る",
]

def make_bad_company_signs_tweet() -> str:
    sign = random.choice(BAD_COMPANY_SIGNS)
    tags = _random_hashtags(extra=["#転職活動"])
    prompt = f"""合わない会社・避けたほうがいい会社のサインに関するツイートを1件作成してください。

【今回扱うサイン】{sign}

【書き方】
- 特定の企業名・業界名は絶対に出さない
- 「絶対ダメ」ではなく「赤信号の可能性」というトーン
- タイプによって耐性に差があることに軽く触れる

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 29. ポータブルスキル論（transferable_skill）
# ══════════════════════════════════════════════════════════
PORTABLE_SKILLS = [
    "業界が変わっても評価される「構造化する力」",
    "職種が変わっても通用する「対人観察力」",
    "どこでも通用する「優先順位づけ」の習慣",
    "再現性のある「課題発見力」の身につけ方",
    "数値化できなくても評価される「巻き込み力」",
    "MBTIタイプ別の「自然と身につくポータブルスキル」",
    "ポータブルスキルを言語化できないと損する場面",
    "副業・転職どちらにも効く「説明力」の磨き方",
]

def make_transferable_skill_tweet() -> str:
    skill = random.choice(PORTABLE_SKILLS)
    tags  = _random_hashtags()
    prompt = f"""ポータブルスキル（持ち運べる力）に関するツイートを1件作成してください。

【今回のテーマ】{skill}

【書き方】
- 具体例（場面・行動）を最低1つ入れる
- タイプ別に身につけやすいスキルの差にも軽く触れる
- 「資格」ではなく「習慣・思考のクセ」レベルの話

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 30. 深い問い（deep_question）
# ══════════════════════════════════════════════════════════
DEEP_QUESTIONS = [
    "「働く」とは何のためか、という根本の問い",
    "「向いてる仕事」を探すことの限界",
    "やりたいことが見つからないのは悪いことか",
    "「成長」を目的にしないキャリア設計はあり得るか",
    "好きでも得意でもない仕事を選ぶ理由",
    "「自分らしさ」を仕事に求めることのリスク",
    "やりがいと給料、どちらかを諦める覚悟",
    "MBTI診断が当たることの不気味さと安心",
    "「天職」という言葉への違和感",
    "自分を変えるべきか、環境を変えるべきか",
]

def make_deep_question_tweet() -> str:
    q = random.choice(DEEP_QUESTIONS)
    tags = _random_hashtags(n=1)
    prompt = f"""深い問いを投げかけるツイートを1件作成してください。

【今回の問い】{q}

【書き方】
- 答えを断定しない。問いを共有する形
- 自分なりの仮説を1つだけ添える
- 短めで余白のある書き方（70〜100文字程度）
- ハッシュタグは1〜2個と少なめ

{_flavor_block()}
【末尾ハッシュタグ】{tags}"""
    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# Claude API 呼び出し
# ══════════════════════════════════════════════════════════
_RECENT_TWEETS_CONTEXT: list[str] = []

def set_recent_tweets(tweets: list[str]) -> None:
    global _RECENT_TWEETS_CONTEXT
    _RECENT_TWEETS_CONTEXT = tweets


def _call_claude(prompt: str, max_retries: int = 3) -> str:
    client      = _get_client()
    history_ctx = _build_history_context(_RECENT_TWEETS_CONTEXT)
    full_prompt = f"{prompt}\n\n{history_ctx}" if history_ctx else prompt

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                system=CHARACTER_SYSTEM,
                messages=[{"role": "user", "content": full_prompt}],
            )
            text = response.content[0].text.strip()
            text = re.sub(r'\*+', '', text)

            char_count = _x_char_count(text)
            if char_count > 280:
                over = char_count - 280
                if attempt < max_retries - 1:
                    print(f"[content] 文字数超過 {char_count}/280 (+{over}) → 再生成 ({attempt+1}/{max_retries})")
                    cut_chars = (over + 1) // 2
                    full_prompt = (
                        f"{full_prompt}\n\n"
                        f"※前回の生成が280カウントを{over}超過しました。"
                        f"日本語に換算して約{cut_chars}文字削ってください（全体を130文字以内に収めること）。"
                    )
                    continue
                else:
                    print(f"[content] 警告: 文字数超過 {char_count}/280 (+{over}) のまま返します（リトライ上限）")
            return text

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[content] Claude API エラー (attempt {attempt+1}/{max_retries}): {e} → リトライ")
            else:
                raise RuntimeError(f"Claude API エラー: {e}") from e
    return ""


# ══════════════════════════════════════════════════════════
# メインエントリ
# ══════════════════════════════════════════════════════════
_GENERATORS = {
    # 第1陣
    "aruaru":             make_aruaru_tweet,
    "tips":               make_tips_tweet,
    "site_lead":          make_site_lead_tweet,
    "article_intro":      make_article_intro_tweet,
    "quiz":               make_quiz_tweet,
    # 第2陣
    "case_story":         make_case_story_tweet,
    "work_env":           make_work_env_tweet,
    "cognitive":          make_cognitive_tweet,
    "pair_compare":       make_pair_compare_tweet,
    "reframe":            make_reframe_tweet,
    "micro_voice":        make_micro_voice_tweet,
    "myth_buster":        make_myth_buster_tweet,
    # 第3陣（新規18種）
    "boss_subordinate":   make_boss_subordinate_tweet,
    "interview_scene":    make_interview_scene_tweet,
    "resignation_signs":  make_resignation_signs_tweet,
    "stress_recovery":    make_stress_recovery_tweet,
    "team_role":          make_team_role_tweet,
    "side_job":           make_side_job_tweet,
    "money_view":         make_money_view_tweet,
    "growth_phase":       make_growth_phase_tweet,
    "industry_fit":       make_industry_fit_tweet,
    "remote_work":        make_remote_work_tweet,
    "management_style":   make_management_style_tweet,
    "dialogue":           make_dialogue_tweet,
    "list_format":        make_list_format_tweet,
    "counter_argument":   make_counter_argument_tweet,
    "type_strength_3":    make_type_strength_3_tweet,
    "bad_company_signs":  make_bad_company_signs_tweet,
    "transferable_skill": make_transferable_skill_tweet,
    "deep_question":      make_deep_question_tweet,
}


def generate_tweet(content_type: str | None = None, recent_tweets: list[str] | None = None) -> dict:
    from config import CONTENT_TYPES

    if recent_tweets is not None:
        set_recent_tweets(recent_tweets)

    if content_type is None:
        types   = list(CONTENT_TYPES.keys())
        weights = list(CONTENT_TYPES.values())
        content_type = random.choices(types, weights=weights, k=1)[0]

    if content_type not in _GENERATORS:
        raise ValueError(f"Unknown content_type: {content_type!r}")

    text = _GENERATORS[content_type]()
    return {"type": content_type, "text": text}


# ── 動作確認 ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    ctype = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"[generate] type={ctype or 'random'}")
    tweet = generate_tweet(ctype)
    print(f"\n[type={tweet['type']}]")
    print(f"{tweet['text']}\n({_x_char_count(tweet['text'])}カウント)")
