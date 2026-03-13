"""
Azure Functions メインエントリポイント。
タイマートリガーで X アカウントを巡回し、新規ツイートを Viva Engage へ転送する。
"""
import logging
import os

import azure.functions as func

from engage_client import post_to_engage
from keyvault_client import get_secret
from state_manager import ensure_table_exists, get_last_tweet_id, set_last_tweet_id
from x_client import fetch_new_tweets

logger = logging.getLogger(__name__)

app = func.FunctionApp()

# コールドスタート時に状態テーブルの存在を確保
try:
    ensure_table_exists()
except Exception:
    logger.warning("状態テーブルの確認に失敗しました（初回実行時に再試行されます）", exc_info=True)


@app.function_name(name="FetchAndPostTweets")
@app.schedule(
    schedule="%TIMER_SCHEDULE%",
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=True,
)
def fetch_and_post_tweets(mytimer: func.TimerRequest) -> None:
    if mytimer.past_due:
        logger.warning("タイマーが遅延して実行されています")

    # シークレット取得
    try:
        bearer_token = get_secret("x-bearer-token", env_fallback="X_BEARER_TOKEN")
        webhook_url  = get_secret("logic-app-webhook-url", env_fallback="LOGIC_APP_WEBHOOK_URL")
    except Exception:
        logger.critical("必須シークレットの取得に失敗しました。処理を中断します", exc_info=True)
        return

    # 監視対象アカウントの取得
    accounts_raw = os.environ.get("X_ACCOUNTS", "").strip()
    if not accounts_raw:
        logger.warning("X_ACCOUNTS が未設定です。処理するアカウントがありません")
        return

    accounts = [a.strip().lstrip("@") for a in accounts_raw.split(",") if a.strip()]
    logger.info("%d アカウントを処理します: %s", len(accounts), accounts)

    total_posted = 0
    total_failed = 0

    for username in accounts:
        logger.info("--- @%s 処理開始 ---", username)

        since_id = get_last_tweet_id(username)
        tweets = fetch_new_tweets(
            bearer_token=bearer_token,
            username=username,
            since_id=since_id,
        )

        if not tweets:
            logger.info("@%s: 新規ツイートなし", username)
            continue

        logger.info("@%s: %d 件を投稿します", username, len(tweets))

        new_since_id = since_id
        for tweet in tweets:
            success = post_to_engage(
                webhook_url=webhook_url,
                tweet_id=tweet.tweet_id,
                author_username=tweet.author_username,
                text=tweet.text,
                published=tweet.created_at,
                post_url=tweet.url,
            )
            if success:
                new_since_id = tweet.tweet_id
                total_posted += 1
            else:
                total_failed += 1
                logger.warning(
                    "@%s: tweet_id=%s の投稿に失敗。このアカウントの残りをスキップ（次回リトライ）",
                    username, tweet.tweet_id,
                )
                break

        # 成功した最後のツイートIDを保存
        if new_since_id and new_since_id != since_id:
            try:
                set_last_tweet_id(username, new_since_id)
            except Exception:
                logger.error(
                    "@%s: last_tweet_id=%s の保存に失敗。次回実行時に重複投稿の可能性があります",
                    username, new_since_id, exc_info=True,
                )

    logger.info(
        "処理完了 | アカウント数: %d | 投稿成功: %d | 投稿失敗: %d",
        len(accounts), total_posted, total_failed,
    )
