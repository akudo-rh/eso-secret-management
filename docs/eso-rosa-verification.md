# ESO on ROSA 検証手順 (ROSA 単体)

ROSA クラスタに External Secrets Operator (ESO) を導入し、Secret が同期されることを確認する手順。
OCI Vault 検証 ([eso-oci-vault-verification.md](eso-oci-vault-verification.md)) と同じ章立てで、**ROSA と AWS だけで完結**させる (OCI は使わない)。

- 検証に使う YAML → [yaml/eso/aws/](../yaml/eso/aws/)、[yaml/aws-iam/](../yaml/aws-iam/)
- 実施記録 (結果・出力) は §1 の結果サマリと各節の「実測」欄に追記する。**現時点は手順のみで未実施。**

## 0. 検証開始前に確定させる項目 (ヒアリング・確認事項)

| 項目 | 確認先 | 影響 |
|---|---|---|
| ROSA の種別 (Classic / HCP)、OCP バージョン | `rosa describe cluster` | Operator の導入手順、STS の手順 |
| `cluster-admin` が使えるか | ROSA 管理者 | Operator 導入に必須。不可なら導入のみ依頼 |
| クライアントから API サーバーへ到達可能か (Private か) | ネットワーク担当 | Private の場合は踏み台 / VPN 経由 |
| クラスタから AWS API (STS / Secrets Manager) への egress | ネットワーク担当 | 不可の場合は許可依頼 (§2.3) |
| 利用可能な AWS 権限 (IAM Role / Policy、Secrets Manager の作成) | AWS 管理者 | 不可の場合は [request-to-admin-rosa.md](request-to-admin-rosa.md) の代替案で依頼 |

## 1. 検証の概要

| 項目 | 内容 |
|---|---|
| 目的 | ROSA 上で ESO が動作し、外部ストアの値を K8s Secret に同期できることを確認する |
| クラスタ | ROSA (検証用クラスタ。Classic / HCP は実施時に記入: ______) |
| ESO | External Secrets Operator for Red Hat OpenShift (OCI 検証と同じ `stable-v1.2` 系を想定) |
| cert-manager | cert-manager Operator for Red Hat OpenShift (OCI 検証と同じ `stable-v1.20` 系を想定) |
| バックエンド | ① fake (ダミー。外部不要) → ② AWS Secrets Manager |
| 認証方式 (②) | ROSA の STS / OIDC (ServiceAccount トークン → `AssumeRoleWithWebIdentity`)。**アクセスキーは作らない** |
| 作業端末 | 別クライアント端末 (`oc` / `rosa` / `aws` CLI) |
| 検証用 Namespace | `eso-test` |

### 構成

```
(① fake)   SecretStore 内のダミー値
(② AWS)    AWS Secrets Manager (secret: rosa-demo/password)
              ↑ STS (OIDC) で一時認証して取得
ESO (SecretStore / ExternalSecret)
              ↓ 同期
Kubernetes Secret (key: password)
```

### 結果サマリ (実施後に記入)

| 確認項目 | 結果 |
|---|---|
| ROSA へのログイン (`oc whoami`) | 未実施 |
| cert-manager Operator / ESO のインストール | 未実施 |
| ① fake: SecretStore `Valid` / ExternalSecret `SecretSynced` | 実施済み (リソース作成成功・イベントに問題なし。出力ログは未添付) |
| ② AWS: IAM Role / Secrets Manager の作成 | 未実施 |
| ② AWS: SecretStore が AWS に接続できる (`Valid`) | 未実施 |
| ② AWS: ExternalSecret による同期 | 未実施 |
| ② AWS: 値の更新が追従する | 未実施 |

### 進め方
**①で ESO 自体が動くことを確認してから、②で AWS 連携を行う。** ②が失敗した場合に「ESO の問題」か「AWS 側の問題」かを切り分けるため。

## 2. 事前準備と制約

