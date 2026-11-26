# OpenShift における Secret 管理と External Secrets Operator (ESO) のご提案

> 検証結果は ROSA (AWS Secrets Manager) / OpenShift on OCI (OCI Vault) の実機検証に基づく。
> 図は Mermaid 形式 (GitHub 上で図として表示される)。

## 1. Secret とは、なぜ管理が必要か

**Secret** = パスワード、API キー、証明書、トークンなど、漏えいすると被害が出る値。

```mermaid
flowchart LR
  subgraph NG["よくある状態 (課題)"]
    direction TB
    A1["ソースコード / Git に平文"]
    A2["CI の変数・設定ファイルに値が残る"]
    A3["ローテーションが手作業"]
    A4["誰が使ったか追えない"]
  end
  subgraph OK["目指す状態"]
    direction TB
    B1["値の正は専用の保管庫に 1 か所"]
    B2["アプリには必要な時だけ安全に渡す"]
    B3["Git には値を置かない"]
    B4["更新・権限を保管庫側で一元管理"]
  end
  NG ==> OK
```

## 2. OpenShift / Kubernetes での Secret 管理の方法

| 方法 | 概要 | 値の保管先 |
|---|---|---|
| ① 標準 Secret (手動作成) | `oc create secret` で直接登録。簡単だが保管と更新は人手 | クラスタ内 |
| ② Git で管理 (暗号化) | SealedSecrets / SOPS などで暗号化した Secret を Git に置く (GitOps 向け) | Git (暗号化) |
| ③ **External Secrets Operator (ESO)** | 外部の保管庫の値を、Operator が定期的に Kubernetes の Secret へ同期する | **外部の保管庫** |

```mermaid
flowchart LR
  subgraph M1["① 標準 Secret"]
    P1["担当者"] -- "oc create secret" --> S1["Secret"]
  end
  subgraph M2["② Git + 暗号化"]
    G2["Git (暗号化した Secret)"] -- "デプロイ時に復号" --> S2["Secret"]
  end
  subgraph M3["③ ESO"]
    V3["外部の保管庫"] -- "定期的に同期" --> S3["Secret"]
  end
```

## 3. ESO の仕組み

「どこへ・どう接続するか」(SecretStore) と「何を取得するか」(ExternalSecret) を別のリソースに分けて定義する。

```mermaid
flowchart TB
  V["外部の保管庫<br/>(AWS Secrets Manager / OCI Vault など)"]
  subgraph OCP["OpenShift クラスタ"]
    SS["SecretStore<br/>接続先と認証方法"]
    ES["ExternalSecret<br/>どの値を取得するか"]
    ESO["ESO (Operator)"]
    SEC["Kubernetes Secret<br/>(ESO が自動作成・更新)"]
    APP["アプリ (Pod)<br/>環境変数 / ボリュームで参照"]
    SS --> ESO
    ES --> ESO
    ESO -- "② 同期 (作成・更新)" --> SEC
    SEC -- "③ 従来どおり参照" --> APP
  end
  ESO -- "① 認証して取得 (定期的)" --> V
```

| リソース | 役割 | 作る人 |
|---|---|---|
| SecretStore | 保管庫への接続先と認証方法 | プラットフォームチーム |
| ExternalSecret | どの値を、どの名前の Secret にするか | アプリチーム |
| Kubernetes Secret | ESO が自動で作成・更新する (**手で作らない**) | (自動) |

- 保管庫側で値を更新すれば、`refreshInterval` ごとの再取得で自動的に Secret へ反映される (検証では 1 分周期)。
- アプリは通常の Secret を使う形のままで、**改修が不要**。
- Git に置くのは「参照の定義」だけで、値そのものは置かない。

## 4. 方式の比較 (メリット・デメリット)

| 観点 | ① 標準 Secret | ② Git + 暗号化 | ③ ESO |
|---|---|---|---|
| 値の保管先 | クラスタ内 | Git (暗号化) | **外部の保管庫** |
| 更新・ローテーション | 手動 | 再暗号化・再配布 | **自動 (定期同期)** |
| アプリ改修 | 不要 | 不要 | **不要** |
| Git に値を置かない | ○ (ただし手作業) | △ (暗号化して置く) | **○** |
| 権限・監査の一元管理 | × | △ | **○ (保管庫側)** |
| 保管庫停止時 | 影響なし | 影響なし | 同期済みの Secret で稼働継続 |
| クラスタ (etcd) に値が残る | 残る | 残る | 残る |
| 導入の手間 | 小 | 中 | 中 (Operator 導入と保管庫の準備) |
| 向く場面 | 小規模・検証 | GitOps を徹底したい | **標準の選択肢 (本提案)** |

