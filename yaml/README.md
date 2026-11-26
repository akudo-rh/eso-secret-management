# yaml 構成

検証で使った manifest。手順は [docs/](../docs/) を参照。

| パス | 内容 | 手順 |
|---|---|---|
| `common/` | 検証用 Namespace | — |
| `eso/oci/` | ESO × OCI Vault (認証情報の例、SecretStore、ExternalSecret) | [eso-oci-vault-verification.md](../docs/eso-oci-vault-verification.md) |
| `eso/aws/` | ESO × AWS Secrets Manager (ROSA / STS) | [eso-rosa-verification.md](../docs/eso-rosa-verification.md) |
| `aws-iam/` | IAM Role の信頼ポリシー / 権限ポリシーのテンプレート | 同上 §4.3 |

`${VAR}` を含むファイルは `envsubst < <file> | oc apply -f -` で適用する (変数は `env.sample` 参照)。
