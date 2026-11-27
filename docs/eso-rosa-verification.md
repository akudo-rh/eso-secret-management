# ESO on ROSA 検証手順 (ROSA 単体)

ROSA クラスタに External Secrets Operator (ESO) を導入し、Secret が同期されることを確認する手順。
**ROSA と AWS だけで完結**する構成 (外部ストアは AWS Secrets Manager、認証は ROSA の STS / OIDC)。

- 検証に使う YAML → [yaml/eso/aws/](../yaml/eso/aws/)、[yaml/aws-iam/](../yaml/aws-iam/)
- YAML / JSON 内の `<...>` は、§2.2 で確認した自分の環境の値に置き換えてから使う。プレースホルダの一覧は [yaml/README.md](../yaml/README.md)。 作成する OpenShift リソースのスコープ (クラスタ / Namespace) は [README 5.4](../README.md#54-openshift-上で作成するリソースとスコープ) を参照。
- コマンドの `<TARGET_NAMESPACE>` などは YAML と同じプレースホルダ。本書の検証では `eso-test` を使った。

## 0. 検証開始前に確定させる項目 (ヒアリング・確認事項)

| 項目 | 確認先 | 影響 |
|---|---|---|
| ROSA の種別 (Classic / HCP)、OCP バージョン | `rosa describe cluster` | Operator の導入手順、STS の手順 |
| `cluster-admin` が使えるか | ROSA 管理者 | Operator 導入に必須。不可なら導入のみ依頼 |
| クライアントから API サーバーへ到達可能か (Private か) | ネットワーク担当 | Private の場合は踏み台 / VPN 経由 |
| クラスタから AWS API (STS / Secrets Manager) への egress | ネットワーク担当 | 不可の場合は許可依頼 (§2.4) |
| 利用可能な AWS 権限 (IAM Role / Policy、Secrets Manager の作成) | AWS 管理者 | §4.2・4.3 の作成に必要 |

## 1. 検証の概要

| 項目 | 内容 |
|---|---|
| 目的 | ROSA 上で ESO が動作し、外部ストアの値を K8s Secret に同期できることを確認する |
| クラスタ | ROSA (検証用クラスタ) |
| ESO | External Secrets Operator for Red Hat OpenShift 1.2.1 (チャネル `stable-v1.2`) |
| cert-manager | cert-manager Operator for Red Hat OpenShift 1.20.1 (チャネル `stable-v1.20`) |
| バックエンド | ① fake (ダミー。外部不要) → ② AWS Secrets Manager |
| 認証方式 (②) | ROSA の STS / OIDC (ServiceAccount トークン → `AssumeRoleWithWebIdentity`)。**アクセスキーは作らない** |
| 作業端末 | クライアント端末 (`oc` / `rosa` / `aws` CLI) |
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

### 進め方
**①で ESO 自体が動くことを確認してから、②で AWS 連携を行う。** ②が失敗した場合に「ESO の問題」か「AWS 側の問題」かを切り分けるため。

## 2. 事前準備と制約

### 公式ドキュメント
- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/security_and_compliance/index#external-secrets-operator-for-red-hat-openshift) (ROSA の OCP バージョンに合わせて参照)
- [ROSA のドキュメント](https://docs.redhat.com/en/documentation/red_hat_openshift_service_on_aws)

### Limitations
- Operator をアンインストールしても、external-secrets 用に作られたリソースは削除されない。手動で削除する。
- **cert-manager Operator は ESO より先にインストールしておく。** 後から入れた場合は `external-secrets-operator` の Pod を手動で再起動する。
- ROSA ではクラスタ管理の Namespace・リソースを変更できない場合がある。Operator 導入に `cluster-admin` 相当が必要。

### 2.1 クライアント端末のツール
| ツール | 用途 | 確認 |
|---|---|---|
| `oc` (ROSA の OCP バージョンに合わせる) | クラスタ操作 | `oc version --client` |
| `rosa` CLI | クラスタ情報の取得、管理者の作成 | `rosa version` |
| `aws` CLI v2 (任意) | IAM / Secrets Manager の操作 (AWS コンソールでも代替可) | `aws --version` |

### 2.2 必要な情報と確認方法
以降の手順で使う値を、先にすべて確認して手元に控える。以降の `<...>` はここで確認した値に置き換える。

| 情報 | 使う場所 | 確認方法 |
|---|---|---|
| `<CLUSTER_NAME>` | `rosa` コマンド | `rosa list clusters` / OCM コンソール (https://console.redhat.com/openshift) のクラスタ一覧 |
| ROSA 種別 (Classic / HCP)、OCP バージョン | 手順の分岐 | `rosa describe cluster -c <CLUSTER_NAME>` の `Type` / `OpenShift Version` / OCM コンソールのクラスタ詳細 |
| `<API_URL>` | `oc login` | `rosa describe cluster -c <CLUSTER_NAME>` の `API URL` |
| `<CONSOLE_URL>` | Operator のインストール (Web コンソール) | `rosa describe cluster -c <CLUSTER_NAME>` の `Console URL` |
| `<REGION>` (例: `ap-northeast-1`) | SecretStore の `region`、AWS コマンド、§2.4 の通信確認 | `rosa describe cluster -c <CLUSTER_NAME>` の `Region` / AWS コンソール右上のリージョン表示 |
| `<ACCOUNT_ID>` (12 桁) | IAM Role / Policy の ARN | `aws sts get-caller-identity --query Account --output text` / AWS コンソール右上のアカウントメニュー |
| `<OIDC_HOST_PATH>` (`https://` を除いた OIDC URL) | IAM Role の信頼ポリシー | `rosa describe cluster -c <CLUSTER_NAME>` の `OIDC Endpoint URL` から `https://` を除く。IAM コンソール →「ID プロバイダ」に同じ値のプロバイダがあること (`aws iam list-open-id-connect-providers`) |
| `<REMOTE_SECRET_NAME>` (例: `rosa-demo/password`) | ExternalSecret の `remoteRef.key` | 自分で決める。作成後は AWS コンソール → Secrets Manager の一覧 / `aws secretsmanager list-secrets --region <REGION>` |
| `<SECRET_ARN>` | 権限ポリシーの `Resource` | `aws secretsmanager describe-secret --region <REGION> --secret-id <REMOTE_SECRET_NAME> --query ARN --output text` / コンソールのシークレット詳細画面 (末尾にランダムな 6 文字が付く) |
| `<TARGET_NAMESPACE>` (本書は `eso-test`)、`<SERVICE_ACCOUNT>` (本書は `eso-aws-sa`) | 信頼ポリシーの `sub`、ServiceAccount、SecretStore | 自分で決める。**信頼ポリシーの `sub` (`system:serviceaccount:<TARGET_NAMESPACE>:<SERVICE_ACCOUNT>`) と、クラスタ上の実際の名前が 1 文字でも違うと認証に失敗する** (`oc get sa -n <TARGET_NAMESPACE>` で確認) |
| `<SECRET_STORE>` (本書は `aws-sm`)、`<TARGET_SECRET>` (本書は `demo-secret-aws`)、`<SECRET_KEY>` (本書は `password`) | SecretStore、ExternalSecret | 自分で決める ([yaml/README.md](../yaml/README.md)) |
| `<ROLE_ARN>` | ServiceAccount の注釈 | Role を管理者に作ってもらった場合は返ってきた ARN / `aws iam get-role --role-name <ROLE_NAME> --query Role.Arn --output text` / IAM コンソール →「ロール」の詳細 |

### 2.3 ROSA へのログイン
```bash
rosa login --token=<OCM token>              # トークンは https://console.redhat.com/openshift/token で取得
rosa describe cluster -c <CLUSTER_NAME>        # State=ready を確認
```
IdP が無く管理者が必要な場合 (検証用。終了後に削除):
```bash
rosa create admin -c <CLUSTER_NAME>            # 表示される oc login コマンドを実行 (反映まで数分)
oc login <API_URL> --username cluster-admin --password <表示されたPW>
```
確認:
```bash
oc whoami
oc get nodes
oc auth can-i '*' '*' --all-namespaces      # yes なら Operator 導入可
```
- Private クラスタの場合は VPN / 踏み台経由で API に到達できること。

### 2.4 クラスタからの外部通信 (②のみ)
Pod から AWS の STS / Secrets Manager に出られること。ROSA は通常 egress 可だが、制限環境では確認する。
```bash
oc run curl -n default --image=registry.access.redhat.com/ubi9/ubi-minimal --restart=Never --command -- sleep 300
oc wait -n default --for=condition=Ready pod/curl --timeout=120s
oc exec -n default curl -- curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 https://sts.<REGION>.amazonaws.com
oc exec -n default curl -- curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 https://secretsmanager.<REGION>.amazonaws.com
oc delete pod curl -n default
```
HTTP コードが返れば (302 / 400 / 403 / 404 でも) 到達 OK。タイムアウトは egress 制限。
※ ここで到達できても、**ESO の Pod からは到達できない場合がある** (§4.4)。

## 3. 導入手順と結果

### 3.1 cert-manager Operator

1. ROSA の Web コンソール (`<CONSOLE_URL>`) → OperatorHub から **cert-manager Operator for Red Hat OpenShift** をインストール
   - チャネル: `stable-v1.20` / バージョン: 1.20.1 / 更新の承認: 手動 / その他デフォルト
   - **ROSA (STS クラスタ) では「Role ARN」欄が表示される。** cert-manager が AWS (Route53 の DNS-01 など) を操作するための IAM Role を指定する欄。
     ESO の用途では cert-manager は webhook 用の内部証明書発行にしか使わず AWS 権限は不要なので、**本検証では実質使われない**。
     - 入れるべき値は ROSA の OIDC を信頼する **IAM Role の ARN** (`...:role/...`)。IAM ユーザー ARN など Role 以外の値を入れてもインストールと ESO の動作には影響しないが、cert-manager で Route53 / ACME を使うと失敗する。
     - 次回以降は、空欄にできるなら空欄、必須なら IAM Role の ARN を入力する。誤った値を入れた場合は Subscription の `ROLEARN` を修正する。
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

### 3.2 External Secrets Operator for Red Hat OpenShift
1. OperatorHub から **External Secrets Operator for Red Hat OpenShift** をインストール
   - チャネル: `stable-v1.2` / バージョン: 1.2.1 / 更新の承認: 手動 / その他デフォルト
2. InstallPlan を承認
3. インストール済み Operator で ESO が `Succeeded` になることを確認
4. 確認
   ```bash
   oc get po -n external-secrets-operator
   ```
   想定: `external-secrets-operator-controller-manager-...  1/1  Running`

### 3.3 ESO 本体 (operand) の展開
Operator は ESO 本体 (`external-secrets` Namespace の Pod 群) を管理するが、本体は `ExternalSecretsConfig` (name は `cluster`) を作成して初めて展開される。
**まず展開済みか確認し、何も無い場合のみ作成する。**
```bash
oc get po -n external-secrets
oc get externalsecretsconfigs.operator.openshift.io
```
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
※ apiVersion はバージョン依存。`oc explain externalsecretsconfig` で確認する。

## 4. 検証

```bash
oc new-project <TARGET_NAMESPACE>
```

### 4.1 ① fake ストアで ESO の動作を確認
外部ストア・認証を使わず、ESO の基本動作だけを確認する。

```bash
cat <<'EOF' | oc apply -f -
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  name: fake-store
  namespace: <TARGET_NAMESPACE>
spec:
  provider:
    fake:
      data:
        - key: /demo/password
          value: "P@ssw0rd-from-fake"
EOF

oc get secretstore -n <TARGET_NAMESPACE>
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
  namespace: <TARGET_NAMESPACE>
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

oc get externalsecret demo-secret-fake -n <TARGET_NAMESPACE>       # STATUS=SecretSynced / READY=True になるまで待つ
oc get secret demo-secret-fake -n <TARGET_NAMESPACE> -o jsonpath='{.data.password}' | base64 -d; echo
```
**`demo-secret-fake` (K8s Secret) は自分で作るものではなく、ExternalSecret を適用すると ESO が自動で作成する。**
そのため、ExternalSecret の適用前や、同期が完了する前に `oc get secret demo-secret-fake` を実行すると `NotFound` になる。
必ず先に ExternalSecret が `SecretSynced` / `Ready=True` になったことを確認してから Secret を取得する (待つ場合は下記)。
```bash
oc wait --for=condition=Ready externalsecret/demo-secret-fake -n <TARGET_NAMESPACE> --timeout=60s
```
Ready にならない / Secret ができない場合:
```bash
oc describe externalsecret demo-secret-fake -n <TARGET_NAMESPACE>    # Events / Conditions のエラーを確認
oc get secretstore fake-store -n <TARGET_NAMESPACE>                  # Valid / READY=True か
oc logs -n external-secrets deploy/external-secrets --tail=50
```
想定: `SecretSynced` / `Ready=True`、値は `P@ssw0rd-from-fake`。

合格条件: SecretStore が `Valid`、ExternalSecret が `SecretSynced`、値が一致。
※ `fake` provider が使えないバージョンの場合は §4.1 を飛ばして §4.2 へ進む。

### 4.2 ② AWS Secrets Manager にシークレットを作成
AWS CLI で作成する場合:
```bash
aws secretsmanager create-secret --region <REGION> \
  --name <REMOTE_SECRET_NAME> --secret-string 'P@ssw0rd-from-aws'

aws secretsmanager describe-secret --region <REGION> \
  --secret-id <REMOTE_SECRET_NAME> --query ARN --output text      # <SECRET_ARN> を控える
```

#### コンソールで作成する場合 (AWS CLI が使えない端末向け)
1. AWS マネジメントコンソールにサインイン → 右上のリージョンを **ROSA クラスタと同じリージョン** (`<REGION>`) に切り替える
2. **Secrets Manager** → 「新しいシークレットを保存する」
3. シークレットのタイプ: **その他のシークレットのタイプ**
4. 「キー/値」ではなく **「プレーンテキスト」タブ** を選び、既定の JSON を消して `P@ssw0rd-from-aws` だけを入力
   - ※ キー/値で作ると値が JSON (`{"password":"..."}`) になり、ESO が取得する値もその JSON 文字列になる。`remoteRef` に `property` 指定が必要になるため、今回はプレーンテキストにする
5. 暗号化キー: 既定の `aws/secretsmanager` のまま → 次へ
6. シークレット名: `<REMOTE_SECRET_NAME>` (例: `rosa-demo/password`) → 次へ (ローテーション: 無効のまま) → 保存
7. 作成後、シークレットの詳細画面で **シークレットの ARN** を控える (例: `arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:rosa-demo/password-AbCdEf`)
   - 権限ポリシー (§4.3) の `Resource` には **この完全な ARN** を使う

### 4.3 IAM Role の作成 (ROSA の OIDC を信頼)
ESO が使う ServiceAccount (`<TARGET_NAMESPACE>/<SERVICE_ACCOUNT>`) だけがこの Role を引き受けられるようにする。アクセスキーは作らない。

**① 権限ポリシー** (`rosa-eso-demo-read`): 対象シークレット 1 件の参照のみ ([yaml/aws-iam/read-secret-policy.json](../yaml/aws-iam/read-secret-policy.json))
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
      "Resource": "<SECRET_ARN>"
    }
  ]
}
```

**② 信頼ポリシー** (Role `rosa-eso-demo`): ROSA の OIDC と ServiceAccount を限定 ([yaml/aws-iam/trust-policy.json](../yaml/aws-iam/trust-policy.json))
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/<OIDC_HOST_PATH>"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "<OIDC_HOST_PATH>:sub": "system:serviceaccount:<TARGET_NAMESPACE>:<SERVICE_ACCOUNT>",
          "<OIDC_HOST_PATH>:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
```
- `<OIDC_HOST_PATH>` は `https://` なし・末尾 `/` なし。
- `sub` の Namespace 名と ServiceAccount 名は、§4.4 で作るものと**完全一致**させる。

