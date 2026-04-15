"""
MBTIキャリア X Bot — メインスクリプト
GitHub Actions で1日3回（朝・昼・夜）実行される。

処理フロー:
  1. posted_log.json から過去ツイートを読み込む（重複回避用）
  2. Claude でコンテンツ生成
  3. X に投稿
  4. posted_log.json に結果を追記
     → GitHub Actions が git commit & push でリポジトリに永続保存

使い方:
  python poster.py          # 本番実行
  python poster.py --dry    # ドライラン（X投稿・ログ保存しない）
  python poster.py --type aruaru  # コンテンツタイプ指定
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import tweepy

from config import (
    X_API_KEY, X_API_SECRET,
    X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET,
    LOG_FILE,
)
from content import generate_tweet

JST = timezone(timedelta(hours=9))


# ─────────────────────────────────────────────
# ログ読み書き
# ─────────────────────────────────────────────

def load_log() -> list[dict]:
    """posted_log.json を読み込む。存在しなければ空リストを返す。"""
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    return []


def save_log(log: list[dict]) -> None:
    """posted_log.json に書き込む。"""
    LOG_FILE.write_text(
        json.dumps(log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_texts(log: list[dict], limit: int = 30) -> list[str]:
    """ログから直近 limit 件のツイートテキストを新しい順で返す。"""
    return [entry["text"] for entry in log[-limit:]][::-1]


# ─────────────────────────────────────────────
# X クライアント
# ─────────────────────────────────────────────

def get_x_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────

def run(content_type: str | None = None, dry_run: bool = False) -> None:
    now_jst = datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    print(f"[poster] 開始 {now_jst}  dry_run={dry_run}")

    # 1. 過去ログ読み込み
    log           = load_log()
    recent_texts  = extract_texts(log)
    print(f"[poster] 過去ログ {len(log)} 件 / 重複チェック用 {len(recent_texts)} 件")

    # 2. コンテンツ生成
    tweet = generate_tweet(content_type=content_type, recent_tweets=recent_texts)
    text  = tweet["text"]
    ctype = tweet["type"]
    print(f"[poster] 生成完了 type={ctype}  {len(text)}文字")
    print(f"--- 本文 ---\n{text}\n-----------")

    if dry_run:
        print("[poster] ドライラン: 投稿・ログ保存をスキップ")
        return

    # 3. X に投稿（403 not-permitted はコンテンツ再生成してリトライ）
    client   = get_x_client()
    tweet_id = None
    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.create_tweet(text=text)
            tweet_id = str(response.data["id"])
            print(f"[poster] 投稿成功 tweet_id={tweet_id}")
            break
        except tweepy.errors.Forbidden as e:
            err_str = str(e)
            if "oauth1" in err_str or "app permissions" in err_str:
                # App permissions が Read only → Developer Portal で Read+Write に変更し Access Token 再生成が必要
                print(f"[poster] 403 権限エラー: X Developer Portal の App permissions を確認してください")
                print(f"[poster]   → https://developer.x.com/en/portal/projects")
                print(f"[poster]   → App Settings > User authentication settings > App permissions")
                print(f"[poster]   → 「Read and Write」に変更後、Access Token & Secret を再生成して GitHub Secrets を更新")
                print(f"[poster] エラー詳細: {e}")
                sys.exit(1)
            elif "not permitted" in err_str and attempt < MAX_RETRIES:
                # スパム検知と判断 → コンテンツ再生成してリトライ
                print(f"[poster] 403 not-permitted（{attempt}回目）→ コンテンツ再生成してリトライ")
                tweet = generate_tweet(content_type=content_type, recent_tweets=recent_texts)
                text  = tweet["text"]
                ctype = tweet["type"]
                print(f"[poster] 再生成完了 type={ctype}")
                print(f"--- 本文（再生成）---\n{text}\n-----------")
            else:
                print(f"[poster] 投稿エラー（リトライ上限 or 不明な権限エラー）: {e}")
                sys.exit(1)
        except tweepy.TweepyException as e:
            print(f"[poster] 投稿エラー: {e}")
            sys.exit(1)
    if tweet_id is None:
        print("[poster] 全リトライ失敗")
        sys.exit(1)

    # 4. ログに追記して保存
    entry = {
        "tweet_id":     tweet_id,
        "content_type": ctype,
        "text":         text,
        "posted_at":    now_jst,
    }
    log.append(entry)
    save_log(log)
    print(f"[poster] ログ保存完了 → posted_log.json ({len(log)} 件)")


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────

if __name__ == "__main__":
    dry   = "--dry"  in sys.argv
    ctype = None
    if "--type" in sys.argv:
        idx = sys.argv.index("--type")
        if idx + 1 < len(sys.argv):
            ctype = sys.argv[idx + 1]

    run(content_type=ctype, dry_run=dry)
