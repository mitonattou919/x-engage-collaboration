"""
X API v2 クライアント。
tweepy を使用して指定アカウントの新規ツイートを取得する。

レート制限（Basic プラン）:
  - GET /2/users/by/username/:username : 100 req/15min
  - GET /2/users/:id/tweets            : 10,000 tweets/月
    ※ since_id 指定で新規ゼロなら読み取りカウントは消費しない
"""
import logging
from dataclasses import dataclass

import tweepy

logger = logging.getLogger(__name__)

# 起動中インスタンス内でのユーザーID キャッシュ（username -> user_id）
_user_id_cache: dict[str, str] = {}


@dataclass
class Tweet:
    tweet_id: str
    author_username: str
    text: str
    created_at: str   # ISO 8601
    url: str


def _tweet_url(username: str, tweet_id: str) -> str:
    return f"https://x.com/{username}/status/{tweet_id}"


def _get_user_id(client: tweepy.Client, username: str) -> str | None:
    key = username.lower()
    if key in _user_id_cache:
        return _user_id_cache[key]

    try:
        resp = client.get_user(username=username, user_auth=False)
        if resp.data:
            user_id = str(resp.data.id)
            _user_id_cache[key] = user_id
            logger.info("@%s -> user_id=%s を解決", username, user_id)
            return user_id
        logger.warning("@%s のユーザーが見つかりません", username)
    except tweepy.TweepyException:
        logger.exception("@%s の user_id 解決に失敗", username)
    return None


def fetch_new_tweets(
    bearer_token: str,
    username: str,
    since_id: str | None = None,
    max_results: int = 5,
) -> list[Tweet]:
    """
    指定アカウントの新規ツイートを取得する（oldest first）。
    エラー時は空リストを返す（呼び出し元で他アカウントの処理を継続できる）。
    """
    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)

    user_id = _get_user_id(client, username)
    if not user_id:
        return []

    try:
        resp = client.get_users_tweets(
            id=user_id,
            since_id=since_id,
            max_results=max_results,
            tweet_fields=["created_at", "author_id", "text"],
            exclude=["retweets", "replies"],
        )
    except tweepy.TooManyRequests:
        logger.warning("@%s: レート制限に達したためスキップ", username)
        return []
    except tweepy.TweepyException:
        logger.exception("@%s: ツイート取得に失敗", username)
        return []

    if not resp.data:
        logger.debug("@%s: 新規ツイートなし（since_id=%s）", username, since_id)
        return []

    # X API はデフォルト新しい順で返すため逆順にして時系列順にする
    tweets = [
        Tweet(
            tweet_id=str(t.id),
            author_username=username,
            text=t.text,
            created_at=str(t.created_at),
            url=_tweet_url(username, str(t.id)),
        )
        for t in reversed(resp.data)
    ]
    logger.info("@%s: %d 件の新規ツイートを取得", username, len(tweets))
    return tweets
