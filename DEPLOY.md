# SumaiBoard — Debian 12 + 宝塔部署手顺

対象は Debian 12 の VPS と宝塔面板です。公開通信は宝塔の Nginx を通し、アプリは `127.0.0.1:18080` のみにバインドします。MySQL は Compose 内部ネットワークだけで使用し、データは named volume `mysql-data` に保存します。紹介状PDFは公開されない専用 named volume `referral-documents` に保存します。初回起動時にアプリがテーブル作成と架空のデモデータ投入を自動で行うため、手動の seed コマンドは不要です。

## 0. 事前準備

ドメインの DNS A レコードを VPS の IP アドレスへ向け、宝塔のセキュリティ設定・VPS のファイアウォールで TCP 80/443 を許可します。MySQL の 3306 番ポートは開放しません。

**期待結果:** ドメインが VPS の IP に解決され、HTTP/HTTPS の受信が許可されていること。

## 1. Docker と Compose をインストール

VPS に SSH 接続し、Docker 公式 Debian リポジトリから Engine と Compose plugin をインストールします。

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
docker --version
docker compose version
systemctl is-enabled docker
```

**期待結果:** Docker と Docker Compose のバージョンが表示され、最後のコマンドが `enabled` を返すこと。Docker はサーバー起動時に自動起動します。

## 2. アプリをアップロードして展開

交付物の ZIP/TAR を VPS にアップロードします。以下は TAR.GZ の例です。ZIP の場合は `unzip` を使い、リポジトリのルート（`Dockerfile` と `docker-compose.yml` がある階層）を `/opt/sumaiboard` に展開してください。

```bash
sudo mkdir -p /opt/sumaiboard
sudo tar -xzf SumaiBoard-delivery.tar.gz -C /opt/sumaiboard --strip-components=1
cd /opt/sumaiboard
ls -la
```

**期待結果:** `Dockerfile`、`docker-compose.yml`、`.env.example`、`backend/`、`frontend/`、`DEPLOY.md` が表示されること。サーバーに Node.js や PDF ソフトをインストールする必要はありません。フロントエンド `dist` と PDF 生成用 WeasyPrint/Pango/HarfBuzz/Noto CJK フォントは Docker のビルド時にアプリイメージへ含まれます。

## 3. `.env` を設定

```bash
cd /opt/sumaiboard
cp .env.example .env
nano .env
chmod 600 .env
awk -F= '/^(DB_NAME|DB_USER|DB_PASSWORD|MYSQL_ROOT_PASSWORD|DEMO_MODE|PUBLIC_SAMPLE_MODE|SAMPLE_GUEST_EMPLOYEE_CODE|SAMPLE_RESET_TOKEN)=/ {print $1 " は設定済み"}' .env
stat -c '%a %n' .env
```

`DB_NAME` と `DB_USER` は英数字とアンダースコアで指定し、`DB_PASSWORD` と `MYSQL_ROOT_PASSWORD` はそれぞれ別の長いランダム値に置き換えます。例の値のまま運用しないでください。`openssl rand -hex 32` で値を生成できます。`.env` は Git に登録せず、バックアップもアクセス制限してください。

公開サンプル専用スタックの `.env` では `PUBLIC_SAMPLE_MODE=true`、`DEMO_MODE=true`、`SAMPLE_GUEST_EMPLOYEE_CODE=EX-01` を設定し、`SAMPLE_RESET_TOKEN` に専用のランダム値を設定します。公開サンプルには専用の DB 名・認証情報・ボリュームを使用します。運用環境ごとの分離条件は [公開サンプルのデプロイ境界](docs/sample-deployment-boundary.md) を参照してください。

**期待結果:** `.env` の8項目名が表示され、権限表示が `600 .env` になること。パスワード値は以後の画面出力やチャットへ貼り付けないでください。

## 4. Compose でビルド・起動

```bash
cd /opt/sumaiboard
sudo docker compose up -d --build
sudo docker compose ps
curl -fsS http://127.0.0.1:18080/api/health
```

初回は React のビルド、MySQL 初期化のため数分かかることがあります。Compose は MySQL の healthcheck が成功してからアプリを起動します。アプリ起動時に空の MySQL データベースへテーブルとデモデータを投入します。

PDF 一覧レポートは Settings のデータ入出力から作成できます。PDF レンダリング依存関係と日本語・中文フォントはアプリイメージにインストールされます。コンテナ再ビルド時の apt/pip 取得にはインターネット接続が必要です。

**期待結果:** `app` と `mysql` の両方が `Up` / `healthy` になり、health API が `{"status":"ok"}` を返すこと。MySQL コンテナに公開ポート設定がなく、ホストの 3306 番ポートでは接続できないこと。初回の状態確認は `sudo docker compose logs --tail=100 app mysql` で行えます。

両サービスには `restart: always` を設定しています。Docker デーモンとコンテナは VPS 再起動後に自動復帰します。

## 5. 宝塔でサイトとリバースプロキシを設定

1. 宝塔面板の「网站」→「添加站点」で対象ドメインのサイトを作成します。
2. 作成したサイトの「设置」→「反向代理」でプロキシを追加します。
3. 目标 URL を `http://127.0.0.1:18080` にし、送信先 Host を `$host` に設定します。宝塔の標準リバースプロキシが `X-Real-IP` / `X-Forwarded-For` を引き継ぐ設定も有効にします。
4. サイトの設定画面で Let's Encrypt 証明書を申請し、ドメインの検証成功後に HTTPS と「HTTP を HTTPS にリダイレクト」を有効にします。

