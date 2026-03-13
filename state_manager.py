"""
Azure Table Storage を使った処理済み tweet_id の永続管理。

テーブルスキーマ:
  PartitionKey : "x2engage"（固定）
  RowKey       : username（小文字）
  last_tweet_id: 最後に処理したツイートID（文字列）
"""
import logging
import os

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

PARTITION_KEY = "x2engage"


def _get_client() -> TableClient:
    return TableClient(
        endpoint=os.environ["TABLE_STORAGE_ACCOUNT_URL"],
        table_name=os.environ.get("STATE_TABLE_NAME", "x2engagestate"),
        credential=DefaultAzureCredential(),
    )


def ensure_table_exists() -> None:
    """起動時に一度だけ呼び出してテーブルを作成する（既存の場合はスキップ）。"""
    try:
        _get_client().create_table()
        logger.info("状態テーブルを作成しました")
    except Exception:
        pass  # テーブルが既に存在する場合は無視


def get_last_tweet_id(username: str) -> str | None:
    try:
        entity = _get_client().get_entity(
            partition_key=PARTITION_KEY,
            row_key=username.lower(),
        )
        return entity.get("last_tweet_id") or None
    except ResourceNotFoundError:
        return None
    except Exception:
        logger.exception("@%s の状態取得に失敗", username)
        return None


def set_last_tweet_id(username: str, tweet_id: str) -> None:
    entity = {
        "PartitionKey": PARTITION_KEY,
        "RowKey": username.lower(),
        "last_tweet_id": tweet_id,
    }
    try:
        _get_client().upsert_entity(entity=entity)
        logger.debug("@%s の last_tweet_id を %s に更新", username, tweet_id)
    except Exception:
        logger.exception("@%s の状態保存に失敗", username)
        raise
