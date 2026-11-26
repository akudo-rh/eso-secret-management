# クライアント準備と ROSA 事前確認

## 0-1. 必要ツール
| ツール | 用途 | 確認 |
|---|---|---|
| `git` | リポジトリ取得 | `git --version` |
| `oc` (ROSA の OCP バージョンに合わせる) | クラスタ操作 | `oc version --client` |
| `rosa` CLI | ROSA 情報取得/管理者作成 | `rosa version` |
| `aws` CLI v2 | AWS 連携の IAM/Secrets Manager | `aws --version` |
| `envsubst` (gettext) / `jq` | manifest 変数展開/JSON 処理 | `envsubst --version` |
| `oci` CLI (任意) | OCI 連携の Secret 作成/更新 | `oci --version` |

Windows の場合は WSL (Ubuntu) 上で全て実施するのが最も手戻りが少ない。

## 0-2. リポジトリ取得と環境変数
```bash
git clone <このリポジトリの URL> && cd <リポジトリ名>
cp env.sample env.local && vi env.local && source env.local
```

## 0-3. ROSA クラスタ情報の取得
```bash
rosa login --token=<OCM token>           # https://console.redhat.com/openshift/token
rosa describe cluster -c $CLUSTER_NAME   # Classic/HCP、API URL、OIDC Endpoint URL、State=ready を確認
```
記録する項目 (環境情報): 種別、OCP バージョン、リージョン、API URL、OIDC Endpoint URL。

## 0-4. oc ログイン
IdP が未設定なら cluster-admin を発行 (検証用。終了後に削除):
```bash
rosa create admin -c $CLUSTER_NAME       # 表示された oc login コマンドを実行 (反映に数分)
oc login <API URL> --username cluster-admin --password <表示されたPW>
oc whoami && oc get nodes && oc auth can-i '*' '*' --all-namespaces
```
- Private クラスタの場合は VPN/踏み台経由で API に到達できること。
- 既存 IdP を使う場合は `oc login --web` 等。`cluster-admin` 権限があるかを `oc auth can-i` で確認。

## 0-5. egress 確認 (手戻り最大要因)
クラスタ内から外部 API に出られるかを **先に** 確認する。
```bash
oc new-project egress-check
oc run curl --image=registry.access.redhat.com/ubi9/ubi-minimal --restart=Never --command -- sleep 600
oc wait --for=condition=Ready pod/curl --timeout=120s
# OCI Vault (OCI 連携)
oc exec curl -- curl -sS -o /dev/null -w '%{http_code}\n' https://vaults.${OCI_REGION}.oci.oraclecloud.com --max-time 10
oc exec curl -- curl -sS -o /dev/null -w '%{http_code}\n' https://secretsmgmt.${OCI_REGION}.oci.oraclecloud.com --max-time 10
oc exec curl -- curl -sS -o /dev/null -w '%{http_code}\n' https://auth.${OCI_REGION}.oraclecloud.com --max-time 10
# AWS (AWS 連携)
oc exec curl -- curl -sS -o /dev/null -w '%{http_code}\n' https://secretsmanager.${AWS_REGION}.amazonaws.com --max-time 10
oc exec curl -- curl -sS -o /dev/null -w '%{http_code}\n' https://sts.${AWS_REGION}.amazonaws.com --max-time 10
oc delete project egress-check
```
HTTP コードが返れば (401/403/404 でも) 到達 OK。タイムアウトなら egress 制限 → ネットワーク担当に許可依頼。
※ OCI エンドポイントのホスト名はサービス/リージョンにより異なる。ESO ログ (`oc logs -n external-secrets deploy/external-secrets`) の接続先で最終確認。

## 0-6. AWS 側の共通準備 (AWS 連携用)
```bash
aws sts get-caller-identity                       # AWS_ACCOUNT_ID を env.local に反映
export OIDC_URL=$(rosa describe cluster -c $CLUSTER_NAME -o json | jq -r '.aws.sts.oidc_endpoint_url')
export OIDC_HOST_PATH=${OIDC_URL#https://}        # env.local にも追記
aws iam list-open-id-connect-providers | grep "$OIDC_HOST_PATH"   # ROSA 作成済み OIDC Provider が存在すること

aws secretsmanager create-secret --region $AWS_REGION --name $AWS_SECRET_NAME \
  --secret-string 'P@ssw0rd-from-aws'
export AWS_SECRET_ARN=$(aws secretsmanager describe-secret --region $AWS_REGION --secret-id $AWS_SECRET_NAME --query ARN --output text)
```
(`env.local` の `OIDC_HOST_PATH` / `AWS_SECRET_ARN` を更新)

## 合格条件
- [ ] `oc whoami` 成功、cluster-admin 相当
- [ ] §0-5 で必要な宛先すべて到達可
- [ ] OIDC Provider と Secrets Manager のシークレットを確認済み
