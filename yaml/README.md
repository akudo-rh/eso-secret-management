# yaml 構成

検証で使った manifest のひな形。手順は [docs/](../docs/) を参照。

| ファイル | リソース (スコープ) | 置く Namespace | 環境 | 手順 |
|---|---|---|---|---|
| `common/namespaces.yaml` | Namespace (クラスタ) | — | 共通 | 各手順書 §4 |
| `eso/aws/networkpolicy-allow-aws-egress.yaml` | NetworkPolicy (Namespace) | `external-secrets` (固定) | ROSA | [eso-rosa-verification.md](../docs/eso-rosa-verification.md) §4.4.1 |
| `eso/aws/serviceaccount.yaml` | ServiceAccount (Namespace) | `<TARGET_NAMESPACE>` | ROSA | 同上 §4.4.2 |
| `eso/aws/secretstore.yaml` | SecretStore (Namespace) | `<TARGET_NAMESPACE>` | ROSA | 同上 §4.4.2 |
| `eso/aws/externalsecret.yaml` | ExternalSecret (Namespace) | `<TARGET_NAMESPACE>` | ROSA | 同上 §4.5 |
| `aws-iam/*.json` | AWS IAM のポリシー (OpenShift のリソースではない) | — | ROSA | 同上 §4.3 |
| `eso/oci/01-oci-credentials_example.yaml` | Secret (Namespace)。書式の参考用 | `<TARGET_NAMESPACE>` | OCI | [eso-oci-vault-verification.md](../docs/eso-oci-vault-verification.md) §4.3 |
| `eso/oci/02-secretstore.yaml` | SecretStore (Namespace) | `<TARGET_NAMESPACE>` | OCI | 同上 §4.4 |
| `eso/oci/03-externalsecret.yaml` | ExternalSecret (Namespace) | `<TARGET_NAMESPACE>` | OCI | 同上 §4.5 |

- スコープ: 「クラスタ」は Namespace に属さないリソース、「Namespace」は Namespace の中に作るリソース。
- `ExternalSecretsConfig` (クラスタ) は手順書の中で直接作成するため、ファイルは置いていない。OpenShift 上の全リソースの一覧は [README 5.4](../README.md#54-openshift-上で作成するリソースとスコープ)。

## 置き換える値

`<...>` を環境の値に置き換えてから適用する (`oc apply -f <file>`)。OpenShift 上のリソース名は OCI 版と ROSA 版で共通のプレースホルダにしてあるので、同じ値で揃えられる。

**OpenShift 上のリソース名 (自分で決める)**

| プレースホルダ | 意味 | 検証で使った値 (OCI / ROSA) | 使うファイル |
|---|---|---|---|
| `<TARGET_NAMESPACE>` | ESO のリソースを置く Namespace | `eso-test` / `eso-test` | すべて |
| `<SECRET_STORE>` | SecretStore 名 | `oci-vault` / `aws-sm` | SecretStore、ExternalSecret |
| `<TARGET_SECRET>` | ExternalSecret 名 = ESO が作る Kubernetes Secret 名 | `demo-secret` / `demo-secret-aws` | ExternalSecret |
| `<SECRET_KEY>` | Kubernetes Secret 側のキー名 | `password` / `password` | ExternalSecret |
| `<SERVICE_ACCOUNT>` | ESO が認証に使う ServiceAccount (ROSA のみ) | — / `eso-aws-sa` | ServiceAccount、SecretStore、信頼ポリシー |
| `<OCI_CREDENTIALS_SECRET>` | API キーを入れる Secret (OCI のみ) | `oci-credentials` / — | 認証情報 Secret、SecretStore |

**クラウド側の値 (確認方法は各手順書の §2.2)**

| プレースホルダ | 意味 | 環境 |
|---|---|---|
| `<REGION>` | リージョン | 共通 |
| `<REMOTE_SECRET_NAME>` | 保管庫上のシークレット名 | 共通 |
| `<VAULT_OCID>` / `<TENANCY_OCID>` / `<USER_OCID>` | Vault / テナンシー / API キーのユーザーの OCID | OCI |
| `<ROLE_ARN>` / `<SECRET_ARN>` / `<ACCOUNT_ID>` / `<OIDC_HOST_PATH>` | IAM Role / シークレットの ARN、アカウント ID、OIDC ホストパス | ROSA |

一括で置き換える例:
```bash
sed -e 's/<TARGET_NAMESPACE>/eso-test/g' -e 's/<SECRET_STORE>/oci-vault/g' \
    -e 's/<TARGET_SECRET>/demo-secret/g' -e 's/<SECRET_KEY>/password/g' \
    yaml/eso/oci/03-externalsecret.yaml | oc apply -f -
```
