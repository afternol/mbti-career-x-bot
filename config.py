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

# ── ファイルパス ─────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
LOG_FILE  = BASE_DIR / "posted_log.json"
LOG_DIR   = BASE_DIR / "logs"
