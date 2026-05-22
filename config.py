"""
MBTIキャリア X Bot — 設定モジュール
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ── X API 認証情報 ──────────────────────────────────────────────
X_API_KEY             = os.getenv("X_API_KEY", "")
X_API_SECRET          = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN        = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

# ── Claude API ──────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── サイト情報 ──────────────────────────────────────────────────
SITE_URL = os.getenv("SITE_URL", "https://career-kentaro.com/mbti/")

# ── コンテンツタイプと重み（合計=100、全30種） ───────────────────
CONTENT_TYPES = {
    # ── 第1陣（既存改修・主軸） ──
    "aruaru":             8,  # MBTIタイプ別あるある
    "tips":               6,  # 適職・キャリアTips
    "article_intro":      5,  # タイプ別記事紹介（URL付き）
    "site_lead":          4,  # サイト全体への誘導（URL付き）
    "quiz":               3,  # 診断クイズ形式
    # ── 第2陣（前回追加） ──
    "case_story":         5,  # 相談事例風
    "work_env":           5,  # 職場環境ミスマッチ論
    "cognitive":          4,  # 認知機能解説
    "pair_compare":       4,  # 2タイプ比較
    "reframe":            5,  # 弱みを強みに読み替え
    "micro_voice":        5,  # 短文のぼやき
    "myth_buster":        4,  # MBTI誤解の訂正
    # ── 第3陣（今回追加18種） ──
    "boss_subordinate":   3,  # 上司・部下の相性と対処
    "interview_scene":    2,  # 面接シーンのタイプ別振る舞い
    "resignation_signs":  3,  # 退職を考えるサイン（タイプ別）
    "stress_recovery":    3,  # ストレス対処・回復方法
    "team_role":          2,  # チーム内での役割傾向
    "side_job":           2,  # 副業との相性
    "money_view":         2,  # お金・年収との向き合い方
    "growth_phase":       2,  # 年代別キャリア論
    "industry_fit":       2,  # 業界別の向き不向き
    "remote_work":        2,  # リモートワーク適性
    "management_style":   2,  # マネジメント・管理職向け
    "dialogue":           3,  # 対話形式（相談者×研たろう）
    "list_format":        3,  # リスト形式（3つのポイント）
    "counter_argument":   3,  # 一般論への反論
    "type_strength_3":    2,  # 隠れた強み3選
    "bad_company_signs":  2,  # 合わない会社のサイン
    "transferable_skill": 2,  # ポータブルスキル論
    "deep_question":      2,  # 働くとは何かという問い
}

# ── X API Bearer Token（検索系API用：Free tierでは401になるため実質未使用） ──
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")

# ── 自動RT設定 ──────────────────────────────────────────────────
BOT_ACCOUNT_ID: str = os.getenv("BOT_ACCOUNT_ID", "")  # 自分のuser_id（数値文字列）

RT_KEYWORDS: list[str] = [
    "MBTI 転職", "MBTI 適職", "MBTI キャリア",
    "性格診断 仕事", "INTJ 仕事", "INFP 転職",
    "ENFP キャリア", "ISTJ 適職",
]

RT_TARGET_ACCOUNTS: list[str] = []  # RT対象アカウントの数値user_idを追加する

RT_DAILY_LIMIT: int = 3  # 1日のRT上限件数

# ── ファイルパス ─────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
LOG_FILE  = BASE_DIR / "posted_log.json"
LOG_DIR   = BASE_DIR / "logs"
RT_LOG    = BASE_DIR / "rt_log.json"