AWS CLI で作成する場合 (①②を `read-secret.json` / `trust.json` に保存して):
```bash
aws iam create-policy --policy-name rosa-eso-demo-read --policy-document file://read-secret.json
aws iam create-role   --role-name   rosa-eso-demo      --assume-role-policy-document file://trust.json
aws iam attach-role-policy --role-name rosa-eso-demo \
  --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/rosa-eso-demo-read
```
コンソールの場合: IAM →「ポリシー」で ① を作成 →「ロール」→「ロールを作成」→ カスタム信頼ポリシーに ② を貼る → ① をアタッチ。

### 4.4 NetworkPolicy・ServiceAccount・SecretStore の作成と接続確認

#### 4.4.1 ESO から AWS への通信を許可する NetworkPolicy (必須)
Red Hat 版 ESO の Operator は、`external-secrets` Namespace に「全通信を拒否し、API サーバーと DNS だけ許可する」NetworkPolicy (`eso-sys-*`) を自動で作成する。そのままでは ESO の Pod は AWS (STS / Secrets Manager) に出られず、SecretStore が次のエラーで Invalid になる。

```
STS: AssumeRoleWithWebIdentity ... Post "https://sts.<REGION>.amazonaws.com/": dial tcp ...: i/o timeout
```
(§2.4 のように、別の Namespace の普通の Pod からは到達できても、ESO の Pod だけが届かない。)

