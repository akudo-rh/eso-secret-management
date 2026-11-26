# ESO × OCI Vault 導入・動作確認手順 (OpenShift on OCI)

OpenShift on OCI 上のクラスタに External Secrets Operator (ESO) を導入し、OCI Vault のシークレットを Kubernetes Secret として同期できることを確認する手順。

- 検証に使った YAML → [yaml/eso/oci/](../yaml/eso/oci/)
- YAML とコマンドの `<...>` は §2.2 で確認した値に置き換える。OpenShift 上のリソース名のプレースホルダ (`<TARGET_NAMESPACE>` など) は [yaml/README.md](../yaml/README.md) を参照。 作成する OpenShift リソースのスコープ (クラスタ / Namespace) は [README 5.4](../README.md#54-openshift-上で作成するリソースとスコープ) を参照。本書の検証では `eso-test` / `oci-vault` / `demo-secret` / `oci-credentials` を使い、実行結果のログはその値のまま載せている。

## 0. 検証開始前に確定させる項目 (ヒアリング・確認事項)

| 項目 | 確認先 | 影響 |
|---|---|---|
| OpenShift クラスタの種別・OCP バージョン | クラスタ管理者 | Operator の導入手順 |
| `cluster-admin` が使えるか | クラスタ管理者 | Operator 導入に必須 |
| クラスタから OCI API (`*.oraclecloud.com`) への egress | ネットワーク担当 | 不可の場合は許可依頼 (§5 タイムアウト) |
| OCI Vault と Master Encryption Key の有無、作成権限 | OCI 管理者 | シークレット作成に必須 (§4.1)。不可なら作成を依頼 |
| OCI の IAM ポリシー (`read secret-family`、`read vaults`) | OCI 管理者 | 不足すると 401 / 404 や SecretStore が Valid にならない (§5) |
| API キーの登録可否 (ユーザーあたり 3 つまで) | OCI 管理者 | 認証方式 (§4.3)。不可なら登録許可を依頼 |

## 1. 検証の概要

| 項目 | 内容 |
|---|---|
| 目的 | ESO が OCI Vault をバックエンドとして動作するかを実機で確認する |
| クラスタ | OpenShift on OCI (検証用クラスタ) |
| ESO | External Secrets Operator for Red Hat OpenShift 1.2.1 (チャネル `stable-v1.2`) |
| cert-manager | cert-manager Operator for Red Hat OpenShift 1.20.1 (チャネル `stable-v1.20`) |
| OCI Region | ap-tokyo-1 |
| 認証方式 | User Principal (API キー) |
| 作業端末 | クライアント端末 (`oc` / `oci` CLI) |
| 検証用 Namespace | `eso-test` |

### 構成

```
OCI Vault (secret: eso-demo-password)
        ↑ API キーで認証して取得
ESO (SecretStore: oci-vault / ExternalSecret: demo-secret)
        ↓ 同期
Kubernetes Secret: demo-secret (key: password)
```

### Red Hat の動作確認対象について

OCI Vault は、Red Hat が ESO で動作確認している保管庫の一覧には含まれない。本検証で技術的に動作することを確認した (README 7 章)。

## 2. 事前準備と制約

### 公式ドキュメント
- [External Secrets Operator for Red Hat OpenShift (OCP 4.22)](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/security_and_compliance/index#external-secrets-operator-for-red-hat-openshift)
- [Installing (OCP 4.22)](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/security_and_compliance/index#external-secrets-operator-install)

### Limitations (13.3.1 より)
- Operator をアンインストールしても、external-secrets アプリケーション用に作られたリソースは削除されない。手動で削除する。
- `externalsecrets.operator.openshift.io` に cert-manager 設定を後から追加した場合、`external-secrets-cert-controller` の Deployment を手動で削除する (ESO が degraded になるのを防ぐため)。
- `BitwardenSecretManagerProvider` を有効にできるのは x86_64 / arm64 のクラスタのみ。
- **cert-manager Operator は ESO より先にインストールしておく。** 後から入れた場合は `external-secrets-operator` の Pod を手動で再起動する。

### 2.1 クライアント端末のツール
| ツール | 用途 | 確認 |
|---|---|---|
| `oc` (クラスタの OCP バージョンに合わせる) | クラスタ操作 | `oc version --client` |
| `oci` CLI (任意) | シークレットの作成・更新 (OCI コンソール / Cloud Shell でも代替可) | `oci --version` |

### 2.2 必要な情報と確認方法
以降の手順で使う値を、先にすべて確認して手元に控える。以降の `<...>` はここで確認した値に置き換える。
OCI コンソールは、画面右上のプロファイル (人型アイコン) から「テナンシ」「ユーザー設定」を開ける。

| 情報 | 使う場所 | 確認方法 |
|---|---|---|
| `<API_URL>` (OpenShift) | `oc login` | OpenShift Web コンソール右上のユーザー名 →「Copy login command」で表示される `--server=` の値 |
| `<REGION>` (例: `ap-tokyo-1`) | SecretStore の `region` | OCI コンソール右上のリージョン表示 |
| `<TENANCY_OCID>` | SecretStore の `auth.tenancy` | OCI コンソール → プロファイル →「テナンシ: ○○」→ 詳細の OCID の「コピー」 |
| `<USER_OCID>` | SecretStore の `auth.user` | OCI コンソール → プロファイル →「ユーザー設定」→ OCID の「コピー」 |
| `<FINGERPRINT>` | 認証情報 Secret (`<OCI_CREDENTIALS_SECRET>`) | 「ユーザー設定」→「API キー」→ 登録済みキーの一覧の「フィンガープリント」(API キー追加時の構成ファイルのプレビューにも表示される) |
| 秘密鍵 (PEM ファイル、`<PRIVATE_KEY_PATH>`) | 認証情報 Secret (`<OCI_CREDENTIALS_SECRET>`) | API キー追加時にダウンロードしたファイル。**再取得はできない**ので、無ければ API キーを作り直す |
| `<VAULT_OCID>` | SecretStore の `vault` | OCI コンソール → アイデンティティとセキュリティ → ボールト → 対象 Vault の詳細の OCID の「コピー」 |
| `<COMPARTMENT_OCID>` | シークレット作成 (§4.2) | OCI コンソール → アイデンティティとセキュリティ → コンパートメント → 対象の詳細の OCID |
| `<KEY_OCID>` | シークレット作成 (§4.2) | 対象 Vault の詳細 →「マスター暗号化キー」タブ → キーの OCID |
| `<TARGET_NAMESPACE>` (本書は `eso-test`)、`<SECRET_STORE>` (本書は `oci-vault`)、`<TARGET_SECRET>` (本書は `demo-secret`)、`<SECRET_KEY>` (本書は `password`)、`<OCI_CREDENTIALS_SECRET>` (本書は `oci-credentials`) | YAML、コマンド | 自分で決める ([yaml/README.md](../yaml/README.md)) |
| `<REMOTE_SECRET_NAME>` (本書は `eso-demo-password`) | ExternalSecret の `remoteRef.key` | 自分で決める。作成後は Vault の「シークレット」タブ / `oci vault secret list --compartment-id <COMPARTMENT_OCID>` |
| `<SECRET_OCID>` | 値の更新 (§4.6) | Vault の「シークレット」タブから対象を開き、詳細の OCID / 上記 `oci vault secret list` の `id` |

### 2.3 クラスタへのログイン
```bash
oc login --token=<トークン> --server=<API_URL>     # Web コンソールの「Copy login command」の内容
oc whoami
oc auth can-i '*' '*' --all-namespaces            # yes なら Operator 導入可
```

### 2.4 クラスタからの外部通信
Pod から OCI の API に出られること。
```bash
oc run curl -n default --image=registry.access.redhat.com/ubi9/ubi-minimal --restart=Never --command -- sleep 300
oc wait -n default --for=condition=Ready pod/curl --timeout=120s
oc exec -n default curl -- curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 https://vaults.<REGION>.oci.oraclecloud.com
oc exec -n default curl -- curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 https://secretsmgmt.<REGION>.oci.oraclecloud.com
oc exec -n default curl -- curl -sS -o /dev/null -w '%{http_code}\n' --max-time 10 https://auth.<REGION>.oraclecloud.com
oc delete pod curl -n default
```
HTTP コードが返れば (401 / 403 / 404 でも) 到達 OK。タイムアウトは egress 制限。ホスト名はサービス・リージョンにより異なるため、ESO のログ (`oc logs -n external-secrets deploy/external-secrets`) の接続先で最終確認する。
※ ここで到達できても、ESO の Pod からは到達できない場合がある (ROSA + AWS では実際に発生。[eso-rosa-verification.md](eso-rosa-verification.md) §4.4.1)。ESO の Pod だけタイムアウトする場合は、`external-secrets` Namespace の NetworkPolicy (`oc get networkpolicy -n external-secrets`) を確認する。
※ 本検証 (OCI) では、ROSA で必要だった外向き通信の NetworkPolicy を追加しなくても ESO から OCI Vault に接続できた。タイムアウトする場合は ROSA 版と同じ NetworkPolicy ([yaml/eso/aws/networkpolicy-allow-aws-egress.yaml](../yaml/eso/aws/networkpolicy-allow-aws-egress.yaml)) を追加する。

## 3. 導入手順と結果

### 3.1 cert-manager Operator

1. Web コンソールの OperatorHub からインストール
   - チャネル: `stable-v1.20` / バージョン: 1.20.1 / 更新の承認: 手動 / その他デフォルト
2. InstallPlan を Web コンソールで承認
3. 確認
   ```bash
   oc get po -n cert-manager-operator
   ```
   ```
   NAME                                                       READY   STATUS    RESTARTS   AGE
   cert-manager-operator-controller-manager-87646768b-57vxs   1/1     Running   0          79s
   ```

### 3.2 External Secrets Operator for Red Hat OpenShift

1. Web コンソールの OperatorHub からインストール
   - チャネル: `stable-v1.2` / バージョン: 1.2.1 / 更新の承認: 手動 / その他デフォルト
2. InstallPlan を承認
3. インストール済み Operator で ESO が `Succeeded` になることを確認
4. 確認
   ```bash
   oc get po -n external-secrets-operator
   ```
   ```
   NAME                                                            READY   STATUS    RESTARTS   AGE
   external-secrets-operator-controller-manager-548ff8d645-96ds4   1/1     Running   0          43m
   ```

### 3.3 ESO 本体 (operand) の展開

README 5 章の手順 3。Operator を入れただけでは ESO 本体 (`external-secrets` Namespace の Pod 群) は展開されず、`ExternalSecretsConfig` (name は `cluster`) を作成して初めて展開される。手順は ROSA 版と同じ ([eso-rosa-verification.md](eso-rosa-verification.md) §3.3)。**まず展開済みか確認し、何も無い場合のみ作成する。**

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
```
想定: `external-secrets` / `external-secrets-cert-controller` / `external-secrets-webhook` の Pod が `Running`。
※ apiVersion はバージョン依存。`oc explain externalsecretsconfig` で確認する。

## 4. OCI Vault 連携の検証

### 4.1 OCI Vault と Master Encryption Key の作成 (OCI コンソール)

OCI では**シークレット作成時に Master Encryption Key の指定が必須**。キー作成権限がない場合は、既存キーを使うか管理者に作成を依頼する (`use keys` と `manage secret-family` があればシークレット作成は可能)。

Vault: Identity & Security → Vault で作成 (例: `test-vault`)

OCI Vaultについて [https://docs.oracle.com/en-us/iaas/Content/KeyManagement/Concepts/keyoverview.htm]

Key: 作成した Vault の「マスター暗号化キー」タブで作成

| 項目 | 値 |
|---|---|
| 名前 | `eso-test-key` |
| アルゴリズム | AES |
| キーの長さ | 256 ビット |
| 保護モード | ソフトウェア |

### 4.2 シークレットの作成 (OCI Cloud Shell)

`oci` CLI が使える端末、OCI Cloud Shell、またはコンソールで作成する。

```bash
oci vault secret create-base64 \
  --compartment-id <COMPARTMENT_OCID> \
  --vault-id <VAULT_OCID> \
  --key-id <KEY_OCID> \
  --secret-name <REMOTE_SECRET_NAME> \
  --secret-content-content "$(echo -n 'P@ssw0rd-from-oci' | base64)"
```

`oci vault secret list --compartment-id <COMPARTMENT_OCID>` で、`<REMOTE_SECRET_NAME>` が `ACTIVE` であることを確認する (作成直後は `CREATING`)。

### 4.3 API キーの登録と認証情報 Secret の作成

**OCI コンソール:** 対象ユーザーの API keys → Add API key → Generate API key pair → 秘密鍵をダウンロードして Add。表示される構成プレビューから `user`、`fingerprint`、`tenancy`、`region` を控える。
(API キーは 1 ユーザーあたり 3 つまで)

**クライアント端末:** ダウンロードした秘密鍵を端末に置き、Secret を作成する。

```bash
oc new-project <TARGET_NAMESPACE>

oc create secret generic <OCI_CREDENTIALS_SECRET> -n <TARGET_NAMESPACE> \
  --from-file=privateKey=<PRIVATE_KEY_PATH> \
  --from-literal=fingerprint='<FINGERPRINT>'
```
```
secret/oci-credentials created
```

> 秘密鍵は Git に置かない。検証後は端末上の `.pem` を削除し、OCI 側の API キーも不要なら削除する。
> 本書は手順を簡単にするため、認証情報 Secret を SecretStore と同じ Namespace に置いている。本番で API キー方式を使う場合の置き場所とローテーションは README 5.2.2 を参照。
> [yaml/eso/oci/01-oci-credentials_example.yaml](../yaml/eso/oci/01-oci-credentials_example.yaml) は書式の参考用で、実際の値は入れない。

### 4.4 SecretStore の作成と接続確認

[yaml/eso/oci/02-secretstore.yaml](../yaml/eso/oci/02-secretstore.yaml) の `<...>` (`<TARGET_NAMESPACE>`、`<SECRET_STORE>`、`<REGION>`、`<VAULT_OCID>`、`<TENANCY_OCID>`、`<USER_OCID>`、`<OCI_CREDENTIALS_SECRET>`) を置き換えて適用する。

```bash
oc apply -f yaml/eso/oci/02-secretstore.yaml
oc get secretstore -n <TARGET_NAMESPACE>
```
```
NAME        AGE   STATUS   CAPABILITIES   READY
oci-vault   13s   Valid    ReadWrite      True
```

`status.conditions` に `reason: Valid` / `message: store validated` が出ており、OCI Vault への認証と接続が成功している。

```
~ $ oc get secretstore oci-vault -n eso-test -oyaml
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"external-secrets.io/v1","kind":"SecretStore","metadata":{"annotations":{},"name":"oci-vault","namespace":"eso-test"},"spec":{"provider":{"oracle":{"auth":{"secretRef":{"fingerprint":{"key":"fingerprint","name":"oci-credentials"},"privatekey":{"key":"privateKey","name":"oci-credentials"}},"tenancy":"ocid1.tenancy.oc1..<省略>","user":"ocid1.user.oc1..<省略>"},"region":"ap-tokyo-1","vault":"ocid1.vault.oc1..<省略>"}}}}
  creationTimestamp: "2026-10-21T04:27:16Z"
  generation: 1
  name: oci-vault
  namespace: eso-test
  resourceVersion: "10094176"
  uid: 67ca17ee-1d30-464a-b165-5cd2ac7bfbd9
spec:
  provider:
    oracle:
      auth:
        secretRef:
          fingerprint:
            key: fingerprint
            name: oci-credentials
          privatekey:
            key: privateKey
            name: oci-credentials
        tenancy: ocid1.tenancy.oc1..<省略>
        user: ocid1.user.oc1..<省略>
      region: ap-tokyo-1
      vault: ocid1.vault.oc1..<省略>
status:
  capabilities: ReadWrite
  conditions:
  - lastTransitionTime: "2026-10-21T04:27:16Z"
    message: store validated
    reason: Valid
    status: "True"
    type: Ready
~ $ 
```

> **注意:** SecretStore が存在しない状態で `oc get secretstore <SECRET_STORE>` を実行すると "not found" になる。`oc apply -f yaml/eso/oci/02-secretstore.yaml` を先に実行する必要がある。
> また、`oc get secretstore` には `-n <TARGET_NAMESPACE>` を付ける (付けないと現在のプロジェクトを参照する)。

### 4.5 ExternalSecret による同期の確認

[yaml/eso/oci/03-externalsecret.yaml](../yaml/eso/oci/03-externalsecret.yaml) の `<...>` (`<TARGET_SECRET>`、`<SECRET_KEY>`、`<REMOTE_SECRET_NAME>` など) を置き換えて適用する。

```bash
oc apply -f yaml/eso/oci/03-externalsecret.yaml
oc get externalsecret <TARGET_SECRET> -n <TARGET_NAMESPACE>
oc get secret <TARGET_SECRET> -n <TARGET_NAMESPACE> -o jsonpath='{.data.password}' | base64 -d; echo
```

期待する結果: ExternalSecret が `SecretSynced` / `Ready=True` になり、`P@ssw0rd-from-oci` が取得できる。

```
~ $ oc get externalsecret -n eso-test
NAME          STORETYPE     STORE       REFRESH INTERVAL   STATUS         READY   LAST SYNC
demo-secret   SecretStore   oci-vault   1m                 SecretSynced   True    55s
~ $

~ $ oc get secret demo-secret -n eso-test -o jsonpath='{.data.password}' | base64 -d; echo
P@ssw0rd-from-oci
~ $ 
```

### 4.6 更新追従の確認

OCI 側でシークレットの新バージョンを作成し、`refreshInterval` (1m) 後に K8s Secret が更新されることを確認する。

```bash
oci vault secret update-base64 --secret-id <SECRET_OCID> \
  --secret-content-content "$(echo -n 'changed-value' | base64)"
```

シークレットを更新する ( 'changed-value' を 'P@ssw0rd-from-oci-v2' にした場合）
```
<user>@cloudshell:~ (ap-tokyo-1)$ oci vault secret update-base64 --secret-id 'ocid1.vaultsecret.oc1..<省略>' --secret-content-content "$(echo -n 'P@ssw0rd-from-oci-v2' | base64)"
{
  "data": {
    "compartment-id": "ocid1.compartment.oc1..<省略>",
    "current-version-number": 2,
    "defined-tags": {
      "Oracle-Tags": {
        "CreatedBy": "default/<user>@example.com",
        "CreatedOn": "2026-10-21T03:53:09.185Z"
      }
    },
    "description": null,
    "freeform-tags": {},
    "id": "ocid1.vaultsecret.oc1..<省略>",
    "is-auto-generation-enabled": false,
    "is-replica": null,
    "key-id": "ocid1.key.oc1..<省略>",
    "last-rotation-time": null,
    "lifecycle-details": null,
    "lifecycle-state": "UPDATING",
    "metadata": null,
    "next-rotation-time": null,
    "replication-config": null,
    "rotation-config": null,
    "rotation-status": "NOT_ENABLED",
    "secret-generation-context": null,
    "secret-name": "eso-demo-password",
    "secret-rules": null,
    "source-region-information": null,
    "time-created": "2026-10-21T03:53:09.105000+00:00",
    "time-of-current-version-expiry": null,
    "time-of-deletion": null,
    "vault-id": "ocid1.vault.oc1..<省略>"
  },
  "etag": "bb5bfccd28fcd64a2cc96986aff0a28cb8d408526a55a66ded250eb459e5f23d"
}
<user>@cloudshell:~ (ap-tokyo-1)$ 
```

ocコマンドでsecretの更新を確認する
```
~ $ oc get externalsecret -n eso-test
NAME          STORETYPE     STORE       REFRESH INTERVAL   STATUS         READY   LAST SYNC
demo-secret   SecretStore   oci-vault   1m                 SecretSynced   True    15s
~ $ 
~ $ oc get secret demo-secret -n eso-test -o jsonpath='{.data.password}' | base64 -d; echo
P@ssw0rd-from-oci-v2
~ $ 
```

## 5. トラブルシュート

| 症状 | 確認 |
|---|---|
| SecretStore が Invalid | `oc describe secretstore <SECRET_STORE> -n <TARGET_NAMESPACE>`。fingerprint・user・tenancy OCID・秘密鍵の組み合わせを確認 |
| 401 / 404 | IAM ポリシー不足 (値の取得に `read secret-bundles`。`read secret-family` に含まれる)、Vault OCID / Region の誤り、シークレット名の誤り |
| SecretStore が Valid にならない (状態が Unknown) | ESO は接続確認で Vault の情報を読む。`read vaults` が無いと確認できず Valid にならない (値の取得はできる) |
| タイムアウト | クライアント端末やクラスタから OCI API への egress 制限 |
| ESO のログ | `oc logs -n external-secrets deploy/external-secrets` (名前空間は環境により異なるため `oc get po -A \| grep external-secrets` で確認) |
| cert-manager 関連で ESO が不調 | 2 章の Limitations を参照。ESO の Operator Pod を再起動する |

## 6. 本番利用に向けた課題

README 5.2・5.3 のとおり、OpenShift on OCI では認証方式が論点になる。

| 方式 | 位置づけ (README) | 特徴 | 課題 |
|---|---|---|---|
| User Principal (API キー) ← 本書の構成 | 検証で使用。当面の運用候補 (5.2.2) | 手軽 | 秘密鍵の保管とローテーションが必要。管理案は README 5.2.2 |
| Workload Identity | 本番候補 (5.2.1)。検証予定 | ServiceAccount 単位で権限を分けられる (AWS の STS と同じ考え方) | ESO の OCI 用の Workload 設定は OKE 向けの仕組みを前提にしているため、OpenShift で使えるかを検証する |
| Instance Principal | Workload Identity が使えない場合の代替 (8 章 No. 9) | 鍵の管理が不要 | 権限がノード単位になる。対策とあわせて検討 |

加えて、キー・IAM の管理者を責任分界で明確にする点も整理が必要 (README 6 章)。今後の検討事項の一覧は README 8 章。

## 7. 後片付け

```bash
oc delete project <TARGET_NAMESPACE>
```

- OCI: シークレット (削除予約、最短 1 日)・Key (削除予約、最短 7 日)・不要な API キーを削除する
- クライアント端末: 秘密鍵 (`.pem`) を削除する
- ESO / cert-manager をアンインストールする場合は、2 章の Limitations のとおり残ったリソースを手動で削除する