### 公式ドキュメント
- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/security_and_compliance/index#external-secrets-operator-for-red-hat-openshift) (ROSA の OCP バージョンに合わせて参照)
- [ROSA のドキュメント](https://docs.redhat.com/en/documentation/red_hat_openshift_service_on_aws)

### Limitations (OCI 検証と同じ)
- Operator をアンインストールしても、external-secrets 用に作られたリソースは削除されない。手動で削除する。
- **cert-manager Operator は ESO より先にインストールしておく。** 後から入れた場合は `external-secrets-operator` の Pod を手動で再起動する。
- ROSA ではクラスタ管理の Namespace・リソースを変更できない場合がある。Operator 導入に `cluster-admin` 相当が必要。

### 2.1 クライアント端末の準備
| ツール | 用途 | 確認 |
|---|---|---|
| `oc` (ROSA の OCP バージョンに合わせる) | クラスタ操作 | `oc version --client` |
| `rosa` CLI | クラスタ情報取得、管理者作成 | `rosa version` |
| `aws` CLI v2 | IAM / Secrets Manager (②) | `aws --version` |
| `envsubst`, `jq` | manifest 変数展開、JSON 処理 | `envsubst --version` |

Windows の場合は WSL (Ubuntu) 上で実施するのが最も手戻りが少ない。

```bash
git clone <このリポジトリの URL> && cd <リポジトリ名>
cp env.sample env.local     # CLUSTER_NAME / AWS_REGION / AWS_ACCOUNT_ID を埋める
source env.local
```

### 2.2 ROSA へのログイン
```bash
rosa login --token=<OCM token>              # https://console.redhat.com/openshift/token
rosa describe cluster -c $CLUSTER_NAME      # State=ready、API URL、Console URL、OIDC Endpoint URL を控える
```
IdP が無く管理者が必要な場合 (検証用。終了後に削除):
```bash
rosa create admin -c $CLUSTER_NAME          # 表示される oc login コマンドを実行 (反映まで数分)
oc login <API URL> --username cluster-admin --password <表示されたPW>
```
確認:
```bash
oc whoami
oc get nodes
oc auth can-i '*' '*' --all-namespaces      # yes ならOperator導入可
```
- Private クラスタの場合は VPN / 踏み台経由で API に到達できること。
- 実測: `oc whoami` = ______ / ROSA 種別 = ______ / OCP バージョン = ______

### 2.3 クラスタからの外部通信 (②のみ)
ESO の Pod から AWS の STS / Secrets Manager に出られること。ROSA は通常 egress 可だが、制限環境では確認する。
```bash
oc run curl -n default --image=registry.access.redhat.com/ubi9/ubi-minimal --restart=Never --command -- sleep 300
oc wait -n default --for=condition=Ready pod/curl --timeout=120s
oc exec -n default curl -- curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 https://sts.${AWS_REGION}.amazonaws.com
oc exec -n default curl -- curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 https://secretsmanager.${AWS_REGION}.amazonaws.com
oc delete pod curl -n default
```
HTTP コードが返れば (400 / 403 / 404 でも) 到達 OK。タイムアウトは egress 制限。

## 3. 導入手順と結果

### 3.1 cert-manager Operator
OCI 検証と同じ手順。

1. ROSA の Web コンソール (`rosa describe cluster` の Console URL) → OperatorHub から **cert-manager Operator for Red Hat OpenShift** をインストール
   - チャネル: `stable-v1.20` / 更新の承認: 手動 / その他デフォルト
   - **ROSA (STS クラスタ) では「Role ARN」欄が表示される。** cert-manager が AWS (Route53 の DNS-01 など) を操作するための IAM Role を指定する欄。
     ESO の用途では cert-manager は webhook 用の内部証明書発行にしか使わず AWS 権限は不要なので、**本検証では実質使われない**。
     - 今回の実施: 管理者ではない自分の **IAM ユーザー ARN** (`arn:aws:iam::<アカウント>:user/...`) を入力してインストール → 全 Pod が Running で、ESO 検証には影響なし。
     - ただし本来は ROSA の OIDC を信頼する **IAM Role の ARN** (`...:role/...`) を入れる欄であり、ユーザー ARN は正しい値ではない (cert-manager で Route53 / ACME を使うと失敗する)。
     - 次回以降は、空欄にできるなら空欄、必須なら §4.3 で作る `rosa-eso-demo` などの Role ARN を入力する。誤値を直す場合は Subscription の `ROLEARN` を修正する。
       ```bash
       oc get subscription -n cert-manager-operator -o yaml | grep -i -B2 -A2 ROLEARN
       ```
2. InstallPlan を承認
3. 確認
   ```bash
   oc get po -n cert-manager-operator
   oc get po -n cert-manager
   ```
   想定: `cert-manager-operator-controller-manager-...  1/1  Running`

実測: ______

### 3.2 External Secrets Operator for Red Hat OpenShift
1. OperatorHub から **External Secrets Operator for Red Hat OpenShift** をインストール
   - チャネル: `stable-v1.2` / 更新の承認: 手動 / その他デフォルト
2. InstallPlan を承認
3. インストール済み Operator で ESO が `Succeeded` になることを確認
4. 確認
   ```bash
   oc get po -n external-secrets-operator
   ```
   想定: `external-secrets-operator-controller-manager-...  1/1  Running`

実測: ______

### 3.3 ESO 本体 (operand) の展開
Operator は ESO 本体 (`external-secrets` Namespace の Pod 群) を管理するが、本体は `ExternalSecretsConfig` (name は `cluster`) を作成して初めて展開される想定。
**まず展開済みか確認し、何も無い場合のみ作成する。**
```bash
oc get po -n external-secrets
oc get externalsecretsconfigs.operator.openshift.io
```
ROSA での実績: 上記は何も無かったため作成した (OCI 検証の記録には本手順の記載なし。OCI 側は要確認)。
```bash
cat <<'EOF' | oc apply -f -
apiVersion: operator.openshift.io/v1alpha1
kind: ExternalSecretsConfig
metadata:
  name: cluster
spec: {}
EOF

oc get po -n external-secrets
oc get crd | grep external-secrets.io
```
想定: `external-secrets` / `external-secrets-cert-controller` / `external-secrets-webhook` の Pod が `Running`、`externalsecrets.external-secrets.io` などの CRD が存在。
※ apiVersion はバージョン依存。`oc explain externalsecretsconfig` で確認する。OCI 検証で `ExternalSecretsConfig` を作成していた場合は同じ内容に合わせる。

実測: ______

## 4. 検証

```bash
oc new-project eso-test
```

### 4.1 ① fake ストアで ESO の動作を確認
外部ストア・認証を使わず、ESO の基本動作だけを確認する。

```bash
cat <<'EOF' | oc apply -f -
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  name: fake-store
  namespace: eso-test
spec:
  provider:
    fake:
      data:
        - key: /demo/password
          value: "P@ssw0rd-from-fake"
EOF
oc get secretstore -n eso-test
```
想定:
```
NAME         AGE   STATUS   CAPABILITIES   READY
fake-store   5s    Valid    ReadWrite      True
```
```bash
cat <<'EOF' | oc apply -f -
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: demo-secret-fake
  namespace: eso-test
spec:
  refreshInterval: 1m
  secretStoreRef:
    kind: SecretStore
    name: fake-store
  target:
    name: demo-secret-fake
    creationPolicy: Owner
  data:
    - secretKey: password
      remoteRef:
        key: /demo/password
EOF
oc get externalsecret demo-secret-fake -n eso-test       # STATUS=SecretSynced / READY=True になるまで待つ
oc get secret demo-secret-fake -n eso-test -o jsonpath='{.data.password}' | base64 -d; echo
```
**`demo-secret-fake` (K8s Secret) は自分で作るものではなく、ExternalSecret を適用すると ESO が自動で作成する。**
そのため、ExternalSecret の適用前や、同期が完了する前に `oc get secret demo-secret-fake` を実行すると `NotFound` になる。
必ず先に ExternalSecret が `SecretSynced` / `Ready=True` になったことを確認してから Secret を取得する (待つ場合は下記)。
```bash
oc wait --for=condition=Ready externalsecret/demo-secret-fake -n eso-test --timeout=60s
```
Ready にならない / Secret ができない場合:
```bash
oc describe externalsecret demo-secret-fake -n eso-test    # Events / Conditions のエラーを確認
oc get secretstore fake-store -n eso-test                  # Valid / READY=True か
oc logs -n external-secrets deploy/external-secrets --tail=50
```
想定: `SecretSynced` / `Ready=True`、値は `P@ssw0rd-from-fake`。

合格条件: SecretStore が `Valid`、ExternalSecret が `SecretSynced`、値が一致。
※ `fake` provider が使えないバージョンの場合は §4.1 を飛ばして §4.2 へ進む (Red Hat 版での対応は実機で確認)。

実測: SecretStore / ExternalSecret とも問題なく作成でき、イベントにもエラーなし。(初回に Secret 取得でエラーが出たのは、同期完了前に取得したためと推定。Secret の値 `P@ssw0rd-from-fake` の一致も確認済み。出力ログは未添付)

### 4.2 ② AWS Secrets Manager にシークレットを作成
```bash
aws sts get-caller-identity       # AWS_ACCOUNT_ID を env.local に反映

aws secretsmanager create-secret --region $AWS_REGION \
  --name $AWS_SECRET_NAME --secret-string 'P@ssw0rd-from-aws'

export AWS_SECRET_ARN=$(aws secretsmanager describe-secret --region $AWS_REGION \
  --secret-id $AWS_SECRET_NAME --query ARN --output text)
echo $AWS_SECRET_ARN              # env.local にも追記
```
(`AWS_SECRET_NAME` の既定は `rosa-demo/password`。)

#### コンソールで作成する場合 (AWS CLI が使えない端末向け)
1. AWS マネジメントコンソールにサインイン → 右上のリージョンを **ROSA クラスタと同じリージョン** (`AWS_REGION`) に切り替える
2. **Secrets Manager** → 「新しいシークレットを保存する」
3. シークレットのタイプ: **その他のシークレットのタイプ**
4. 「キー/値」ではなく **「プレーンテキスト」タブ** を選び、既定の JSON を消して `P@ssw0rd-from-aws` だけを入力
   - ※ キー/値で作ると値が JSON (`{"password":"..."}`) になり、ESO が取得する値もその JSON 文字列になる。`remoteRef` に `property` 指定が必要になるため、今回はプレーンテキストにする
5. 暗号化キー: 既定の `aws/secretsmanager` のまま → 次へ
6. シークレット名: `rosa-demo/password` → 次へ (ローテーション: 無効のまま) → 保存
7. 作成後、シークレットの詳細画面で **シークレットの ARN** を控える (末尾にランダムな 6 文字が付く。例: `arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:rosa-demo/password-AbCdEf`)
   - クライアントの `env.local` の `AWS_SECRET_ARN` と、アカウント ID (`AWS_ACCOUNT_ID`) を更新する
   - 権限ポリシー (§4.3) の `Resource` には **この完全な ARN** を使う

実測: ______

### 4.3 IAM Role の作成 (ROSA の OIDC を信頼)
ESO が使う ServiceAccount (`eso-test/eso-aws-sa`) だけがこの Role を引き受けられるようにする。アクセスキーは作らない。

```bash
# ROSA の OIDC Provider (クラスタ作成時に作成済み) を確認
export OIDC_URL=$(rosa describe cluster -c $CLUSTER_NAME -o json | jq -r '.aws.sts.oidc_endpoint_url')
export OIDC_HOST_PATH=${OIDC_URL#https://}      # env.local にも追記
aws iam list-open-id-connect-providers | grep "$OIDC_HOST_PATH"    # 1件ヒットすること

# 信頼ポリシーと権限ポリシーを生成
export TARGET_NS=eso-test TARGET_SA=eso-aws-sa
envsubst < yaml/aws-iam/trust-policy.tpl.json       > /tmp/eso-trust.json
envsubst < yaml/aws-iam/read-secret-policy.tpl.json > /tmp/read-secret.json

aws iam create-policy --policy-name rosa-eso-demo-read --policy-document file:///tmp/read-secret.json
aws iam create-role   --role-name   rosa-eso-demo      --assume-role-policy-document file:///tmp/eso-trust.json
aws iam attach-role-policy --role-name rosa-eso-demo \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/rosa-eso-demo-read

export ESO_ROLE_ARN=arn:aws:iam::${AWS_ACCOUNT_ID}:role/rosa-eso-demo     # env.local にも追記
```
- 信頼ポリシーの `sub` は `system:serviceaccount:eso-test:eso-aws-sa`、`aud` は `sts.amazonaws.com`。
- 権限は対象シークレット 1 件の `GetSecretValue` / `DescribeSecret` のみ (最小権限)。

実測: ______

### 4.4 ServiceAccount と SecretStore の作成・接続確認
```bash
envsubst < yaml/eso/aws/serviceaccount.yaml | oc apply -f -
envsubst < yaml/eso/aws/secretstore.yaml    | oc apply -f -
oc get secretstore aws-sm -n eso-test
```
想定:
```
NAME     AGE   STATUS   CAPABILITIES   READY
aws-sm   10s   Valid    ReadWrite      True
```
`Valid` にならない場合は §5 を参照 (最多原因は信頼ポリシーの OIDC ホストパス / `sub` の不一致)。

実測: ______

### 4.5 ExternalSecret による同期の確認
```bash
envsubst < yaml/eso/aws/externalsecret.yaml | oc apply -f -
oc get externalsecret demo-secret-aws -n eso-test
oc get secret demo-secret-aws -n eso-test -o jsonpath='{.data.password}' | base64 -d; echo
```
期待する結果: `SecretSynced` / `Ready=True`、`P@ssw0rd-from-aws` が取得できる。

実測: ______

### 4.6 更新追従の確認
```bash
aws secretsmanager put-secret-value --region $AWS_REGION \
  --secret-id $AWS_SECRET_NAME --secret-string 'P@ssw0rd-from-aws-v2'
sleep 90
oc get externalsecret -n eso-test
oc get secret demo-secret-aws -n eso-test -o jsonpath='{.data.password}' | base64 -d; echo
```
期待する結果: `refreshInterval` (1m) 後に `P@ssw0rd-from-aws-v2` へ更新される。

実測: ______

### 4.7 (任意) 権限を外した場合の挙動
ESO と AWS 側権限の関係を確認する。
```bash
aws iam detach-role-policy --role-name rosa-eso-demo \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/rosa-eso-demo-read
# 次の refresh 後
oc get externalsecret demo-secret-aws -n eso-test      # STATUS が失敗側 (SecretSyncedError) になる
oc get secret demo-secret-aws -n eso-test              # 同期済みの Secret は残る (README の「ストア停止時」と対応)
# 確認後に再 attach
aws iam attach-role-policy --role-name rosa-eso-demo \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/rosa-eso-demo-read
```

実測: ______

## 5. トラブルシュート

| 症状 | 確認 |
|---|---|
| `oc login` できない | `rosa create admin` 直後は反映に数分。Private クラスタは VPN/踏み台経由か |
| Operator が `Succeeded` にならない | InstallPlan の承認、cert-manager を先に導入したか (2 章) |
| ESO の Pod が出ない | §3.3 の `ExternalSecretsConfig` (name: `cluster`) を作成したか |
| SecretStore が Invalid (AWS) | `oc describe secretstore aws-sm -n eso-test`。SA の `role-arn` 注釈、信頼ポリシーの `sub` / `aud` |
| `AccessDenied` / `sts:AssumeRoleWithWebIdentity` エラー | 信頼ポリシーの OIDC ホストパスが `rosa describe cluster` の OIDC URL (`https://` なし、末尾 `/` なし) と一致しているか。OIDC Provider が IAM に存在するか |
| `AccessDeniedException` (Secrets Manager) | 権限ポリシーの Resource ARN、リージョン、シークレット名 (`AWS_SECRET_NAME`) |
| ESO が SA トークンを発行できない | ESO ログ。コントローラーの権限 (`serviceaccounts/token` の create) |
| タイムアウト | クラスタから AWS API への egress 制限 (2.3) |
| SecretStore が Invalid (STS 呼び出し失敗) | **AWS 側 Role の信頼ポリシーの `sub` (namespace / ServiceAccount 名) と、ROSA 上の実際の namespace / SA 名が一致しているか** (今回の実施では namespace 名の不一致が原因だった) |
| ESO のログ | `oc logs -n external-secrets deploy/external-secrets` (名前空間は `oc get po -A \| grep external-secrets` で確認) |
| envsubst で値が空 | `source env.local` 済みか。`echo $ESO_ROLE_ARN` などで確認 |

## 6. 本番利用に向けた課題

| 観点 | 今回の構成 | 本番での論点 |
|---|---|---|
| 認証 | STS / OIDC (静的キーなし) | ROSA では標準的で推奨。Role は用途ごとに分割し、`sub` で ServiceAccount を限定する |
| スコープ | Namespace 単位の `SecretStore` | 共通利用は `ClusterSecretStore`。作成・参照できる人を絞る (README の注意参照) |
| 権限 | 1 シークレットのみ参照 | パスのプレフィックス単位で最小権限を設計する |
| 監査 | CloudTrail には ESO 用 Role 名義で記録される | Pod 単位の追跡が必要なら SSCSI との比較が論点 |
| 可用性 | 同期済み Secret は残る (4.7) | AWS 側障害時の挙動を運用手順に反映 |
| サポート | AWS Secrets Manager は ESO の対象プロバイダー | Red Hat のサポート範囲は ESO のバージョン別に確認 |

## 7. 後片付け

```bash
oc delete project eso-test

aws iam detach-role-policy --role-name rosa-eso-demo --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/rosa-eso-demo-read
aws iam delete-role   --role-name rosa-eso-demo
aws iam delete-policy --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/rosa-eso-demo-read
aws secretsmanager delete-secret --region $AWS_REGION --secret-id $AWS_SECRET_NAME --recovery-window-in-days 7
rosa delete admin -c $CLUSTER_NAME      # 作成した場合
```

- ESO / cert-manager をアンインストールする場合は、2 章の Limitations のとおり残ったリソースを手動で削除する
- 一時ファイル `/tmp/eso-trust.json` `/tmp/read-secret.json` を削除する
