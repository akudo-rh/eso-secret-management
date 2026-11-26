# 依頼: ROSA 上の ESO 検証に必要な情報・権限

目的: ROSA 上に External Secrets Operator (ESO) を導入し、AWS Secrets Manager の値を Secret として同期する動作確認 ([eso-rosa-verification.md](eso-rosa-verification.md))。
検証後は削除予定の一時的な用途です。

## 0. 自分で用意済み / 自分で確認できるもの
- AWS アクセスキー ID / シークレットアクセスキー (クライアント端末の `aws` CLI 用。**クラスタや Git には置かない**)
- 確認コマンド: `aws sts get-caller-identity` (アカウント ID と権限の主体を確認)

## 1. 教えてほしい情報
| 項目 | 用途 | 備考 |
|---|---|---|
| ROSA クラスタ名 | `rosa describe cluster -c` | |
| ROSA 種別 (Classic / HCP)、OCP バージョン | 手順の分岐 | |
| API URL / Console URL | `oc login` | Private の場合は接続経路 (VPN/踏み台) も |
| クラスタのあるリージョン / AWS アカウント ID | IAM・Secrets Manager 作成先 | アクセスキーのアカウントと一致するか |
| ROSA 作成時の OIDC 設定 | IAM ロール信頼先 | `rosa describe cluster` の OIDC Endpoint URL。OCM に入れない場合は値だけ教えてもらう |

## 2. 付与してほしい権限

### 2-1. OpenShift / ROSA
| 権限 | 用途 |
|---|---|
| `cluster-admin` 相当 (または `rosa create admin` の実行許可) | Operator (cert-manager / ESO) の導入、`ExternalSecretsConfig` の作成 |
| OCM のログイン手段 (オフライントークン等) と、対象クラスタの参照権限 | `rosa login` / `rosa describe cluster` |

### 2-2. AWS (アクセスキーのユーザー/ロールに必要)
| 操作 | 権限 | 対象 |
|---|---|---|
| ESO 用 IAM Role/Policy の作成・削除 | `iam:CreatePolicy` `iam:DeletePolicy` `iam:CreateRole` `iam:DeleteRole` `iam:AttachRolePolicy` `iam:DetachRolePolicy` `iam:GetRole` | `rosa-eso-demo*` |
| OIDC Provider の確認 | `iam:ListOpenIDConnectProviders` `iam:GetOpenIDConnectProvider` | ROSA の OIDC Provider |
| 検証用シークレットの作成・更新・削除 | `secretsmanager:CreateSecret` `secretsmanager:PutSecretValue` `secretsmanager:DescribeSecret` `secretsmanager:DeleteSecret` `secretsmanager:GetSecretValue` | `rosa-demo/*` |

IAM の Role 作成が許可されない場合 (組織ポリシー/SCP/権限境界) は、**代替として管理者に以下を作成してもらう**:
- Role (名前例: `rosa-eso-demo`)
  - 信頼ポリシー: ROSA の OIDC Provider を Principal とし、`<OIDC_HOST_PATH>:sub` = `system:serviceaccount:<TARGET_NAMESPACE>:<SERVICE_ACCOUNT>` (検証では `eso-test` / `eso-aws-sa`)、`<OIDC_HOST_PATH>:aud` = `sts.amazonaws.com` の条件付き `sts:AssumeRoleWithWebIdentity`
  - 権限: 検証用シークレット 1 件への `secretsmanager:GetSecretValue` / `DescribeSecret`
  - (テンプレート: [yaml/aws-iam/](../yaml/aws-iam/))
- 検証用シークレット `rosa-demo/password` (値: `P@ssw0rd-from-aws` 検証用ダミー値)
- 回答してほしい情報: **Role ARN / シークレット ARN**

### 2-3. ネットワーク
- ROSA クラスタから `sts.<region>.amazonaws.com` / `secretsmanager.<region>.amazonaws.com` への HTTPS (egress) が許可されていること (制限環境の場合のみ)
- クライアント端末から ROSA の API サーバーへ到達できること

## 3. 後片付け
検証終了後、以下の削除/無効化をお願いします。
- ESO 用 Role / Policy、検証用シークレット (削除予約)
- `rosa create admin` で作成した管理者 (作成した場合)
- 発行したアクセスキーの無効化・削除 (一時利用の場合)

## 4. アクセスキーの取り扱い
- クライアント端末の `aws configure --profile rosa-eso` 等に保存し、リポジトリ・チャット・クラスタ上の Secret には置かない
- できれば有効期限付き (SSO / 一時クレデンシャル) への切替を管理者に相談する
- 検証後は無効化・ローテーションする