**ESO のデメリット/留意点**
- クラスタ内 (etcd) に Secret が残る → etcd の暗号化と RBAC で担保する。
- ESO は強い権限で動くため、SecretStore を作れる人を絞る。
- 保管庫の準備 (作成・権限設定) が別途必要。

## 5. 導入手順 (実機検証済みの流れ)

詳細手順とエビデンスは下記リポジトリの docs を参照。

```mermaid
flowchart LR
  S1["1. cert-manager<br/>Operator 導入"] --> S2["2. ESO Operator<br/>導入"]
  S2 --> S3["3. ESO 本体の展開<br/>(ExternalSecretsConfig)"]
  S3 --> S4["4. 保管庫の準備と<br/>認証の設定"]
  S4 --> S5["5. SecretStore 作成<br/>→ 接続確認 (Valid)"]
  S5 --> S6["6. ExternalSecret 作成<br/>→ Secret が自動作成される"]
```

| 手順 | 共通 / 環境依存 |
|---|---|
| 1〜3 Operator と ESO 本体 | 共通 (ROSA / OCI とも同じ) |
| 4 保管庫の準備と認証 | **環境依存** (下表) |
| 5〜6 SecretStore / ExternalSecret | 接続先の記述だけ環境依存 |

### 5.1 ROSA 版 (保管庫: AWS Secrets Manager)
```mermaid
flowchart LR
  subgraph ROSA["ROSA クラスタ"]
    ESO["ESO"] -- "ServiceAccount の短期トークン" --> OIDC["クラスタの OIDC"]
  end
  OIDC -- "信頼" --> ROLE["AWS IAM Role<br/>(読み取り権限のみ)"]
  ESO -- "Role を引き受けて取得" --> SM["AWS Secrets Manager"]
  ROLE -. "許可" .-> SM
```
| 項目 | 内容 |
|---|---|
| 認証 | ROSA の STS (OIDC)。短期トークンで IAM Role を引き受ける。**アクセスキーをクラスタに置かない** |
| AWS 側の準備 | Secrets Manager にシークレット作成、IAM Role と読み取りポリシー、Role の信頼ポリシー |
| 注意点 | Role の信頼ポリシーの namespace / ServiceAccount 名が、クラスタ上の実際の名前と**完全一致**していること |
| 検証結果 | 同期 ✔ ([eso-rosa-verification.md](docs/eso-rosa-verification.md)) |

### 5.2 OCI 版 (保管庫: OCI Vault / OpenShift on OCI)
```mermaid
flowchart LR
  subgraph OCP["OpenShift on OCI"]
    ESO["ESO"]
    CRED["認証情報 Secret<br/>(API キー)"]
    CRED --> ESO
  end
  ESO -- "API キーで認証して取得" --> VAULT["OCI Vault"]
  POL["IAM ポリシー<br/>read secret-family"] -. "許可" .-> VAULT
```
| 項目 | 内容 |
|---|---|
| 認証 | User Principal (API キー)。キーを K8s Secret に保管して SecretStore から参照 (検証用) |
| OCI 側の準備 | Vault と Master Encryption Key、シークレット、ユーザー/グループ/IAM ポリシー |
| 注意点 | API キーの保管とローテーションが必要。本番では Instance Principal 等を検討。**OCI Vault は Red Hat のサポート対象外** (技術的な動作確認のみ) |
| 検証結果 | 同期 ✔、更新追従 ✔ (`refreshInterval` 1 分後に反映) ([eso-oci-vault-verification.md](docs/eso-oci-vault-verification.md)) |

### 5.3 環境による違い (要点)
| 観点 | ROSA + AWS | OpenShift on OCI + OCI Vault |
|---|---|---|
| 認証の安全性 | 高い (短期トークン、鍵の保管不要) | 検証は API キー (鍵管理が必要) |
| Red Hat のサポート | ESO の対象 (バージョン別に要確認) | **対象外** |
| 追加の準備 | IAM Role と信頼設定 | IAM ポリシー、API キー |

## 6. 役割分担 (案)

「正解はない」前提のたたき台。次の 2 チームで考える。

