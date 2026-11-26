#!/usr/bin/env python3
"""README 用の図 (SVG) を共通デザインで生成する。
使い方: python3 docs/images/gen_diagrams.py docs/images

方針
- 図は絵だけにする (タイトル・説明文は README 本文に書く)
- 文字サイズは 4 段階に揃える。表示幅 900px (座標 1200 の 0.75 倍) で
  主要な文字が本文とほぼ同じ大きさ (約 15px) になる
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

FONT = "'Noto Sans JP','Noto Sans CJK JP','Hiragino Sans','Hiragino Kaku Gothic ProN','Yu Gothic UI','Meiryo',sans-serif"
RED, TEAL, TEAL_D, TEAL_L = "#d10000", "#37a3a3", "#1f7a7a", "#e7f4f4"
GRAY_H, GRAY_L, GRAY_S, TXT, TXT2, APP_S = "#b3b3b3", "#f2f2f2", "#c8c8c8", "#333333", "#555555", "#4d4d4d"
SCALE = 0.75                       # 座標 → 表示 (幅 1200 → 900px)
F_HEAD, F_MAIN, F_SUB, F_LABEL = 21, 20, 17, 17   # 見出し / 主要な文字 / 補足 / ラベル

STY = {  # fill, stroke, width, main color, bold, dash
    "plain": ("#ffffff", GRAY_S, 1.5, TXT, False, None),
    "pf": (TEAL_L, TEAL, 2, TEAL_D, True, None),
    "pfstrong": (TEAL, TEAL, 2, "#ffffff", True, None),
    "app": ("#ffffff", APP_S, 2, TXT, True, None),
    "auto": ("#ffffff", "#8a8a8a", 1.5, TXT2, False, "6 4"),
    "vault": (TEAL_L, TEAL, 3, TEAL_D, True, None),
    "warn": ("#ffffff", RED, 3, RED, True, None),
}
LEG_TEAM = [("pf", "プラットフォームチームが管理"), ("app", "アプリチームが管理"), ("auto", "自動で作成")]


class SVG:
    def __init__(self, top, bottom):
        self.top, self.bottom, self.p = top, bottom, []

    def add(self, s):
        self.p.append(s)

    def text(self, x, y, s, size=F_LABEL, color=TXT, bold=False, anchor="middle", mono=False):
        fw = ' font-weight="bold"' if bold else ""
        ff = ' font-family="monospace"' if mono else ""
        self.add(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{color}"{fw}{ff}>{escape(s)}</text>')

    def box(self, x, y, w, h, lines, style="plain"):
        f, st, sw, tc, bold, dash = STY[style]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{f}" stroke="{st}" stroke-width="{sw}"{d}/>')
        lines = [lines] if isinstance(lines, str) else lines
        sizes = [F_MAIN] + [F_SUB] * (len(lines) - 1)
        gap = 26
        top = y + h / 2 - gap * (len(lines) - 1) / 2 + 7
        for i, ln in enumerate(lines):
            col = tc if i == 0 or style == "pfstrong" else TXT2
            self.text(x + w / 2, round(top + i * gap, 1), ln, sizes[i], col, bold and i == 0)

    def panel(self, x, y, w, h, title, kind="gray", header=46):
        r = 22
        path = f"M{x},{y} H{x+w} V{y+h-r} Q{x+w},{y+h} {x+w-r},{y+h} H{x+r} Q{x},{y+h} {x},{y+h-r} Z"
        if kind == "teal":
            self.add(f'<path d="{path}" fill="#ffffff" stroke="{TEAL}" stroke-width="3"/>'); hc = TEAL
        elif kind == "outline":
            self.add(f'<path d="{path}" fill="#ffffff" stroke="{GRAY_S}" stroke-width="2"/>'); hc = GRAY_H
        else:
            self.add(f'<path d="{path}" fill="{GRAY_L}"/>'); hc = GRAY_H
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{header}" fill="{hc}"/>')
        self.text(x + w / 2, y + header / 2 + 7.5, title, F_HEAD, "#ffffff")

    def subpanel(self, x, y, w, h, title, color=TEAL):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#ffffff" stroke="{color}" stroke-width="2"/>')
        self.add(f'<path d="M{x},{y+12} Q{x},{y} {x+12},{y} H{x+w-12} Q{x+w},{y} {x+w},{y+12} V{y+38} H{x} Z" fill="{color}"/>')
        self.text(x + w / 2, y + 25, title, F_SUB, "#ffffff")

    def arrow(self, pts, color=TEAL, width=2.5, dash=False, label=None, lx=None, ly=None, lanchor="middle"):
        mid = {TEAL: "teal", RED: "red"}.get(color, "gray")
        d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(pts))
        da = ' stroke-dasharray="6 5"' if dash else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{da} marker-end="url(#arr-{mid})"/>')
        if label:
            for i, ln in enumerate(label if isinstance(label, list) else [label]):
                self.text(lx, ly + i * 23, ln, F_LABEL, TEAL_D if color == TEAL else TXT2, anchor=lanchor)

    def badge(self, x, y, n):
        self.add(f'<circle cx="{x}" cy="{y}" r="14" fill="{TEAL}"/>')
        self.text(x, y + 6, n, F_LABEL, "#ffffff", True)

    def big_arrow(self, x, y):
        self.add(f'<path d="M{x},{y-23} H{x+38} V{y-47} L{x+78},{y} L{x+38},{y+47} V{y+23} H{x} Z" fill="{TEAL}"/>')

    def legend(self, x, y, items=LEG_TEAM):
        cx = x
        for style, label in items:
            f, st, sw, _, _, dash = STY[style]
            d = f' stroke-dasharray="{dash}"' if dash else ""
            self.add(f'<rect x="{cx}" y="{y-14}" width="28" height="20" rx="4" fill="{f}" stroke="{st}" stroke-width="{sw}"{d}/>')
            self.text(cx + 36, y + 2, label, F_LABEL, TXT2, anchor="start")
            cx += 52 + F_LABEL * len(label)

    def save(self, path):
        h = self.bottom - self.top
        defs = "".join(
            f'<marker id="arr-{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
            for n, c in (("teal", TEAL), ("gray", "#6b6b6b"), ("red", RED)))
        body = "\n  ".join(self.p)
        Path(path).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {self.top} 1200 {h}" width="{int(1200*SCALE)}" height="{int(h*SCALE)}" font-family="{FONT}">\n'
            f'  <defs>{defs}</defs>\n  <rect x="0" y="{self.top}" width="1200" height="{h}" fill="#ffffff"/>\n  {body}\n</svg>\n', encoding="utf-8")


# 1 章
def d_challenges(out):
    s = SVG(80, 400)
    s.panel(40, 100, 500, 280, "よくある状態 (課題)", "gray")
    left = [["拡散する", "値のコピーがあちこちにある"], ["追えない", "誰が見た・使ったか記録がない"], ["変えられない", "変更は置き場所すべてに手作業"]]
    right = [["1 か所で管理", "値は保管庫だけに置く"], ["記録・統制できる", "アクセスを保管庫で管理"], ["1 か所の変更で反映", "残りは自動で同期"]]
    for i, l in enumerate(left):
        y = 166 + i * 70
        s.box(80, y, 420, 58, l, "plain")
        s.text(104, y + 36, "×", F_MAIN, RED, True)
    s.big_arrow(560, 240)
    s.panel(660, 100, 500, 280, "目指す状態 (ESO)", "teal")
    for i, r in enumerate(right):
        y = 166 + i * 70
        s.box(700, y, 420, 58, r, "pf")
        s.text(724, y + 36, "✓", F_MAIN, TEAL_D, True)
    s.save(out / "secret-challenges.svg")


# 2 章
def d_methods(out):
    s = SVG(80, 370)
    s.panel(40, 100, 520, 250, "① 標準 Secret：クラスタ内で手作業管理", "gray")
    s.box(62, 200, 100, 60, "担当者", "plain")
    s.arrow([(166, 230), (318, 230)], "#6b6b6b", 2)
    s.text(242, 216, "oc create secret", 14, TXT2, mono=True)
    s.box(324, 186, 214, 88, ["Secret", "クラスタ (etcd) 内"], "plain")
    s.text(300, 312, "↑ 作成・更新は 1 つずつ手作業", F_LABEL, RED, True)
    s.big_arrow(581, 225)
    s.panel(680, 100, 480, 250, "② ESO：外部の保管庫から自動で同期", "teal")
    s.box(704, 180, 190, 104, ["外部の保管庫", "AWS Secrets Manager", "OCI Vault など"], "vault")
    s.arrow([(898, 232), (984, 232)], TEAL, 2.5, label="同期", lx=941, ly=218)
    s.box(990, 196, 146, 72, ["Secret", "自動で作成"], "auto")
    s.text(799, 318, "↑ 値の管理元はここ 1 か所", F_LABEL, TEAL_D, True)
    s.save(out / "secret-management-methods.svg")


# 3 章
def d_eso_mechanism(out):
    s = SVG(80, 545)
    s.box(40, 270, 210, 112, ["外部の保管庫", "AWS Secrets Manager", "OCI Vault など"], "vault")
    s.panel(290, 100, 870, 430, "OpenShift クラスタ", "outline")
    s.subpanel(315, 168, 330, 337, "プラットフォームチームが管理")
    s.box(345, 225, 270, 70, ["SecretStore", "接続先と認証方法"], "pf")
    s.box(345, 385, 270, 80, ["ESO (Operator)", "値を取得して Secret を作る"], "pfstrong")
    s.subpanel(670, 168, 465, 337, "アプリの Namespace", APP_S)
    s.box(700, 218, 405, 66, ["ExternalSecret", "どの値を、どの Secret 名で取得するか"], "app")
    s.box(700, 322, 405, 66, ["Secret", "ESO が自動で作成・更新"], "auto")
    s.box(700, 426, 405, 62, ["アプリ (Pod)", "環境変数 / ボリュームで参照"], "plain")
    s.arrow([(480, 297), (480, 382)], "#6b6b6b", 2, True)
    s.arrow([(698, 250), (657, 250), (657, 398), (619, 398)], "#6b6b6b", 2, True)
    s.arrow([(343, 440), (145, 440), (145, 385)], TEAL, 3)
    s.badge(245, 440, "①")
    s.arrow([(617, 450), (685, 450), (685, 355), (698, 355)], TEAL, 3)
    s.badge(685, 412, "②")
    s.arrow([(902, 390), (902, 423)], TEAL, 3)
    s.badge(932, 406, "③")
    s.save(out / "eso-mechanism.svg")


# 5 章
def d_install_steps(out):
    s = SVG(80, 450)
    steps = [["cert-manager", "Operator を導入"], ["ESO Operator", "を導入"], ["ESO 本体の展開", "ExternalSecretsConfig を作成"],
             ["保管庫の準備", "認証・通信の設定"], ["SecretStore 作成", "接続確認 (Valid)"], ["ExternalSecret 作成", "Secret が自動で作成される"]]
    w, gap, ys = 340, 50, (140, 296)
    for i, st in enumerate(steps):
        row, col = divmod(i, 3)
        x, y = 40 + col * (w + gap), ys[row]
        s.box(x, y, w, 90, st, "vault" if i == 3 else "pf")
        s.badge(x + 26, y, str(i + 1))
        if col < 2:
            s.arrow([(x + w + 3, y + 45), (x + w + gap - 3, y + 45)], TEAL, 2.5)
    x3 = 40 + 2 * (w + gap) + w / 2
    s.arrow([(x3, 232), (x3, 262), (40 + w / 2, 262), (40 + w / 2, 293)], TEAL, 2.5)

    def band(x, y, w_, label, color):
        s.add(f'<rect x="{x}" y="{y}" width="{w_}" height="32" rx="16" fill="{color}"/>')
        s.text(x + w_ / 2, y + 22, label, F_LABEL, "#ffffff", True)
    band(40, 94, 3 * w + 2 * gap, "共通 (ROSA / OCI とも同じ)", GRAY_H)
    band(40, 400, w, "環境依存", TEAL_D)
    band(40 + w + gap, 400, 2 * w + gap, "接続先の記述だけ環境依存", GRAY_H)
    s.save(out / "install-steps.svg")


def _auth_base(s, left, right):
    s.panel(40, 100, 400, 320, left, "outline")
    s.panel(640, 100, 520, 320, right, "gray")


def d_rosa(out):
    s = SVG(80, 440)
    _auth_base(s, "ROSA クラスタ", "AWS")
    s.box(70, 168, 340, 74, ["ESO", "SecretStore の設定で動作"], "pfstrong")
    s.box(70, 310, 340, 74, ["クラスタの OIDC", "ServiceAccount のトークンを発行"], "pf")
    s.box(670, 168, 460, 74, ["AWS Secrets Manager", "シークレットの保管"], "vault")
    s.box(670, 310, 460, 74, ["IAM Role", "読み取りのみ。クラスタの OIDC を信頼"], "pf")
    s.arrow([(240, 244), (240, 307)], TEAL, 2.5, label="① SA の短期トークン", lx=252, ly=282, lanchor="start")
    s.arrow([(412, 347), (667, 347)], TEAL, 2.5, label=["② Role を", "引き受ける (STS)"], lx=540, ly=311)
    s.arrow([(412, 205), (667, 205)], TEAL, 3, label="③ 値を取得", lx=540, ly=192)
    s.arrow([(900, 308), (900, 246)], "#6b6b6b", 2, True, "許可", 912, 284, "start")
    s.save(out / "rosa-auth.svg")


def d_oci_apikey(out):
    s = SVG(80, 440)
    s.panel(40, 100, 380, 320, "OpenShift on OCI", "outline")
    s.panel(760, 100, 400, 320, "OCI", "gray")
    s.box(65, 168, 330, 74, ["ESO", "SecretStore の設定で動作"], "pfstrong")
    s.box(65, 310, 330, 74, ["Secret (API キー)", "秘密鍵とフィンガープリント"], "warn")
    s.box(785, 168, 350, 74, ["OCI Vault", "シークレットの保管"], "vault")
    s.box(785, 310, 350, 74, ["OCI ユーザー", "API キーを登録"], "pf")
    s.box(500, 310, 180, 74, ["作業端末", "秘密鍵 (一時的)"], "plain")
    s.arrow([(783, 347), (683, 347)], TEAL, 2.5)
    s.badge(733, 347, "①")
    s.arrow([(498, 347), (398, 347)], TEAL, 2.5)
    s.badge(448, 347, "②")
    s.arrow([(230, 307), (230, 246)], "#6b6b6b", 2, True, "参照", 242, 284, "start")
    s.arrow([(397, 205), (782, 205)], TEAL, 3)
    s.badge(590, 205, "③")
    s.arrow([(960, 308), (960, 246)], "#6b6b6b", 2, True, ["IAM ポリシーで", "読み取りを許可"], 972, 270, "start")
    s.save(out / "oci-apikey-auth.svg")


def d_apikey_lifecycle(out):
    s = SVG(110, 470)
    steps = [(["専用ユーザーで", "API キーを作成"], "pf"), (["秘密鍵を", "ダウンロード"], "pf"),
             (["OpenShift に", "Secret として登録"], "pf"), (["作業端末の", "秘密鍵を削除"], "pf")]
    w, gap = 250, 40
    for i, (t, st) in enumerate(steps):
        x = 40 + i * (w + gap)
        s.box(x, 140, w, 90, t, st)
        s.badge(x + 24, 140, str(i + 1))
        if i < 3:
            s.arrow([(x + w + 3, 185), (x + w + gap - 3, 185)], TEAL, 2.5)
    notes = [["権限は読み取りのみ", "(secret-bundles / vaults)"], ["再取得できない", "紛失したら作り直す"],
             ["プラットフォームチームだけが", "参照できる Namespace に置く"], ["Secret 以外に", "秘密鍵を残さない"]]
    for i, lines in enumerate(notes):
        x = 40 + i * (w + gap)
        for k, ln in enumerate(lines):
            s.text(x + w / 2, 262 + k * 24, ln, F_LABEL, TXT2)
    # ローテーション
    s.add(f'<rect x="40" y="330" width="1120" height="120" rx="16" fill="{GRAY_L}"/>')
    s.text(60, 364, "ローテーション (止めずに入れ替え)", F_LABEL, TEAL_D, True, anchor="start")
    rot = ["新しいキーを追加", "Secret を差し替え", "同期を確認", "古いキーを削除"]
    w2, gap2 = 230, 50
    for i, t in enumerate(rot):
        x = 80 + i * (w2 + gap2)
        s.box(x, 388, w2, 46, t, "plain")
        if i < 3:
            s.arrow([(x + w2 + 3, 411), (x + w2 + gap2 - 3, 411)], TEAL, 2.5)
    s.save(out / "apikey-lifecycle.svg")


def d_oci_wi(out):
    s = SVG(80, 440)
    _auth_base(s, "OpenShift on OCI", "OCI")
    s.box(70, 168, 340, 74, ["ESO", "SecretStore の設定で動作"], "pfstrong")
    s.box(70, 310, 340, 74, ["ServiceAccount", "アプリの Namespace ごと"], "pf")
    s.box(670, 168, 460, 74, ["OCI Vault", "シークレットの保管"], "vault")
    s.box(665, 310, 245, 74, ["信頼設定", "アイデンティティ・ドメイン"], "pf")
    s.box(925, 310, 210, 74, ["IAM ポリシー", "SA 名で読み取り許可"], "pf")
    s.arrow([(240, 244), (240, 307)], TEAL, 2.5, label="① SA の短期トークン", lx=252, ly=282, lanchor="start")
    s.arrow([(412, 347), (662, 347)], TEAL, 2.5, label=["② OCI の", "トークンに交換"], lx=537, ly=311)
    s.arrow([(412, 205), (667, 205)], TEAL, 3, label="③ 値を取得", lx=540, ly=192)
    s.arrow([(1030, 308), (1030, 246)], "#6b6b6b", 2, True, "許可", 1042, 284, "start")
    s.save(out / "oci-workload-identity.svg")


def d_scope(out):
    s = SVG(70, 590)
    s.legend(300, 92)
    s.panel(40, 116, 1120, 124, "クラスタ スコープ (Namespace に属さない)", "teal", 44)
    s.box(75, 174, 330, 50, "ExternalSecretsConfig (cluster)", "pf")
    s.box(435, 174, 330, 50, "Namespace", "pf")
    s.box(795, 174, 330, 50, "ClusterSecretStore (本番案)", "pf")
    s.text(600, 272, "Namespace スコープ (Namespace の中に作る)", F_HEAD, TEAL_D, True)
    s.subpanel(40, 290, 300, 290, "external-secrets-operator 等", GRAY_H)
    s.box(62, 344, 256, 62, ["Operator", "cert-manager / ESO"], "pf")
    s.subpanel(360, 290, 360, 290, "external-secrets", GRAY_H)
    s.box(382, 340, 316, 58, ["ESO 本体の Pod"], "auto")
    s.box(382, 410, 316, 70, ["NetworkPolicy eso-sys-*", "通信制限。編集しない"], "auto")
    s.box(382, 492, 316, 70, ["NetworkPolicy 外向き許可", "ROSA で追加"], "pf")
    s.subpanel(740, 290, 420, 290, "<TARGET_NAMESPACE> (アプリごと)", APP_S)
    for i, (t, st) in enumerate([("ServiceAccount", "pf"), ("Secret: API キー (OCI)", "pf"), ("SecretStore", "pf"),
                                 ("ExternalSecret", "app"), ("Secret: 同期先", "auto")]):
        s.box(762, 338 + i * 47, 376, 40, t, st)
    s.save(out / "openshift-resources-scope.svg")


def d_permissions(out):
    s = SVG(70, 600)
    s.legend(300, 92)
    s.panel(40, 116, 600, 466, "OpenShift クラスタ (環境ごと)", "outline")
    s.box(70, 180, 540, 52, "ESO", "pfstrong")
    for i, name in enumerate(["アプリ A", "アプリ B"]):
        x = 70 + i * 280
        s.subpanel(x, 250, 260, 312, f"Namespace: {name}", APP_S)
        for j, (t, st) in enumerate([("ExternalSecret", "app"), ("SecretStore", "pf"), (f"ServiceAccount {name[-1]}", "pf"), ("Secret", "auto")]):
            s.box(x + 18, 300 + j * 64, 224, 48, t, st)
        s.arrow([(x + 130, 349), (x + 130, 361)], "#6b6b6b", 2)
        s.arrow([(x + 130, 413), (x + 130, 425)], "#6b6b6b", 2)
    s.panel(700, 116, 460, 466, "OCI テナンシ", "gray")
    s.box(728, 180, 404, 62, ["信頼設定 (クラスタごと)", "アイデンティティ・ドメイン"], "pf")
    s.subpanel(728, 262, 404, 300, "コンパートメント: 環境")
    s.box(752, 312, 356, 54, "Vault + マスター暗号化キー", "vault")
    s.box(752, 420, 168, 118, ["シークレット", "アプリ A 用", "SA A だけ読める"], "pf")
    s.box(940, 420, 168, 118, ["シークレット", "アプリ B 用", "SA B だけ読める"], "pf")
    s.arrow([(836, 368), (836, 417)], "#6b6b6b", 2, True)
    s.arrow([(1024, 368), (1024, 417)], "#6b6b6b", 2, True)
    s.text(930, 398, "暗号化", F_LABEL, TXT2)
    s.arrow([(612, 206), (725, 206)], TEAL, 3)
    s.badge(668, 206, "①")
    s.arrow([(612, 222), (668, 222), (668, 478), (749, 478)], TEAL, 3)
    s.badge(668, 350, "②")
    s.save(out / "permission-separation.svg")


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for f in (d_challenges, d_methods, d_eso_mechanism, d_install_steps, d_rosa, d_oci_apikey, d_apikey_lifecycle, d_oci_wi,
              d_scope, d_permissions,):
        f(out)
    print("generated")
