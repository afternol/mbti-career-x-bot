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

# ── コンテンツタイプと重み ────────────────────────────────────────
CONTENT_TYPES = {
    "aruaru":        35,  # MBTIタイプ別あるある
    "tips":          20,  # 適職・キャリアTips
    "article_intro": 20,  # タイプ別記事紹介（URL付き）
    "site_lead":     15,  # サイト全体への誘導（URL付き）
    "quiz":          10,  # 診断クイズ形式
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
