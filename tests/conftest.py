from unittest.mock import patch

# function_app はモジュールロード時に ensure_table_exists() を呼ぶため、
# conftest で先にパッチを当ててからインポートする（テスト実行順に依存しない）
with patch("state_manager.ensure_table_exists"):
    import function_app  # noqa: F401