`eso-sys-*` は Operator の管理対象なので編集せず、別名の NetworkPolicy を追加して 443 の外向き通信を許可する ([yaml/eso/aws/networkpolicy-allow-aws-egress.yaml](../yaml/eso/aws/networkpolicy-allow-aws-egress.yaml))。
```bash
oc get networkpolicy -n external-secrets          # eso-sys-* が存在することを確認
oc apply -f yaml/eso/aws/networkpolicy-allow-aws-egress.yaml
```
- 宛先は検証用に限定していない (AWS の IP は可変で、NetworkPolicy では FQDN を指定できないため)。本番では VPC エンドポイント経由にする、または宛先 FQDN で制限できる仕組みを検討する。

#### 4.4.2 ServiceAccount と SecretStore
[yaml/eso/aws/serviceaccount.yaml](../yaml/eso/aws/serviceaccount.yaml) と [yaml/eso/aws/secretstore.yaml](../yaml/eso/aws/secretstore.yaml) の `<...>` (`<TARGET_NAMESPACE>`、`<SERVICE_ACCOUNT>`、`<ROLE_ARN>`、`<SECRET_STORE>`、`<REGION>`) を置き換えて適用する。
```bash
oc apply -f yaml/eso/aws/serviceaccount.yaml
oc apply -f yaml/eso/aws/secretstore.yaml
oc get secretstore <SECRET_STORE> -n <TARGET_NAMESPACE>
```
想定:
```
NAME     AGE   STATUS   CAPABILITIES   READY
aws-sm   10s   Valid    ReadWrite      True
```
`Valid` にならない場合は §5 を参照。

