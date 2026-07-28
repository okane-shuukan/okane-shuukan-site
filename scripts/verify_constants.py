#!/usr/bin/env python3
"""data/tax-constants.json と公開HTML内の制度数値が一致するかを検証する。

本サイトはビルドを持たない静的HTMLなので、HTML側は表示用の実値を保持している
（JSが無効でも法令由来の数値が消えないようにするため）。そのぶん同じ数値が
複数ファイルに存在するため、片方だけ更新される事故をこのスクリプトで防ぐ。

  - data/tax-constants.json が唯一の定義元
  - HTML内の該当箇所は定義元から導出した文字列と完全一致しなければならない
  - 基準日ラベル・改正予告の施行日も同様に検証する

使い方: python3 scripts/verify_constants.py
        （公開前に必ず実行する。終了コード0で一致、1で不一致）
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "data/tax-constants.json").read_text(encoding="utf-8"))

failures: list[str] = []
checks = 0


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def need(rel: str, needle: str, label: str) -> None:
    """rel のHTMLに needle が現れることを要求する。"""
    global checks
    checks += 1
    if needle not in read(rel):
        failures.append(f"{rel}: {label} が定義元と一致しない（期待: {needle!r}）")


def man(yen: int) -> str:
    """円 → 「x.y」万円表記（例: 23000 -> 2.3）。"""
    return f"{yen / 10000:.1f}"


# ---------------------------------------------------------------------------
# 1. iDeCo 拠出限度額（現行）
#    記事の表と simulator.html の埋め込みJSONの両方に同じ値が存在する。
# ---------------------------------------------------------------------------
cur = C["ideco"]["current"]
for key, label in (("no_pension", "企業年金なし"), ("with_corporate_pension", "企業年金あり")):
    m_yen = cur[key]["monthly_yen"]
    a_yen = cur[key]["annual_yen"]
    need(
        "articles/ideco-limit-tax.html",
        f"月{man(m_yen)}万円（年間 約{man(a_yen)}万円）",
        f"iDeCo拠出限度額（{label}）",
    )

# simulator.html の sim-data（JSONとして取り出して厳密に比較）
sim_html = read("simulator.html")
m = re.search(r'<script type="application/json" id="sim-data">(.*?)</script>', sim_html, re.S)
checks += 1
if not m:
    failures.append("simulator.html: sim-data が見つからない")
else:
    sim = json.loads(m.group(1))
    expected_limits = {
        "no_pension": {
            "monthly_limit_yen": cur["no_pension"]["monthly_yen"],
            "annual_limit_yen": cur["no_pension"]["annual_yen"],
        },
        "with_pension": {
            "monthly_limit_yen": cur["with_corporate_pension"]["monthly_yen"],
            "annual_limit_yen": cur["with_corporate_pension"]["annual_yen"],
        },
    }
    checks += 1
    if sim.get("ideco_limits") != expected_limits:
        failures.append(
            f"simulator.html: sim-data の ideco_limits が定義元と不一致\n"
            f"    期待: {expected_limits}\n    実際: {sim.get('ideco_limits')}"
        )

    # ふるさと納税の年収別上限（記事の表 と sim-data の二重管理を突合）
    for income, limit in C["furusato"]["limit_single_man_yen"].items():
        bracket = next(
            (b for b in sim.get("income_brackets", []) if b.get("income_man_yen") == int(income)),
            None,
        )
        checks += 1
        if bracket is None:
            failures.append(f"simulator.html: 年収{income}万円のブラケットが無い")
            continue
        actual = bracket.get("furusato_limit_single_man_yen")
        if actual != limit:
            failures.append(
                f"simulator.html: 年収{income}万円の独身上限が定義元と不一致"
                f"（期待 {limit} / 実際 {actual}）"
            )

# ---------------------------------------------------------------------------
# 2. iDeCo 2026-12-01 改正の予告表示
# ---------------------------------------------------------------------------
sc = C["ideco"]["scheduled_change"]
eff = sc["effective_from"]
y, mth, d = eff.split("-")
eff_label = f"{y}年{int(mth)}月{int(d)}日"
for rel in ("articles/ideco-limit-tax.html", "simulator.html"):
    need(rel, eff_label, "iDeCo改正の施行日")
    need(rel, f"月{man(sc['second_insured_monthly_yen'])}万円", "改正後の第2号拠出限度額")

# ---------------------------------------------------------------------------
# 3. NISA 投資枠
# ---------------------------------------------------------------------------
n = C["nisa"]
need("articles/nisa-tsumitate-basics.html", f"{n['tsumitate_annual_man_yen']}万円", "つみたて投資枠")
need("articles/nisa-tsumitate-basics.html", f"{n['growth_annual_man_yen']}万円", "成長投資枠")
need(
    "articles/nisa-tsumitate-basics.html",
    f"{n['lifetime_man_yen']:,}万円",
    "生涯非課税保有限度額",
)
need(
    "articles/nisa-tsumitate-basics.html",
    f"{n['growth_within_lifetime_man_yen']:,}万円",
    "生涯枠のうち成長投資枠",
)

# ---------------------------------------------------------------------------
# 4. ふるさと納税（記事の表・自己負担額・ワンストップ特例）
# ---------------------------------------------------------------------------
f = C["furusato"]
need("articles/furusato-nozei-limit.html", f"{f['self_burden_yen']:,}円", "自己負担額")
need(
    "articles/furusato-nozei-limit.html",
    f"年間{f['one_stop_max_municipalities']}自治体以内",
    "ワンストップ特例の自治体数",
)
for income, limit in f["limit_single_man_yen"].items():
    need(
        "articles/furusato-nozei-limit.html",
        f"<td>{income}万円</td><td>約{limit}万円</td>",
        f"ふるさと納税上限（年収{income}万円・独身）",
    )

# ---------------------------------------------------------------------------
# 5. 所得税率の例示
# ---------------------------------------------------------------------------
it = C["income_tax"]
need("articles/ideco-limit-tax.html", f"{it['example_rate_percent']}%", "所得税率の例示")
need(
    "articles/ideco-limit-tax.html",
    f"年間{it['example_annual_contribution_man_yen']}万円を拠出",
    "拠出額の例示",
)

# ---------------------------------------------------------------------------
# 6. 基準日ラベル（制度数値を載せる全ページに表示されていること）
# ---------------------------------------------------------------------------
for rel in (
    "articles/ideco-limit-tax.html",
    "articles/nisa-tsumitate-basics.html",
    "articles/furusato-nozei-limit.html",
    "simulator.html",
):
    need(rel, C["as_of_label"], "基準日ラベル")

# ---------------------------------------------------------------------------
print(f"検証項目数: {checks}")
if failures:
    print(f"\n✘ 不一致 {len(failures)} 件:\n")
    for msg in failures:
        print(f"  - {msg}")
    sys.exit(1)
print("✔ すべての制度数値が data/tax-constants.json と一致")
