"""
MBTIキャリア X Bot — コンテンツ生成モジュール
Claude API（claude-sonnet-4-6）で毎回動的生成。

コンテンツ種別：
  1. aruaru        - MBTIタイプ別あるある
  2. tips          - 適職・キャリアTips
  3. site_lead     - サイト誘導
  4. article_intro - タイプ別記事紹介（URL付き）
  5. quiz          - 診断クイズ形式
"""
import re
import random
from pathlib import Path

import anthropic

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from generate_articles import TYPES

from config import ANTHROPIC_API_KEY, SITE_URL

# ── Claudeクライアント ────────────────────────────────────
_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


# ── タイプ別URL ───────────────────────────────────────────
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
    """X APIのweighted文字数を計算（上限280）"""
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


# ── キャラクター設定（character.md から読み込み） ──────────
_CHAR_MD = (Path(__file__).parent / "character.md").read_text(encoding="utf-8")

CHARACTER_SYSTEM = f"""あなたは「キャリア研たろう」というキャラクターとしてXに投稿するツイートを書きます。
以下のキャラクター設定を厳密に守ってください。

{_CHAR_MD}

---

【投稿の追加ルール】
- X文字数上限：280カウント以内（日本語1文字=2カウント、URL=23カウント固定、改行=1カウント）
  → 日本語中心なら本文は実質110〜120文字程度が目安。必ず守ること。
- URLは1件まで。ハッシュタグは2〜3個のみ。
- 改行は適切に使い、読みやすくする。
- 「キャリア研たろうです」などの自己紹介は不要。

【出力形式】
ツイート本文のみを出力。「ツイート：」「以下が〜」などの前置きは一切不要。"""


# ── 過去ツイート履歴をプロンプトに変換 ───────────────────
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
def make_aruaru_tweet(mbti_type: str | None = None) -> str:
    if mbti_type is None:
        mbti_type = random.choice(list(TYPES.keys()))

    data   = TYPES[mbti_type]
    nick   = data["nickname"]
    sample = random.choice(data["aruaru"])["text"]

    prompt = f"""{mbti_type}（{nick}）のあるあるツイートを1件作成してください。

【参考データ（サイトの既存内容）】
タイプの特徴：{data['tagline']}
あるある例（参考のみ・そのまま使わないこと）：{sample}

【要件】
- 「{mbti_type}（{nick}）あるある、言っていいですか。」「これ、{mbti_type}あるあるだと思うんですけど。」などの導入から始める
- 具体的なシーン・行動・感覚を描写する（職場・日常・転職活動など）
- 末尾に「#MBTI #{mbti_type} #性格診断」を付ける"""

    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 2. キャリアTipsツイート
# ══════════════════════════════════════════════════════════
TIPS_THEMES = [
    "転職活動でやりがちなミスと、MBTIを使った改善策",
    "「仕事が合わない」と感じる本当の原因（職種より職場環境）",
    "MBTIのN型とS型で、向いてる職場環境の違い",
    "MBTIのT型とF型で、消耗しやすい仕事の違い",
    "年収を上げるための転職タイミングとデータ",
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
]

def make_tips_tweet() -> str:
    theme = random.choice(TIPS_THEMES)

    prompt = f"""以下のテーマでキャリア・転職のTipsツイートを1件作成してください。

【テーマ】{theme}

【要件】
- データや具体的な数字・傾向を盛り込む
- 「ぼくのデータだと〜」「ぼくが見てきた中では〜」など一人称で語る
- 「あなたのせいじゃなく環境のせい」という視点を入れると◎
- ハッシュタグ例：#転職 #キャリア #MBTI #適職 から2〜3個選ぶ"""

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
]

