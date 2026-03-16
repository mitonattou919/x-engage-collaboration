# x-engage-collaboration

X（旧Twitter）の指定アカウントの新規投稿を定期的に取得し、Viva Engage へ自動転送する Azure Functions アプリ。

## 概要

```
Timer Trigger（毎時0分）
  └─ X API v2 で新規ツイートを取得
  └─ Logic Apps Webhook 経由で Viva Engage に投稿
```

- **ランタイム**: Python 3.11 / Azure Functions v2 (Flex Consumption)
- **パッケージ管理**: [uv](https://docs.astral.sh/uv/)
- **シークレット管理**: Azure Key Vault（Managed Identity）
- **状態管理**: Azure Table Storage（重複投稿防止）

詳細は [DESIGN.md](./DESIGN.md) を参照。

---

## セットアップ

### 前提条件

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Azure Functions Core Tools v4](https://learn.microsoft.com/ja-jp/azure/azure-functions/functions-run-local)
- [Azure CLI](https://learn.microsoft.com/ja-jp/cli/azure/install-azure-cli)
- X Developer アカウント（Bearer Token 取得済み）

### ローカル開発

```bash
# 依存ライブラリのインストール（dev 依存含む）
uv sync --dev

# ローカル設定ファイルを作成
cp local.settings.json.example local.settings.json
# local.settings.json を編集して Bearer Token 等を入力

# ローカル起動
uv run func start
```

### テスト実行

```bash
uv run pytest
```

外部サービスへの接続は不要（すべてモック化済み）。

### 手動トリガー（動作確認）

```bash
curl -X POST http://localhost:7071/admin/functions/FetchAndPostTweets \
  -H "Content-Type: application/json" -d "{}"
```

---

## 環境変数

| 名前 | 説明 |
|---|---|
| `KEYVAULT_URL` | Key Vault の URL |
| `TABLE_STORAGE_ACCOUNT_URL` | Table Storage の URL |
| `STATE_TABLE_NAME` | 状態管理テーブル名（デフォルト: `x2engagestate`） |
| `X_ACCOUNTS` | 監視対象アカウント（カンマ区切り、`@` 不要） |
| `TIMER_SCHEDULE` | タイマー cron 式（デフォルト: `0 0 * * * *`） |

ローカル開発時は `X_BEARER_TOKEN` / `LOGIC_APP_WEBHOOK_URL` を `local.settings.json` に直接設定することで Key Vault をバイパスできる。

---

## デプロイ

```bash
# requirements.txt を生成（Azure Functions ランタイムが使用）
uv export --no-hashes -o requirements.txt

# Azure へデプロイ
func azure functionapp publish <function-app-name>
```

### 必要な Azure リソース

| リソース | 用途 |
|---|---|
| Function App (Flex Consumption) | 本体 |
| Storage Account | Functions ランタイム + 状態テーブル |
| Key Vault | `x-bearer-token` / `logic-app-webhook-url` の格納 |

### Key Vault シークレット名

| シークレット名 | 内容 |
|---|---|
| `x-bearer-token` | X API Bearer Token |
| `logic-app-webhook-url` | Logic Apps HTTP トリガー URL |

### Managed Identity の RBAC 設定

| ロール | 対象リソース |
|---|---|
| `Key Vault Secrets User` | Key Vault |
| `Storage Table Data Contributor` | Storage Account |
| `Storage Blob Data Contributor` | Storage Account |
| `Storage Queue Data Contributor` | Storage Account |
