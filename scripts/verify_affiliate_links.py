#!/usr/bin/env python3
"""公開HTML内のアフィリエイトリンクとPR表記を検証する。

本サイトはビルドを持たない静的HTMLで、アフィリエイトリンクは手書きで貼る。
そのため「トラッキングIDの取り違え」「rel/target の付け忘れ」「PR表記の欠落」
「他のリンクを消してしまう事故」は誰にも気づかれないまま公開されうる。
verify_constants.py と同じ方針で、公開前に機械的に止められるようにする。

  - 各リンクは ASP のトラッキング識別子まで含めて完全一致を要求する
  - 景表法・ステマ規制の観点から必須の表記（PRバナー / 各リンクの「（PR）」）を要求する
  - 既存リンクの回帰（新しいリンクを足したときに古いものを消していないか）を要求する

使い方: python3 scripts/verify_affiliate_links.py
        （公開前に必ず実行する。終了コード0で合格、1で不合格）
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

failures: list[str] = []
checks = 0

# ---------------------------------------------------------------------------
# 掲載中のアフィリエイトリンク（ASP / 広告主 / トラッキング識別子 / 掲載ページ）
#   識別子は「取り違えたら別の広告主に成果が付く」箇所なので、URL断片ごと固定する。
# ---------------------------------------------------------------------------
LINKS = [
    {
        "label": "楽天証券NISA（TGアフィリエイト リンクID928 / MID738）",
        "tracking": "/928/738/317425_398282",
        "host": "ad2.trafficgate.net",
        "pages": ["articles/nisa-tsumitate-basics.html", "simulator.html"],
        # TG提供素材そのままの属性。素材は改変禁止（規約 第9条1項(2)）のため、
        # rel/target を勝手に足し引きしないこと。
        "attrs": ['target="_blank"', 'rel="nofollow"'],
        "anchor_text": "NISA訴求汎用",
    },
    {
        "label": "マネックス証券NISA（アクセストレード rk=010072vk00ovpf）",
        "tracking": "rk=010072vk00ovpf",
        "host": "h.accesstrade.net",
        "pages": ["articles/nisa-tsumitate-basics.html", "simulator.html"],
        "attrs": ['rel="nofollow"'],
        "anchor_text": "マネックス証券",
    },
    {
        "label": "松井証券iDeCo（A8.net a8mat=4B8092+FG2Y3U+3XCC+BXIYQ）",
        "tracking": "a8mat=4B8092+FG2Y3U+3XCC+BXIYQ",
        "host": "px.a8.net",
        "pages": ["simulator.html"],
        "attrs": ['rel="nofollow sponsored"'],
        "anchor_text": "松井証券ではじめるiDeCo",
    },
]

# アフィリエイトリンクを載せるページに必須のPRバナー（2026-07-28に文言統一済み）
PR_BANNER = "本ページはプロモーションが含まれます。"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(rel: str, needle: str, label: str) -> None:
    global checks
    checks += 1
    if needle not in read(rel):
        failures.append(f"{rel}: {label}（期待: {needle!r}）")


def anchor_for(html: str, tracking: str) -> str | None:
    """tracking を href に含む <a ...> の開始タグを返す。"""
    for m in re.finditer(r"<a\s[^>]*>", html):
        if tracking in m.group(0):
            return m.group(0)
    return None


# ---------------------------------------------------------------------------
# 1. 各リンクが掲載ページに存在し、必須属性とPR表記を伴っていること
# ---------------------------------------------------------------------------
for link in LINKS:
    for rel in link["pages"]:
        html = read(rel)

        require(rel, link["tracking"], f"{link['label']} のトラッキング識別子が無い")
        require(rel, link["host"], f"{link['label']} の遷移先ホストが無い")
        require(rel, link["anchor_text"], f"{link['label']} のリンク文言が無い")

        # 属性は「そのリンクのaタグ自身」に付いていることまで見る。
        # ページ内の別のリンクが持っているだけでは通さない。
        checks += 1
        tag = anchor_for(html, link["tracking"])
        if tag is None:
            failures.append(f"{rel}: {link['label']} の <a> タグが見つからない")
        else:
            for attr in link["attrs"]:
                checks += 1
                if attr not in tag:
                    failures.append(
                        f"{rel}: {link['label']} の <a> に {attr} が無い（実際: {tag}）"
                    )

# ---------------------------------------------------------------------------
# 2. PR表記
#    - ページ冒頭のPRバナー
#    - 各アフィリエイトリンクの近傍の「（PR）」
#      （リンク単位の表示が無いと、どのリンクが広告か読者に伝わらない）
# ---------------------------------------------------------------------------
AFFILIATE_PAGES = sorted({rel for link in LINKS for rel in link["pages"]})

for rel in AFFILIATE_PAGES:
    require(rel, PR_BANNER, "PRバナーが無い（2026-07-28統一の文言）")

    html = read(rel)
    for link in LINKS:
        if rel not in link["pages"]:
            continue
        checks += 1
        # トラッキング識別子の出現位置から後ろ300文字以内に「（PR）」があること。
        # 計測用imgやliの閉じタグを挟むため、単純な隣接一致にはしない。
        pos = html.find(link["tracking"])
        if pos == -1 or "（PR）" not in html[pos : pos + 300]:
            failures.append(f"{rel}: {link['label']} の近傍に「（PR）」表記が無い")

# ---------------------------------------------------------------------------
# 3. 広告主の表記ゆれ・取り違えが無いこと
#    リンク先の広告主名が本文に出ていること（読者が遷移先を判断できる状態か）
# ---------------------------------------------------------------------------
for rel, advertisers in (
    ("articles/nisa-tsumitate-basics.html", ["マネックス証券", "楽天証券"]),
    ("simulator.html", ["松井証券", "マネックス証券", "楽天証券"]),
):
    for name in advertisers:
        require(rel, name, f"広告主名「{name}」が本文に無い")

# ---------------------------------------------------------------------------
# 4. プライバシーポリシーの参加ASP一覧が実態と一致していること
#    リンクを足したのに一覧を更新し忘れると、開示内容が事実と食い違う。
# ---------------------------------------------------------------------------
for asp in ("A8.net", "アクセストレード", "TGアフィリエイト"):
    require("privacy.html", asp, f"参加ASP「{asp}」がプライバシーポリシーに無い")

# ---------------------------------------------------------------------------
print(f"検証項目数: {checks}")
if failures:
    print(f"\n✘ 不合格 {len(failures)} 件:\n")
    for msg in failures:
        print(f"  - {msg}")
    sys.exit(1)
print("✔ アフィリエイトリンクとPR表記はすべて期待どおり")
