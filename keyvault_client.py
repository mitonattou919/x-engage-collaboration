"""
Key Vault シークレット取得モジュール。
DefaultAzureCredential を使用するため、ローカル（az login）・本番（Managed Identity）
いずれも同じコードで動作する。

ローカル開発時は env_fallback に指定した環境変数が設定されていれば
Key Vault アクセスをバイパスできる。
"""
import logging
import os
from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_client() -> SecretClient:
    vault_url = os.environ["KEYVAULT_URL"]
    return SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())


def get_secret(secret_name: str, env_fallback: str | None = None) -> str:
    """
    Key Vault からシークレットを取得する。
    env_fallback が指定されており、その環境変数に値が入っていれば
    Key Vault をバイパスしてその値を返す（ローカル開発用）。
    """
    if env_fallback:
        value = os.environ.get(env_fallback, "").strip()
        if value:
            logger.debug("env var '%s' を使用（Key Vault バイパス）", env_fallback)
            return value

    try:
        secret = _get_client().get_secret(secret_name)
        return secret.value
    except Exception:
        logger.exception("Key Vault からのシークレット取得に失敗: %s", secret_name)
        raise
