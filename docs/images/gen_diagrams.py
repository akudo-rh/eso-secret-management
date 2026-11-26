#!/usr/bin/env python3
"""README 用の図 (SVG) を共通デザインで生成する (secret-management-methods.svg は手作業で作成)。
使い方: python3 docs/images/gen_diagrams.py docs/images
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

FONT = "'Noto Sans JP','Noto Sans CJK JP','Hiragino Sans','Hiragino Kaku Gothic ProN','Yu Gothic UI','Meiryo',sans-serif"
RED, TEAL, TEAL_D, TEAL_L = "#d10000", "#37a3a3", "#1f7a7a", "#e7f4f4"
GRAY_H, GRAY_L, GRAY_BAR, GRAY_S, TXT, TXT2 = "#b3b3b3", "#f2f2f2", "#ededed", "#c8c8c8", "#333333", "#555555"
APP_S = "#4d4d4d"

# 箱のスタイル: (fill, stroke, stroke-width, text-color, bold, dash)
STY = {
    "plain": ("#ffffff", GRAY_S, 1.5, TXT, False, None),
    "gray": (GRAY_L, GRAY_S, 1.5, TXT, False, None),
    "pf": (TEAL_L, TEAL, 2, TEAL_D, True, None),            # プラットフォームチーム
    "pfstrong": (TEAL, TEAL, 2, "#ffffff", True, None),    # 主役 (ESO など)
    "app": ("#ffffff", APP_S, 2, TXT, True, None),          # アプリチーム
    "auto": ("#ffffff", "#8a8a8a", 1.5, TXT2, False, "6 4"),  # 自動で作られる
    "vault": (TEAL_L, TEAL, 3, TEAL_D, True, None),         # 保管庫
    "warn": ("#ffffff", RED, 3, RED, True, None),
}


class SVG:
    def __init__(self, w, h):
        self.w, self.h, self.p = w, h, []

    def add(self, s):
        self.p.append(s)

    def text(self, x, y, s, size=16, color=TXT, bold=False, anchor="middle", mono=False):
        fw = ' font-weight="bold"' if bold else ""
        ff = ' font-family="monospace"' if mono else ""
        self.add(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{color}"{fw}{ff}>{s}</text>')

    def lines(self, cx, cy, lines, size=16, color=TXT, bold_first=False, gap=None):
        gap = gap or size * 1.45
        top = cy - gap * (len(lines) - 1) / 2 + size * 0.36
        for i, ln in enumerate(lines):
            b = bold_first and i == 0
            sz = size if (i == 0 or not bold_first) else size - 3
            col = color if (i == 0 or not bold_first) else TXT2 if color in (TXT,) else color
            self.text(cx, round(top + i * gap, 1), escape(ln), sz, col, b)

    def title(self, s):
        self.text(self.w / 2, 52, s, 26, RED)

    def box(self, x, y, w, h, lines, style="plain", size=16, rx=8):
        f, st, sw, tc, bold, dash = STY[style]
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{f}" stroke="{st}" stroke-width="{sw}"{d}/>')
        lines = [lines] if isinstance(lines, str) else lines
        gap = size * 1.35
        top = y + h / 2 - gap * (len(lines) - 1) / 2 + size * 0.36
        for i, ln in enumerate(lines):
            sz = size if i == 0 else size - 3
            col = tc if i == 0 else (tc if style == "pfstrong" else TXT2)
            self.text(x + w / 2, round(top + i * gap, 1), escape(ln), sz, col, bold and i == 0)

    def panel(self, x, y, w, h, title, kind="gray", size=19, header=48):
        """kind: gray (これまで/一般) / teal (主役) / outline (枠のみ)"""
        r = 22
        path = f"M{x},{y} H{x+w} V{y+h-r} Q{x+w},{y+h} {x+w-r},{y+h} H{x+r} Q{x},{y+h} {x},{y+h-r} Z"
        if kind == "teal":
            self.add(f'<path d="{path}" fill="#ffffff" stroke="{TEAL}" stroke-width="3"/>')
            hc = TEAL
        elif kind == "outline":
            self.add(f'<path d="{path}" fill="#ffffff" stroke="{GRAY_S}" stroke-width="2"/>')
            hc = GRAY_H
        else:
            self.add(f'<path d="{path}" fill="{GRAY_L}"/>')
            hc = GRAY_H
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{header}" fill="{hc}"/>')
        self.text(x + w / 2, y + header / 2 + size * 0.36, escape(title), size, "#ffffff")

    def subpanel(self, x, y, w, h, title, color=TEAL, size=15):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#ffffff" stroke="{color}" stroke-width="2"/>')
        self.add(f'<path d="M{x},{y+12} Q{x},{y} {x+12},{y} H{x+w-12} Q{x+w},{y} {x+w},{y+12} V{y+34} H{x} Z" fill="{color}"/>')
        self.text(x + w / 2, y + 23, escape(title), size, "#ffffff")

    def arrow(self, pts, color=TEAL, width=2.5, dash=False, label=None, lx=None, ly=None, lsize=14, lcolor=None, lanchor="middle"):
        mid = "teal" if color == TEAL else "gray" if color != RED else "red"
        d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(pts))
        da = ' stroke-dasharray="6 5"' if dash else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{da} marker-end="url(#arr-{mid})"/>')
        if label:
            for i, ln in enumerate(label if isinstance(label, list) else [label]):
                self.text(lx, ly + i * lsize * 1.35, escape(ln), lsize, lcolor or (TEAL_D if color == TEAL else TXT2), anchor=lanchor)

    def badge(self, x, y, n, color=TEAL):
        self.add(f'<circle cx="{x}" cy="{y}" r="13" fill="{color}"/>')
        self.text(x, y + 5.5, n, 15, "#ffffff", True)

    def big_arrow(self, x, y):
        self.add(f'<path d="M{x},{y-23} H{x+38} V{y-47} L{x+78},{y} L{x+38},{y+47} V{y+23} H{x} Z" fill="{TEAL}"/>')

    def bar(self, y, lines, h=None):
        h = h or (34 + 28 * len(lines))
        self.add(f'<rect x="40" y="{y}" width="{self.w-80}" height="{h}" rx="16" fill="{GRAY_BAR}"/>')
        top = y + h / 2 - 28 * (len(lines) - 1) / 2 + 6
        for i, ln in enumerate(lines):
            self.text(self.w / 2, round(top + i * 28), ln, 17, TXT)

    def legend(self, x, y, items):
        cx = x
        for style, label in items:
            f, st, sw, _, _, dash = STY[style]
            d = f' stroke-dasharray="{dash}"' if dash else ""
            self.add(f'<rect x="{cx}" y="{y-13}" width="26" height="18" rx="4" fill="{f}" stroke="{st}" stroke-width="{sw}"{d}/>')
            self.text(cx + 34, y + 1, escape(label), 14, TXT2, anchor="start")
            cx += 44 + 15 * len(label)

    def save(self, path):
        defs = "".join(
            f'<marker id="arr-{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
            for n, c in (("teal", TEAL), ("gray", "#6b6b6b"), ("red", RED)))
        body = "\n  ".join(self.p)
        Path(path).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" font-family="{FONT}">\n'
            f'  <defs>{defs}</defs>\n  <rect width="{self.w}" height="{self.h}" fill="#ffffff"/>\n  {body}\n</svg>\n', encoding="utf-8")


T = lambda s, c=TEAL_D: f'<tspan fill="{c}" font-weight="bold">{escape(s)}</tspan>'
R_ = lambda s: T(s, RED)
LEG_TEAM = [("pf", "プラットフォームチームが管理"), ("app", "アプリチームが管理"), ("auto", "自動で作成")]


def d1_challenges(out):
    s = SVG(1200, 560)
    s.title("Secret 管理の課題と目指す状態")
    s.panel(40, 100, 500, 330, "よくある状態 (課題)", "gray")
    items = ["ソースコード / Git に平文", "CI の変数・設定ファイルに値が残る", "ローテーションが手作業", "誰が使ったか追えない"]
    for i, t in enumerate(items):
        y = 172 + i * 62
        s.box(80, y, 420, 48, t, "plain", 16)
        s.text(98, y + 30, "×", 18, RED, True)
    s.big_arrow(560, 265)
    s.panel(660, 100, 500, 330, "目指す状態", "teal")
    items = ["値の正は専用の保管庫に 1 か所", "アプリには必要な時だけ安全に渡す", "Git には値を置かない", "更新・権限を保管庫側で一元管理"]
    for i, t in enumerate(items):
        y = 172 + i * 62
        s.box(700, y, 420, 48, t, "pf", 16)
        s.text(718, y + 30, "✓", 18, TEAL_D, True)
    s.bar(462, ["Secret = パスワード、API キー、証明書、トークンなど、漏えいすると被害が出る値。",
                "値の正を " + T("保管庫 1 か所") + " に集め、アプリには自動で安全に渡す仕組みが必要になる。"])
    s.save(out / "secret-challenges.svg")


def d2_eso_mechanism(out):
    s = SVG(1200, 650)
    s.title("ESO の仕組み：定義を 2 つに分け、Operator が同期する")
    s.box(40, 270, 210, 110, ["外部の保管庫", "AWS Secrets Manager", "OCI Vault など"], "vault", 19)
    s.panel(290, 100, 870, 430, "OpenShift クラスタ", "outline")
    s.subpanel(315, 170, 330, 335, "プラットフォームチームが管理")
    s.box(345, 222, 270, 68, ["SecretStore", "接続先と認証方法"], "pf", 18)
    s.box(345, 385, 270, 80, ["ESO (Operator)", "値を取得して Secret を作る"], "pfstrong", 19)
    s.subpanel(670, 170, 465, 335, "アプリの Namespace", APP_S)
    s.box(700, 215, 405, 62, ["ExternalSecret", "どの値を、どの Secret 名で取得するか"], "app", 18)
    s.box(700, 320, 405, 62, ["Secret", "ESO が自動で作成・更新 (手で作らない)"], "auto", 18)
    s.box(700, 425, 405, 62, ["アプリ (Pod)", "環境変数 / ボリュームで参照"], "plain", 18)
    s.arrow([(480, 292), (480, 382)], "#6b6b6b", 2, True, "参照", 492, 343, lanchor="start")
    s.arrow([(698, 246), (657, 246), (657, 398), (619, 398)], "#6b6b6b", 2, True)
    s.arrow([(343, 440), (145, 440), (145, 383)], TEAL, 3)
    s.badge(245, 440, "①")
    s.arrow([(617, 450), (685, 450), (685, 351), (698, 351)], TEAL, 3)
    s.badge(685, 410, "②")
    s.arrow([(902, 384), (902, 422)], TEAL, 3)
    s.badge(935, 403, "③")
    s.bar(555, [T("①") + " ESO が保管庫から定期的に値を取得 → " + T("②") + " Secret を自動で作成・更新 → " + T("③") + " アプリは従来どおり参照",
                "アプリは保管庫の存在を意識しない。Git に置くのは「参照の定義」だけで、値そのものは置かない。"])
    s.save(out / "eso-mechanism.svg")


def d3_install_steps(out):
    s = SVG(1200, 360)
    s.title("導入の流れ (ROSA / OCI で実機検証済み)")
    steps = [["cert-manager", "Operator 導入"], ["ESO Operator", "導入"], ["ESO 本体の展開", "ExternalSecretsConfig"],
             ["保管庫の準備と", "認証・通信の設定"], ["SecretStore 作成", "接続確認 (Valid)"], ["ExternalSecret 作成", "Secret が自動作成"]]
    w, gap, x0 = 168, 22, 40
    for i, st in enumerate(steps):
        x = x0 + i * (w + gap)
        style = "vault" if i == 3 else "pf"
        s.box(x, 150, w, 96, st, style, 16)
        s.badge(x + w / 2, 150, str(i + 1))
        if i < 5:
            s.arrow([(x + w + 2, 198), (x + w + gap - 2, 198)], TEAL, 2.5)
    # 区分の帯
    def band(i0, i1, label, color):
        x1 = x0 + i0 * (w + gap)
        x2 = x0 + i1 * (w + gap) + w
        s.add(f'<rect x="{x1}" y="98" width="{x2-x1}" height="30" rx="15" fill="{color}"/>')
        s.text((x1 + x2) / 2, 119, escape(label), 15, "#ffffff", True)
    band(0, 2, "共通 (ROSA / OCI とも同じ)", GRAY_H)
    band(3, 3, "環境依存", TEAL_D)
    band(4, 5, "接続先の記述だけ環境依存", GRAY_H)
    s.bar(276, ["手順 4 の内容は環境ごとに異なる (5.1 / 5.2)。ROSA では ESO の外向き通信を許可する " + T("NetworkPolicy") + " の追加が必要。"])
    s.save(out / "install-steps.svg")


def _two_panel_auth(s, left_title, right_title):
    s.panel(40, 100, 400, 320, left_title, "outline")
    s.panel(640, 100, 520, 320, right_title, "gray")


def d4_rosa(out):
    s = SVG(1200, 540)
    s.title("ROSA 版：STS で認証し、AWS Secrets Manager から取得")
    _two_panel_auth(s, "ROSA クラスタ", "AWS")
    s.box(70, 170, 340, 70, ["ESO", "SecretStore の設定で動作"], "pfstrong", 19)
    s.box(70, 310, 340, 70, ["クラスタの OIDC", "ServiceAccount のトークンを発行"], "pf", 17)
    s.box(670, 170, 460, 70, ["AWS Secrets Manager", "シークレットの保管"], "vault", 19)
    s.box(670, 310, 460, 70, ["IAM Role", "読み取り権限のみ。クラスタの OIDC を信頼"], "pf", 17)
    s.arrow([(240, 242), (240, 307)], TEAL, 2.5, label="① SA の短期トークン", lx=252, ly=280, lanchor="start")
    s.arrow([(412, 345), (667, 345)], TEAL, 2.5, label=["② Role を", "引き受ける (STS)"], lx=540, ly=313)
    s.arrow([(412, 205), (667, 205)], TEAL, 3, label="③ 値を取得", lx=540, ly=192)
    s.arrow([(900, 308), (900, 244)], "#6b6b6b", 2, True, "許可", 912, 281, lanchor="start")
    s.bar(448, [T("アクセスキーをクラスタに置かない") + "。短期トークンで都度認証する。",
                "注意: Role の信頼ポリシーの Namespace / ServiceAccount 名は、クラスタ上の実際の名前と完全一致させる。"])
    s.save(out / "rosa-auth.svg")


def d5_oci_apikey(out):
    s = SVG(1200, 540)
    s.title("OCI 版 (検証で使用)：API キーで認証し、OCI Vault から取得")
    _two_panel_auth(s, "OpenShift on OCI", "OCI")
    s.box(70, 170, 340, 70, ["ESO", "SecretStore の設定で動作"], "pfstrong", 19)
    s.box(70, 310, 340, 70, ["Secret (API キー)", "秘密鍵とフィンガープリント"], "warn", 17)
    s.box(670, 170, 460, 70, ["OCI Vault", "シークレットの保管"], "vault", 19)
    s.box(670, 310, 460, 70, ["IAM ポリシー", "API キーのユーザーに読み取りを許可"], "pf", 17)
    s.arrow([(240, 307), (240, 243)], "#6b6b6b", 2, True, "参照", 252, 281, lanchor="start")
    s.arrow([(412, 205), (667, 205)], TEAL, 3, label="API キーで署名して取得", lsize=13, lx=540, ly=192)
    s.arrow([(900, 308), (900, 244)], "#6b6b6b", 2, True, "許可", 912, 281, lanchor="start")
    s.bar(448, [R_("クラスタ内に秘密鍵を持つ") + " ため、保管とローテーションの管理が必要 (管理方法の案は 5.2.2)。",
                "本番では、ServiceAccount 単位で権限を分けられる Workload Identity を候補とする (5.2.1)。"])
    s.save(out / "oci-apikey-auth.svg")


def d6_oci_wi(out):
    s = SVG(1200, 540)
    s.title("OCI 版 (本番候補)：Workload Identity で認証")
    _two_panel_auth(s, "OpenShift on OCI", "OCI")
    s.box(70, 170, 340, 70, ["ESO", "SecretStore の設定で動作"], "pfstrong", 19)
    s.box(70, 310, 340, 70, ["ServiceAccount", "アプリの Namespace ごと"], "pf", 17)
    s.box(670, 170, 460, 70, ["OCI Vault", "シークレットの保管"], "vault", 19)
    s.box(670, 310, 220, 70, ["信頼設定", "アイデンティティ・ドメイン"], "pf", 16)
    s.box(910, 310, 220, 70, ["IAM ポリシー", "SA 名で読み取りを許可"], "pf", 16)
    s.arrow([(240, 242), (240, 307)], TEAL, 2.5, label="① SA の短期トークン", lx=252, ly=280, lanchor="start")
    s.arrow([(412, 345), (667, 345)], TEAL, 2.5, label=["② OCI の", "トークンに交換"], lx=540, ly=313)
    s.arrow([(412, 205), (667, 205)], TEAL, 3, label="③ 値を取得", lx=540, ly=192)
    s.arrow([(1020, 308), (1020, 244)], "#6b6b6b", 2, True, "許可", 1032, 281, lanchor="start")
    s.bar(448, ["AWS の STS と同じ考え方で、" + T("ServiceAccount 単位で権限を分けられる") + "。",
                "ESO の OCI 用の Workload 設定は OKE 向けの仕組みが前提のため、OpenShift での利用可否を確認中 (7 章)。"])
    s.save(out / "oci-workload-identity.svg")


def d7_scope(out):
    s = SVG(1200, 640)
    s.title("OpenShift 上で作成するリソースとスコープ")
    s.legend(300, 92, LEG_TEAM)
    s.panel(40, 112, 1120, 118, "クラスタ スコープ (Namespace に属さない)", "teal", 17, 40)
    s.box(80, 168, 320, 48, ["ExternalSecretsConfig (cluster)"], "pf", 16)
    s.box(440, 168, 320, 48, ["Namespace"], "pf", 16)
    s.box(800, 168, 320, 48, ["ClusterSecretStore (本番案)"], "pf", 16)
    s.text(600, 258, "Namespace スコープ (Namespace の中に作る)", 17, TEAL_D, True)
    s.subpanel(40, 276, 300, 290, "external-secrets-operator 等", GRAY_H)
    s.box(65, 330, 250, 56, ["Operator", "cert-manager / ESO"], "pf", 16)
    s.subpanel(360, 276, 360, 290, "external-secrets", GRAY_H)
    s.box(385, 322, 310, 56, ["ESO 本体の Pod"], "auto", 16)
    s.box(385, 392, 310, 56, ["NetworkPolicy eso-sys-*", "通信制限。編集しない"], "auto", 16)
    s.box(385, 462, 310, 56, ["NetworkPolicy 外向き許可", "ROSA で追加"], "pf", 16)
    s.subpanel(740, 276, 420, 290, "<TARGET_NAMESPACE> (アプリごと)", APP_S)
    rows = [("ServiceAccount", "pf"), ("Secret: API キー (OCI)", "pf"), ("SecretStore", "pf"), ("ExternalSecret", "app"), ("Secret: 同期先", "auto")]
    for i, (t, st) in enumerate(rows):
        s.box(765, 318 + i * 48, 370, 40, [t], st, 16)
    s.bar(584, ["アプリチームが作るのは " + T("ExternalSecret", APP_S) + " だけ。それ以外はプラットフォームチームが用意するか、自動で作成される。"], h=40)
    s.save(out / "openshift-resources-scope.svg")


def d8_roles(out):
    s = SVG(1200, 620)
    s.title("作業ごとの担当 (R1〜R8)")
    s.panel(40, 100, 500, 420, "プラットフォームチーム (基盤・権限・保管庫)", "teal", 18)
    s.panel(660, 100, 500, 420, "アプリチーム (Git・アプリ定義)", "gray", 18)
    pf = [("R2", "保管庫・IAM 権限の設定"), ("R3", "Secret の値の登録・更新"), ("R5", "ServiceAccount / SecretStore の作成"), ("R4", "ESO の導入・監視")]
    ys = [175, 260, 345, 430]
    for (n, t), y in zip(pf, ys):
        s.box(80, y, 420, 58, [f"{n}. {t}"], "pf", 17)
    app = [("R1", "必要な Secret の洗い出し", 175), ("R6", "ExternalSecret の作成 (Git 管理)", 345), ("R8", "アプリで Secret を利用", 430)]
    for n, t, y in app:
        s.box(700, y, 420, 58, [f"{n}. {t}"], "app", 17)
    s.arrow([(698, 204), (502, 204)], TEAL, 2.5, label="申請", lx=600, ly=194)
    s.arrow([(290, 233), (290, 258)], TEAL, 2.5)
    s.arrow([(78, 204), (60, 204), (60, 374), (78, 374)], TEAL, 2.5)
    s.arrow([(502, 374), (698, 374)], TEAL, 2.5, label="参照先を提供", lx=600, ly=364)
    s.arrow([(910, 403), (910, 428)], TEAL, 2.5)
    s.text(922, 421, "CI/CD で適用 (R7)", 14, TEAL_D, anchor="start")
    s.bar(546, ["ExternalSecret (R6) はアプリチームだけで作成できる。取得できる範囲は " + T("R2・R5 で先に決まっている") + " ため、個別の確認は不要。"], h=44)
    s.save(out / "roles.svg")


def d9_permissions(out):
    s = SVG(1200, 712)
    s.title("権限分離の全体図 (OCI + Workload Identity の案)")
    s.legend(300, 92, LEG_TEAM)
    s.panel(40, 112, 600, 470, "OpenShift クラスタ (環境ごと)", "outline")
    s.box(70, 178, 540, 50, ["ESO"], "pfstrong", 18)
    for i, name in enumerate(["アプリ A", "アプリ B"]):
        x = 70 + i * 280
        s.subpanel(x, 248, 260, 310, f"Namespace: {name}", APP_S)
        s.box(x + 20, 292, 220, 46, ["ExternalSecret"], "app", 16)
        s.box(x + 20, 356, 220, 46, ["SecretStore"], "pf", 16)
        s.box(x + 20, 420, 220, 46, [f"ServiceAccount {name[-1]}"], "pf", 16)
        s.box(x + 20, 484, 220, 46, ["Secret"], "auto", 16)
        s.arrow([(x + 130, 339), (x + 130, 353)], "#6b6b6b", 2)
        s.arrow([(x + 130, 403), (x + 130, 417)], "#6b6b6b", 2)
    s.panel(700, 112, 460, 470, "OCI テナンシ", "gray")
    s.box(730, 178, 400, 56, ["信頼設定 (クラスタごと)", "アイデンティティ・ドメイン"], "pf", 16)
    s.subpanel(730, 262, 400, 296, "コンパートメント: 環境")
    s.box(755, 308, 350, 56, ["Vault + マスター暗号化キー"], "vault", 17)
    s.box(755, 418, 165, 110, ["シークレット", "アプリ A", "SA A だけ読める"], "pf", 16)
    s.box(940, 418, 165, 110, ["シークレット", "アプリ B", "SA B だけ読める"], "pf", 16)
    s.arrow([(837, 366), (837, 415)], "#6b6b6b", 2, True)
    s.arrow([(1022, 366), (1022, 415)], "#6b6b6b", 2, True)
    s.text(930, 396, "暗号化", 14, TXT2)
    s.arrow([(612, 203), (727, 203)], TEAL, 3)
    s.badge(668, 203, "①")
    s.arrow([(612, 220), (668, 220), (668, 470), (752, 470)], TEAL, 3)
    s.badge(668, 345, "②")
    s.bar(606, [T("①") + " ESO が SA のトークンを OCI のトークンに交換 → " + T("②") + " SA ごとの権限でシークレットを読む",
                "環境はクラスタ・コンパートメント・信頼設定で分ける。" + T("アプリ間の分け方 (a〜c) は検討中") + " (6.3、7 章)。"])
    s.save(out / "permission-separation.svg")


def d10_flow(out):
    s = SVG(1200, 340)
    s.title("運用フロー：新しい Secret を追加する")
    s.legend(330, 92, LEG_TEAM)
    steps = [(["Secret を申請", "R1"], "app"), (["基盤・IAM の準備", "初回のみ (R2・R5)"], "pf"),
             (["保管庫に値を登録", "開発→テスト→本番 (R3)"], "pf"), (["ExternalSecret を", "Git に登録 (R6)"], "app"),
             (["デプロイ・自動同期", "CI/CD → ESO (R7・R8)"], "auto")]
    w, gap, x0 = 200, 30, 40
    for i, (t, st) in enumerate(steps):
        x = x0 + i * (w + gap)
        s.box(x, 140, w, 96, t, st, 16)
        s.badge(x + w / 2, 140, str(i + 1))
        if i < 4:
            s.arrow([(x + w + 3, 188), (x + w + gap - 3, 188)], TEAL, 2.5)
    s.bar(262, ["値の受け渡しは 6.2 の案から選ぶ。値の更新 (ローテーション) は保管庫に登録するだけで、" + T("refreshInterval 後に自動で反映") + " される。"], h=44)
    s.save(out / "operation-flow.svg")


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for f in (d1_challenges, d2_eso_mechanism, d3_install_steps, d4_rosa, d5_oci_apikey, d6_oci_wi, d7_scope, d8_roles, d9_permissions, d10_flow):
        f(out)
    print("generated")