**期待結果:** 宝塔のサイト設定でプロキシ先が `127.0.0.1:18080` と表示され、証明書の状態が有効になること。公開するのは宝塔経由の 80/443 のみです。

## 6. HTTPS の演示確認

```bash
curl -I https://demo.example.com
curl -fsS https://demo.example.com/api/health
```

`demo.example.com` は設定したドメインに置き換えます。

公開サンプルの受入基準は以下のとおりです。

1. HTTPS が成功し、health API が `{"status":"ok"}` を返すこと。ゲスト入場で管理業務ダッシュボードが開き、旧業務 API（例 `GET /api/households`、`GET /api/introductions`、`GET /api/entitlements`）が HTTP 410 を返すこと。
2. 初期データの主要件数が物件 20、部屋 200、賃貸借契約 180、請求 4,680、入金 2,192、消込 4,382、分別管理台帳 4,563、苦情 25、修繕 15、検収 6、オーナー精算 0 であること。検証操作を加える前に、サンプル DB で件数を記録します。
3. [面接デモ操作ガイド](docs/demo-guide.md) に沿って当月の `MC-01-101` の F03 精算を生成し、収納額 85,000 円（家賃 80,000 円と共益費 5,000 円）、管理料 4,250 円、修繕費 12,000 円、模擬送金予定額 68,750 円を確認すること。敷金 80,000 円は分別管理台帳で確認します。経理で提出し、別の模擬担当者で承認した後、経理で確定・模擬送金し、実績が 68,750 円になることを確認します。
4. `OW-A` と `OW-B` のオーナーマイページで、それぞれに紐づく物件、修繕履歴、確定済み精算だけが表示されること。`OW-A` では F03 の金額が管理画面と一致し、`OW-B` が同じ精算詳細 API に直接アクセスすると HTTP 403 を返すこと。オーナーによる管理 API の書き込みも HTTP 403 を返すこと。
5. 公開サンプル専用の配備先で `bash reset-sample.sh` を実行し、操作で作成したデータが消え、主要件数が初期値に戻ること。同じ対象月・契約で F03 を再生成すると同じ金額になることを、連続 2 回のリセット後に確認します。調整者はデプロイ時に運用 cron を毎日 04:00 JST に設定し、スケジュールと確認結果を受入記録に残します。

## 7. VPS 再起動・自動復帰・データ永続性の確認

自動リセットの時刻を避け、先にブラウザーで賃貸借契約やオーナー精算の状態を確認してから VPS を再起動します。

```bash
sudo reboot
```

SSH 再接続後:

```bash
sudo systemctl is-active docker
cd /opt/sumaiboard
sudo docker compose ps
curl -fsS https://demo.example.com/api/health
sudo docker volume ls | grep -E 'mysql-data|referral-documents'
```

**期待結果:** Docker が `active`、両コンテナが稼働中、HTTPS health API が `{"status":"ok"}` を返し、`mysql-data` と `referral-documents` volume が存在すること。ブラウザーでリロードして再起動前の操作データが残っていることを確認します。

## 運用上の注意

- アプリ・DB を停止する場合は `sudo docker compose down` を実行します。named volume は保持されます。
- `sudo docker compose down -v` は MySQL と紹介状ファイルの volume および保存データを削除するため実行しないでください。
- 更新版を配布した場合は、バックアップ後に `sudo docker compose up -d --build` で再ビルドします。
- DB パスワードを変更する際は `.env` と MySQL 側のユーザー認証を同時に更新してください。MySQL 初期化時に作成したユーザーのパスワードは、`.env` だけ変更しても既存 volume 上では自動変更されません。
- このプロトタイプは実顧客情報・本番業務データを扱う設計ではありません。外部公開前に OS、宝塔、Docker の更新と `.env`・DB バックアップを整備してください。

---

## V3.1.0 追補（G1-01 単一テナント製品地基）

- デプロイ形態は `DEPLOYMENT_PROFILE`（sample/product、必須）で決定します。現行の公開サンプルは `sample` として明示し、`DEPLOYMENT_ID`（サンプル用に生成）と `DEPLOYMENT_TENANT_ID=1` を `.env` に追加してください。product 形態では `DEMO_MODE` / `PUBLIC_SAMPLE_MODE` / `SAMPLE_RESET_TOKEN` が有効だと起動しません。
- 旧バージョンからの初回起動時、既存セッションは `auth.policy_epoch` の一回限りの繰り上げ（1→2）で全失効します。履歴サンプルDBを引き継ぐ場合のみ、初回起動に限り `LEGACY_MIGRATION_AUTHORIZED=sample` を設定し、移行完了後に削除してください。
- デプロイ/ロールバックは `scripts/deploy.sh` / `scripts/rollback.sh` を使用します（git archive による不変ソース、昇格前 pinned バックアップ、スナップショット、readiness + smoke）。product へのロールバックは `g1_01_secure=true` のリリースに限ります。
- バックアップは `scripts/backup.sh`（アプリ停止型・整合性方式A）、監視は `scripts/monitor.sh`（5分間隔 cron）を参照してください。詳細は docs/ 配下の運用手順が正本です。
