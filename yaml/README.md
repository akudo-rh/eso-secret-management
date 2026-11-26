# yaml 構成

検証で使った manifest のひな形。手順は [docs/](../docs/) を参照。

| パス | 内容 | 手順 |
|---|---|---|
| `common/` | 検証用 Namespace | — |
| `eso/oci/` | ESO × OCI Vault (認証情報の例、SecretStore、ExternalSecret) | [eso-oci-vault-verification.md](../docs/eso-oci-vault-verification.md) |
| `eso/aws/` | ESO × AWS Secrets Manager (ROSA / STS) | [eso-rosa-verification.md](../docs/eso-rosa-verification.md) |
| `aws-iam/` | IAM Role の信頼ポリシー / 権限ポリシーのひな形 | 同上 §4.3 |

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
