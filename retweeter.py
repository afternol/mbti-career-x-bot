"""
自動RTモジュール
- キーワード検索からRT
- 特定アカウントのタイムラインからRT
- 1日RT上限管理
"""
import json
import logging
from datetime import datetime, timezone, date
from pathlib import Path

import tweepy

from config import (
    X_API_KEY, X_API_SECRET,
    X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET,
    X_BEARER_TOKEN, BOT_ACCOUNT_ID,
    RT_KEYWORDS, RT_TARGET_ACCOUNTS,
    RT_DAILY_LIMIT, RT_LOG, LOG_DIR,
)

LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=str(LOG_DIR / "retweeter.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ── クライアント生成 ──────────────────────────────────────
def _get_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=X_BEARER_TOKEN,
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )


# ── RTログの読み書き ──────────────────────────────────────
def _load_rt_log() -> dict:
    if RT_LOG.exists():
        with open(RT_LOG, encoding="utf-8") as f:
            return json.load(f)
    return {"rt_ids": [], "daily": {}}


def _save_rt_log(log: dict) -> None:
    with open(RT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def _today_rt_count(log: dict) -> int:
    today = str(date.today())
    return log.get("daily", {}).get(today, 0)


def _increment_daily(log: dict) -> None:
    today = str(date.today())
    log.setdefault("daily", {})
    log["daily"][today] = log["daily"].get(today, 0) + 1


# ── RT実行 ───────────────────────────────────────────────
def _do_retweet(client: tweepy.Client, tweet_id: str, log: dict, dry_run: bool) -> bool:
    """1件RTを実行。成功したらTrueを返す"""
    if tweet_id in log.get("rt_ids", []):
        return False  # 既RT済み

    if dry_run:
        print(f"  [DRY RT] tweet_id={tweet_id}")
        return True

    try:
        client.retweet(tweet_id=tweet_id, user_auth=True)
        log.setdefault("rt_ids", []).append(tweet_id)
        _increment_daily(log)
        _save_rt_log(log)
        logger.info(f"RT成功 tweet_id={tweet_id}")
        print(f"  [RT完了] tweet_id={tweet_id}")
        return True
    except tweepy.TweepyException as e:
        logger.warning(f"RTエラー tweet_id={tweet_id}: {e}")
        return False


# ── キーワード検索RT ──────────────────────────────────────
def retweet_by_keywords(dry_run: bool = False) -> int:
    """
    RT_KEYWORDS に含まれるキーワードで検索してRT。
    - 日本語ツイート・リツイートは除外
    - 1日上限に達したら停止
    Returns: RTした件数
    """
    log    = _load_rt_log()
    client = _get_client()
    rt_count = 0

    for keyword in RT_KEYWORDS:
        remaining = RT_DAILY_LIMIT - _today_rt_count(log)
        if remaining <= 0:
            logger.info("本日のRT上限に達しました")
            break

        query = f"{keyword} lang:ja -is:retweet -is:reply"
        try:
            response = client.search_recent_tweets(
                query=query,
                max_results=10,
                tweet_fields=["public_metrics", "author_id"],
            )
            if not response.data:
                continue

            # いいね数が多い順にソート
            sorted_tweets = sorted(
                response.data,
                key=lambda t: t.public_metrics.get("like_count", 0),
                reverse=True,
            )

            for tweet in sorted_tweets[:3]:
                if _today_rt_count(log) >= RT_DAILY_LIMIT:
                    break
                if str(tweet.author_id) == BOT_ACCOUNT_ID:
                    continue  # 自分のツイートはスキップ
                if _do_retweet(client, str(tweet.id), log, dry_run):
                    rt_count += 1

        except tweepy.TweepyException as e:
            logger.error(f"キーワード検索エラー [{keyword}]: {e}")

    return rt_count


# ── 特定アカウントのタイムラインRT ────────────────────────
def retweet_by_accounts(dry_run: bool = False) -> int:
    """
    RT_TARGET_ACCOUNTS のタイムラインから最新ツイートをRT。
    Returns: RTした件数
    """
    if not RT_TARGET_ACCOUNTS:
        return 0

    log    = _load_rt_log()
    client = _get_client()
    rt_count = 0

    for user_id in RT_TARGET_ACCOUNTS:
        remaining = RT_DAILY_LIMIT - _today_rt_count(log)
        if remaining <= 0:
            break
        try:
            response = client.get_users_tweets(
                id=user_id,
                max_results=5,
                exclude=["retweets", "replies"],
            )
            if not response.data:
                continue

            for tweet in response.data[:2]:
                if _today_rt_count(log) >= RT_DAILY_LIMIT:
                    break
                if _do_retweet(client, str(tweet.id), log, dry_run):
                    rt_count += 1

        except tweepy.TweepyException as e:
            logger.error(f"アカウントタイムライン取得エラー [user_id={user_id}]: {e}")

    return rt_count


# ── まとめてRT実行 ────────────────────────────────────────
def run_auto_retweet(dry_run: bool = False) -> None:
    # X API Freeプランでは検索API(/2/tweets/search/recent)が使用不可のため
    # キーワードRT機能は無効化。特定アカウントRTのみ有効。
    log = _load_rt_log()
    today_count = _today_rt_count(log)

    if today_count >= RT_DAILY_LIMIT:
        print(f"本日のRT上限（{RT_DAILY_LIMIT}件）に達しています")
        return

    print(f"[自動RT開始] 本日残りRT可能数: {RT_DAILY_LIMIT - today_count}件")

    # キーワードRTはFree tierで401エラーになるためスキップ
    kw_count  = 0
    acc_count = retweet_by_accounts(dry_run=dry_run)

    print(f"[自動RT完了] アカウントRT: {acc_count}件")
    logger.info(f"自動RT完了 kw={kw_count} acc={acc_count}")


# ── CLI実行 ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    dry = "--dry" in sys.argv
    run_auto_retweet(dry_run=dry)