### 4.5 ExternalSecret による同期の確認
[yaml/eso/aws/externalsecret.yaml](../yaml/eso/aws/externalsecret.yaml) の `<...>` (`<TARGET_SECRET>`、`<SECRET_KEY>`、`<REMOTE_SECRET_NAME>` など) を置き換えて適用する。本書の検証では `<TARGET_SECRET>` = `demo-secret-aws`、`<SECRET_KEY>` = `password`。
```bash
oc apply -f yaml/eso/aws/externalsecret.yaml
oc get externalsecret <TARGET_SECRET> -n <TARGET_NAMESPACE>
oc get secret <TARGET_SECRET> -n <TARGET_NAMESPACE> -o jsonpath='{.data.password}' | base64 -d; echo
```
期待する結果: `SecretSynced` / `Ready=True`、`P@ssw0rd-from-aws` が取得できる。

### 4.6 更新追従の確認
```bash
aws secretsmanager put-secret-value --region <REGION> \
  --secret-id <REMOTE_SECRET_NAME> --secret-string 'P@ssw0rd-from-aws-v2'
sleep 90
oc get externalsecret -n <TARGET_NAMESPACE>
oc get secret <TARGET_SECRET> -n <TARGET_NAMESPACE> -o jsonpath='{.data.password}' | base64 -d; echo
```
(コンソールの場合: Secrets Manager → シークレット詳細 →「シークレットの値を取得する」→「編集」で値を変更する。)
期待する結果: `refreshInterval` (1m) 後に `P@ssw0rd-from-aws-v2` へ更新される。

