# x2engage 設計ドキュメント

X（旧Twitter）の指定アカウントの新規投稿を定期的に取得し、既存の Logic Apps Webhook 経由で Viva Engage に転送する Azure Functions アプリ。

---

## 技術スタック

| 項目 | 内容 |
|---|---|
| ランタイム | Python 3.11 |
| ホスティング | Azure Functions v2 / Flex Consumption |
| パッケージ管理 | uv |
| X API | v2（tweepy）/ Basic プラン |
| Viva Engage 投稿 | 既存 Logic Apps HTTP Webhook |
| シークレット管理 | Azure Key Vault（Managed Identity アクセス） |
| 状態管理 | Azure Table Storage |

---

## ファイル構成

```
x2engage/
├── function_app.py        # タイマートリガー・オーケストレーション
├── x_client.py            # X API v2 クライアント
├── engage_client.py       # Logic Apps Webhook クライアント
├── state_manager.py       # Table Storage による last_tweet_id 管理
├── keyvault_client.py     # Key Vault シークレット取得
├── pyproject.toml         # uv プロジェクト定義・依存ライブラリ
├── requirements.txt       # デプロイ用（uv export から生成）
├── host.json              # Functions ランタイム設定
├── local.settings.json    # ローカル開発用設定（コミット対象外）
├── .funcignore            # デプロイ除外設定
├── .gitignore             # Git 管理除外設定
└── .git/
```

---

## アーキテクチャ

```
Timer Trigger（毎時0分）
  │
  ├─ Key Vault からシークレット取得
  │    ├─ x-bearer-token
  │    └─ logic-app-webhook-url
  │
  └─ X_ACCOUNTS（環境変数）のアカウントをループ
       │
       ├─ Table Storage から last_tweet_id を取得
       ├─ X API v2: GET /2/users/:id/tweets（since_id 指定）
       │    └─ retweet・reply を除外、max_results=5
       │
       ├─ 新規ツイートを時系列順（古い順）に処理
       │    └─ Logic Apps Webhook に POST
       │         成功 → last_tweet_id を更新して次のツイートへ
       │         失敗 → そのアカウントの処理を中断（次回実行でリトライ）
       │
       └─ 次のアカウントへ（エラーは隔離）
```

---

## Logic Apps Webhook

### エンドポイント

`POST <logic-app-webhook-url>`（Key Vault から取得）

### リクエストボディ（JSON スキーマ準拠）

```json
{
  "media_type": "twitter",
  "id":         "1234567890",
  "author":     "@username",
  "title":      "tweet",
  "text":       "ツイート本文（全文）",
  "published":  "2024-01-01T12:00:00Z",
  "url":        "https://x.com/username/status/1234567890"
}
```

| フィールド | 値 | 備考 |
|---|---|---|
| `media_type` | `"twitter"` | 固定値 |
| `id` | ツイートID | 文字列 |
| `author` | `"@username"` | `@` プレフィックス付き |
| `title` | `"tweet"` | ダミー固定値 |
| `text` | ツイート本文 | 全文 |
| `published` | ISO 8601 文字列 | X API からそのまま渡す |
| `url` | `https://x.com/<user>/status/<id>` | 生成 |

---

## シークレット（Key Vault）

| シークレット名 | 内容 |
|---|---|
| `x-bearer-token` | X API Bearer Token |
| `logic-app-webhook-url` | Logic Apps HTTP トリガー URL |

ローカル開発時は `local.settings.json` の `X_BEARER_TOKEN` / `LOGIC_APP_WEBHOOK_URL` に直接値を設定することで Key Vault をバイパスできる。

> `local.settings.json` はシークレットを含むため **`.gitignore` に登録し絶対にコミットしない**こと。

---

## 環境変数（Application Settings）

| 名前 | 例 | 説明 |
|---|---|---|
| `KEYVAULT_URL` | `https://kv-x2engage.vault.azure.net/` | Key Vault URL |
| `TABLE_STORAGE_ACCOUNT_URL` | `https://stx2engage.table.core.windows.net/` | Table Storage URL |
| `STATE_TABLE_NAME` | `x2engagestate` | 状態管理テーブル名（省略時デフォルト） |
| `X_ACCOUNTS` | `account1,account2` | 監視対象アカウント（カンマ区切り、`@` 不要） |
| `TIMER_SCHEDULE` | `0 0 * * * *` | タイマー cron 式（毎時0分） |
| `AzureWebJobsStorage__accountName` | `stx2engage` | Functions ランタイム用ストレージ（Managed Identity 接続） |

---

## Table Storage スキーマ

テーブル名: `x2engagestate`（`STATE_TABLE_NAME` 環境変数で変更可）

| 属性 | 値 |
|---|---|
| `PartitionKey` | `"x2engage"`（固定） |
| `RowKey` | アカウント名（小文字） |
| `last_tweet_id` | 最後に処理したツイートID（文字列） |

---

## X API レート制限対策

- **Basic プラン**: 10,000 ツイート読み取り/月
- `since_id` 指定で新規ゼロなら読み取りカウント消費なし
- `max_results=5`（最小値）で保守的に運用
- `exclude=["retweets","replies"]` でオリジナル投稿のみ対象
- タイマー間隔: 毎時0分（`TIMER_SCHEDULE` で変更可能）

---

## Azure リソース要件

| リソース | 用途 |
|---|---|
| Function App (Flex Consumption, Python 3.11) | 本体 |
| Storage Account | Functions ランタイム + 状態テーブル（兼用可） |
| Key Vault | シークレット格納 |
| System-Assigned Managed Identity | Key Vault + Storage へのアクセス |

### RBAC ロール割り当て

| 対象 | リソース | ロール |
|---|---|---|
| Function App の Managed Identity | Key Vault | `Key Vault Secrets User` |
| Function App の Managed Identity | Storage Account（状態テーブル） | `Storage Table Data Contributor` |
| Function App の Managed Identity | Storage Account（WebJobs） | `Storage Blob Data Contributor` + `Storage Queue Data Contributor` |

---

## .gitignore の主な除外対象

```
local.settings.json   # シークレットを含む設定ファイル
.venv/                # uv 仮想環境
__pycache__/
*.pyc
.env                  # 万一 .env を使う場合の保険
```

---

## ローカル開発セットアップ

```bash
# 依存ライブラリのインストール
uv sync

# ローカル設定ファイルを編集（X_BEARER_TOKEN と LOGIC_APP_WEBHOOK_URL を直接入力）
# local.settings.json

# ローカル起動
uv run func start

# 手動トリガー（別ターミナルで）
curl -X POST http://localhost:7071/admin/functions/FetchAndPostTweets \
  -H "Content-Type: application/json" -d "{}"
```

---

## デプロイ

```bash
# requirements.txt を生成（Azure Functions ランタイムが使用）
uv export --no-hashes -o requirements.txt

# デプロイ
func azure functionapp publish <function-app-name>
```

---

## 検証方法

1. `func start` でローカル起動 → 手動トリガーで動作確認
2. Table Storage の `x2engagestate` テーブルで `last_tweet_id` が更新されることを確認
3. 2回目の実行で同じツイートが再投稿されないことを確認（冪等性）
4. Viva Engage のコミュニティ画面で投稿が届いていることを確認
5. 本番: Application Insights のライブログで各アカウントの処理結果を監視