def make_site_lead_tweet() -> str:
    angle     = random.choice(LEAD_ANGLES)
    rand_type = random.choice(list(TYPES.keys()))
    rand_nick = TYPES[rand_type]["nickname"]

    prompt = f"""以下の切り口でcareer-kentaro.comのMBTI適職診断サイトへの誘導ツイートを1件作成してください。

【切り口】{angle}
【サイトURL】{SITE_URL}
【タイプ例（使っても使わなくてもOK）】{rand_type}（{rand_nick}）

【要件】
- URLを必ず1件含める
- 押しつけがましくなく、自然に「見てみようかな」と思わせる文体
- ハッシュタグ：#MBTI #適職 #転職 から2〜3個"""

    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# 4. 記事紹介ツイート
# ══════════════════════════════════════════════════════════
INTRO_ANGLES = [
    "このタイプの強みと、それが活きる仕事の紹介",
    "このタイプが消耗しやすい職場環境の警告",
    "「仕事が合わないかも」と感じやすいパターンの紹介",
    "向いてない仕事ワーストの紹介と理由",
]

def make_article_intro_tweet() -> str:
    mbti_type, data = random.choice(list(TYPES.items()))
    nick     = data["nickname"]
    tagline  = data["tagline"]
    angle    = random.choice(INTRO_ANGLES)
    page_url = type_url(mbti_type)

    prompt = f"""以下のMBTIタイプのページ紹介ツイートを1件作成してください。

【タイプ】{mbti_type}（{nick}）
【タイプの特徴】{tagline}
【紹介の切り口】{angle}
【ページURL】{page_url}

【要件】
- URLを必ず含める
- {mbti_type}の人に「自分のことだ」と思わせる具体的な内容
- ハッシュタグ：#MBTI #{mbti_type} #適職 から2〜3個"""

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
]

def make_quiz_tweet() -> str:
    theme = random.choice(QUIZ_THEMES)

    prompt = f"""以下のテーマでMBTI診断クイズ形式のツイートを1件作成してください。

【テーマ】{theme}
【サイトURL】{SITE_URL}

【要件】
- 「ちょっと聞いてもいいですか？」から始める
- A/Bの2択を提示する
- 結果（どのタイプ傾向か）を簡潔に解説する
- URLを末尾に含める
- ハッシュタグ：#MBTI #性格診断 #適職 から2〜3個"""

    return _call_claude(prompt)


# ══════════════════════════════════════════════════════════
# Claude API 呼び出し（リトライ・文字数チェック付き）
# ══════════════════════════════════════════════════════════
_RECENT_TWEETS_CONTEXT: list[str] = []  # scheduler が set_recent_tweets() で渡す

def set_recent_tweets(tweets: list[str]) -> None:
    """schedulerから過去ツイートを注入する"""
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

            # X文字数チェック（280超えなら再生成）
            char_count = _x_char_count(text)
            if char_count > 280:
                if attempt < max_retries - 1:
                    over = char_count - 280
                    full_prompt = (
                        f"{full_prompt}\n\n"
                        f"※前回の生成が{char_count}カウントで超過しました。{over}カウント分短くしてください。"
                    )
                    continue

            return text

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Claude API エラー: {e}") from e

    return ""


# ══════════════════════════════════════════════════════════
# メインエントリ
# ══════════════════════════════════════════════════════════
_GENERATORS = {
    "aruaru":        make_aruaru_tweet,
    "tips":          make_tips_tweet,
    "site_lead":     make_site_lead_tweet,
    "article_intro": make_article_intro_tweet,
    "quiz":          make_quiz_tweet,
}


def generate_tweet(content_type: str | None = None, recent_tweets: list[str] | None = None) -> dict:
    """
    ツイートを生成して返す。
    Args:
        content_type: コンテンツ種別（Noneならconfig.pyの重みでランダム選択）
        recent_tweets: Supabaseから取得した過去ツイートリスト（重複回避用）
    Returns:
        {"type": str, "text": str}
    """
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
    ctype = sys.argv[1] if len(sys.argv) > 1 else "tips"
    print(f"[generate] type={ctype}")
    tweet = generate_tweet(ctype)
    print(f"\n{tweet['text']}\n({_x_char_count(tweet['text'])}カウント)")