### 4.7 (任意) 権限を外した場合の挙動
ESO と AWS 側権限の関係を確認する。
```bash
aws iam detach-role-policy --role-name rosa-eso-demo \
  --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/rosa-eso-demo-read
# 次の refresh 後
oc get externalsecret <TARGET_SECRET> -n <TARGET_NAMESPACE>      # STATUS が失敗側 (SecretSyncedError) になる
oc get secret <TARGET_SECRET> -n <TARGET_NAMESPACE>              # 同期済みの Secret は残る
# 確認後に再 attach
aws iam attach-role-policy --role-name rosa-eso-demo \
  --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/rosa-eso-demo-read
```

## 5. トラブルシュート

| 症状 | 確認 |
|---|---|
| `oc login` できない | `rosa create admin` 直後は反映に数分。Private クラスタは VPN/踏み台経由か |
| Operator が `Succeeded` にならない | InstallPlan の承認、cert-manager を先に導入したか (2 章) |
| ESO の Pod が出ない | §3.3 の `ExternalSecretsConfig` (name: `cluster`) を作成したか |
| SecretStore が Invalid、イベントに `dial tcp ... i/o timeout` | **ESO の Pod から AWS に出られない。** `external-secrets` の NetworkPolicy (`eso-sys-deny-all-traffic` 等) が原因。§4.4.1 の NetworkPolicy を追加する。別 Namespace の Pod から curl が通っても、ESO の Pod は別扱い |
| SecretStore が Invalid、`AccessDenied` / `sts:AssumeRoleWithWebIdentity` エラー | **信頼ポリシーの `sub` (Namespace 名 / ServiceAccount 名) と、クラスタ上の実際の名前が一致しているか** 。`aud` が `sts.amazonaws.com` か、ServiceAccount の `eks.amazonaws.com/role-arn` 注釈が `<ROLE_ARN>` と一致しているか |
| 同上 (OIDC) | 信頼ポリシーの OIDC ホストパスが `rosa describe cluster` の OIDC URL (`https://` なし、末尾 `/` なし) と一致しているか。IAM の「ID プロバイダ」に存在するか |
| `AccessDeniedException` (Secrets Manager) | 権限ポリシーの Resource ARN、リージョン、シークレット名 |
| ESO が SA トークンを発行できない | ESO ログ。コントローラーの権限 (`serviceaccounts/token` の create) |
| 全般のタイムアウト | クラスタから AWS API への egress 制限 (§2.4) |
| ESO のログ | `oc logs -n external-secrets deploy/external-secrets` (名前空間は `oc get po -A \| grep external-secrets` で確認) |

