# 公開サンプルのデプロイ境界

公開サンプルは専用 MySQL 8 コンテナ、専用データボリューム、専用 DB 名を持つ独立 Compose スタックで運用する。実デモ（旧 Singapore 機）とは物理的に別デプロイとし、DB 接続先・ボリューム・認証情報・紹介状ストレージも分離する。サンプル側の `DB_NAME` は公開サンプル専用の名前を設定する。リポジトリのローカル検証用構成 `docker-compose.dev.yml` では専用の MySQL サービス、`enbai-dev-mysql` ボリューム、`enbai_dev` データベースを使用する。

公開サンプルの `POST /api/reset` は、既存のリセットトークンとロールの検査を経て、この専用 DB に対してのみ DROP と再 seed を実行する。アプリは接続設定の DB を操作するため、デプロイ時にサンプルの DB 接続設定とリセットジョブがこの独立スタックを指すことを確認する。通常モードはリセットを 403 で拒否し、実デモの既存 DEMO_MODE での動作は維持する。

公開サンプルの Uvicorn は **1 ワーカー、アプリは 1 コンテナ・1 インスタンス**で運用する。S04 のリセットと API リクエストの互斥・失敗時の遮断、および S08 の書込カウンタはプロセス内にある。ワーカーやインスタンスを増やすと S04 の互斥が成立しない。再試行後もリセットが失敗した場合は API を 503 で遮断し、再起動時は起動時 seed が成功した後にリクエストを受け付ける。

## 起動モードと模擬身份

| モード | フラグ | 旧業務・プラットフォームの初期化 | 賃貸サンプル・OW 口座の生成 |
| --- | --- | --- | --- |
| 通常 | 両方 false | 従来通り | なし |
| 旧実デモ | DEMO_MODE のみ true | 従来通り | なし |
| 公開サンプル | PUBLIC_SAMPLE_MODE が true | プラットフォーム口座・店舗などを従来通り初期化し、旧業務データを隔離 | あり |

通常・旧実デモ・公開サンプルのすべてで賃貸スキーマと移行を適用する。公開サンプルの起動時に完了マーカーがなければ、サンプルテナントの賃貸業務行を削除し、再投入する。完了マーカーは再投入の最後に記録する。

模擬身份一覧は有効で `employee_code` が NULL でない口座に限る。有効な模擬身份で切替でき、`employee_code` が NULL の口座を指定した模擬ログインは 403 を返す。

## 公開サンプルのルーティング

| 分類 | メソッドとパス |
| --- | --- |
| ヘルスチェック・シェル | GET `/api/health`、`/api/public-config`、`/api/bootstrap` |
| 認証 | POST `/api/auth/login`、`/api/auth/logout`、`/api/auth/demo-login`、`/api/auth/guest-login`。GET `/api/auth/demo-accounts` |
| リセット | POST `/api/reset` |
| 賃貸管理 | 全メソッド `/api/rental/` 配下。各ハンドラで既存の認証・権限を検査する |
| 通知 | GET `/api/notifications`。PUT `/api/notifications/{id}/read`、`/api/notifications/{id}/archive` |
| 予定 | GET・POST `/api/calendar`。PUT `/api/calendar/{id}`。作成・更新のタイトルは固定のサンプル文言に置換する。公開サンプルの一覧から旧業務タスク由来の予定を除外する |
| 掲示板・監査・設定・口座・稼働状況 | GET `/api/bulletin`、`/api/audit-events`、`/api/audit-events/{id}`、`/api/system-config`、`/api/accounts`、`/api/operations/status`。監査一覧・詳細は `security`・`seed`・`user` のみ |
| 個人設定 | PUT `/api/preferences`。初期表示の値は GET `/api/bootstrap` から取得する |
| その他 | `/api/` 配下で表にない組み合わせは 410。旧業務の dashboard、expenses、export-jobs、import-jobs、imports、households、introductions、referral-documents、referral-disputes、consents、construction、entitlements、data-corrections、activities、report、management、negotiation-queue を含む。`/api/month-closes` とその配下の全メソッド、パスワード変更・リセット申請・リセット、掲示板・口座・システム設定の書込、および上記以外の予定の書込も 410 |