- **プラットフォームチーム**: クラスタの運用・CI/CD 基盤・クラウド (AWS / OCI) の管理を担う
- **アプリチーム**: アプリケーションの開発・運用を担う

**前提:** 現状、AWS Management Console / OCI の Web コンソールを操作する権限を持つのはプラットフォームチームのみ。将来はアプリチームにも一部の操作権限を渡す可能性がある。

### 6.1 全体像 (現状の案)

```mermaid
flowchart LR
  subgraph PF["プラットフォームチーム"]
    direction TB
    P1["保管庫の作成<br/>(AWS / OCI コンソール)"]
    P2["IAM ロール・ポリシーの設定"]
    P3["Secret の値の登録・更新"]
    P4["ESO の導入・運用"]
    P5["SecretStore の作成"]
    P6["manifest のデプロイ自動化<br/>(CI/CD)"]
  end
  subgraph APP["アプリチーム"]
    direction TB
    A1["必要な Secret の洗い出し<br/>(名前・用途・更新頻度)"]
    A2["ExternalSecret の定義<br/>(Git で管理)"]
    A3["アプリでの Secret の利用"]
  end
  A1 -- "依頼" --> P3
  P5 -- "SecretStore を提供" --> A2
  A2 -- "Git に push" --> P6
  P6 -- "デプロイ" --> A3
```

### 6.2 作業ごとの担当 (現状)

| 作業 | プラットフォーム | アプリ |
|---|---|---|
| 必要な Secret の洗い出し (名前・用途・更新頻度) | 確認 | **実施** |
| 保管庫の作成、IAM ロール・ポリシーの設定 (コンソール操作) | **実施** | |
| Secret の値の登録・更新 (ローテーション含む) | **実施** | 依頼 |
| ESO / Operator の導入・更新・監視 | **実施** | |
| SecretStore の作成 | **実施** | |
| ExternalSecret の作成 (Git 管理) | 確認 | **実施** |
| manifest のデプロイ自動化 (CI/CD) | **実施** | 利用 |
| アプリでの Secret の利用 | | **実施** |

### 6.3 将来の案: アプリチームにも権限を渡す場合
アプリチームがコンソールを操作できるようになったら、**自分のアプリ分の Secret に限って**値の登録・更新を行えるようにする (例: 保管庫のパス/コンパートメントをアプリごとに分け、その範囲だけ権限を付与)。

| 作業 | 現状 | 将来 |
|---|---|---|
| Secret の値の登録・更新 | プラットフォーム | **アプリ (自分の範囲のみ)** |
| 保管庫・IAM・SecretStore の設計と作成 | プラットフォーム | プラットフォーム (変更なし) |

### 6.4 相談したい論点
- Secret の値の受け渡し方法 (アプリチームから値を安全にプラットフォームへ渡す手段。チャットやメールに平文で書かない)
- SecretStore を Namespace (アプリ) ごとに分けるか、共通にするか → 最小権限を重視するなら分ける
- 環境 (開発/検証/本番) ごとの保管庫と権限の分け方
- アプリチームへの権限委譲の範囲とタイミング

## 7. 導入にあたっての留意点とリスク
| 項目 | 内容 |
|---|---|
| サポート範囲 | OCI Vault は Red Hat サポート対象外。AWS Secrets Manager 等はバージョン別に確認 |
| 認証方式 | 検証は簡易な方式。本番は ROSA は STS (標準)、OCI は Instance Principal / Workload Identity を検討 |
| etcd 上の Secret | ESO は etcd に Secret を残す → etcd 暗号化と RBAC を前提にする |
| 保管庫の可用性 | 同期済み Secret があれば稼働は継続。停止中は更新・新規 Secret が反映されない |
| 権限の設計 | ESO に渡す保管庫の権限は最小限にする |

## 8. 次のステップ (案)
1. 対象アプリ・Secret の棚卸し (種類、更新頻度、取得元)
2. 保管庫と認証方式の決定 (ROSA/AWS、OCI など)
3. 役割分担と運用ルールの合意 (§6)
4. 検証環境での PoC → 本番展開計画の策定

## 付録: 参照ドキュメント
- [eso-rosa-verification.md](docs/eso-rosa-verification.md) — ROSA 版の手順
- [eso-oci-vault-verification.md](docs/eso-oci-vault-verification.md) — OCI 版の手順と検証結果
