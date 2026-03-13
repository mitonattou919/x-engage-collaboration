"""
Logic Apps Webhook 経由で Viva Engage に投稿するクライアント。

ペイロードフィールド名は下記定数で一元管理する。
既存 Logic Apps のスキーマに合わせてここだけ変更すればよい。
"""
import logging

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

# Logic Apps が期待するフィールド名（スキーマ変更時はここを修正）
FIELD_MEDIA_TYPE = "media_type"
FIELD_ID         = "id"
FIELD_AUTHOR     = "author"
FIELD_TITLE      = "title"
FIELD_TEXT       = "text"
FIELD_PUBLISHED  = "published"
FIELD_POST_URL   = "url"

_SESSION = requests.Session()


def post_to_engage(
    webhook_url: str,
    tweet_id: str,
    author_username: str,
    text: str,
    published: str,
    post_url: str,
) -> bool:
    """
    Logic Apps Webhook にツイート情報を POST する。
    成功（HTTP 200 or 202）で True、失敗で False を返す。
    例外は送出しない（呼び出し元で処理を継続できるようにする）。
    """
    payload = {
        FIELD_MEDIA_TYPE: "twitter",
        FIELD_ID:         tweet_id,
        FIELD_AUTHOR:     f"@{author_username.lstrip('@')}",
        FIELD_TITLE:      "tweet",
        FIELD_TEXT:       text,
        FIELD_PUBLISHED:  published,
        FIELD_POST_URL:   post_url,
    }

    try:
        resp = _SESSION.post(webhook_url, json=payload, timeout=30)
        if resp.status_code in (200, 202):
            logger.info("Viva Engage に投稿: %s", post_url)
            return True
        logger.error(
            "Webhook が予期しないステータスを返しました: %d  url=%s  body=%s",
            resp.status_code, post_url, resp.text[:200],
        )
        return False
    except RequestException:
        logger.exception("Webhook への POST に失敗: %s", post_url)
        return False