## 6. 本番利用に向けた課題

| 観点 | 本書の構成 | 本番での論点 |
|---|---|---|
| 認証 | STS / OIDC (静的キーなし) | ROSA では標準的で推奨。Role は用途ごとに分割し、`sub` で ServiceAccount を限定する |
| スコープ | Namespace 単位の `SecretStore` | 共通利用は `ClusterSecretStore`。作成・参照できる人を絞る |
| 権限 | 1 シークレットのみ参照 | パスのプレフィックス単位で最小権限を設計する |
| 通信制御 | ESO の外向き 443 を全宛先に許可 (検証用) | VPC エンドポイント経由にする、または宛先を限定する |
| 監査 | CloudTrail には ESO 用 Role 名義で記録される | Pod 単位の追跡が必要なら別方式との比較が論点 |
| 可用性 | 同期済み Secret は残る (4.7) | AWS 側障害時の挙動を運用手順に反映 |
| サポート | AWS Secrets Manager は ESO の対象プロバイダー | Red Hat のサポート範囲は ESO のバージョン別に確認 |

## 7. 後片付け

```bash
oc delete project <TARGET_NAMESPACE>
oc delete networkpolicy allow-aws-egress-for-main-controller -n external-secrets

aws iam detach-role-policy --role-name rosa-eso-demo --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/rosa-eso-demo-read
aws iam delete-role   --role-name rosa-eso-demo
aws iam delete-policy --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/rosa-eso-demo-read
aws secretsmanager delete-secret --region <REGION> --secret-id <REMOTE_SECRET_NAME> --recovery-window-in-days 7
rosa delete admin -c <CLUSTER_NAME>      # 作成した場合
```

- ESO / cert-manager をアンインストールする場合は、2 章の Limitations のとおり残ったリソースを手動で削除する
