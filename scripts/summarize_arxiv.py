"""
scripts/summarize_arxiv.py
ArXiv cs.AI RSS から最新2件を取得し、Claude が記事全文を読んで日本語要約した
Markdown ファイルを docs/arxiv-summary-YYYY-MM-DD.md として出力する。
"""

from __future__ import annotations

import os
import re
import html
import sys
import traceback
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
RSS_URL = "https://arxiv.org/rss/cs.AI"
FETCH_COUNT = 2
DOCS_DIR = Path(__file__).parent.parent / "docs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_rss(url: str) -> list[dict]:
    """RSS を取得して [{title, link, summary, abs_id}] を返す（最大 FETCH_COUNT 件）。"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ArXivSummarizer/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    items = []
    channel = root.find("channel")
    if channel is None:
        return items
    for item in channel.findall("item")[:FETCH_COUNT]:
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or "").strip()
        # ArXiv abstract ID (例: 2506.12345)
        abs_id = link.split("/abs/")[-1] if "/abs/" in link else ""
        items.append({"title": title, "link": link, "rss_summary": desc, "abs_id": abs_id})
    return items


def fetch_article_text(url: str) -> str:
    """記事URLのHTMLを取得してプレーンテキスト化（最大5000文字）。"""
    if not url:
        return ""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ArXivSummarizer/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read(300_000)
        charset = "utf-8"
        ct = resp.headers.get("Content-Type", "")
        if "charset=" in ct:
            charset = ct.split("charset=")[-1].split(";")[0].strip()
        body = raw.decode(charset, errors="replace")
    body = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    return " ".join(body.split())[:5000]


def summarize(title: str, article_text: str, rss_summary: str) -> dict:
    """Claude Haiku で詳細な日本語要約を生成する。"""
    if not _ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY が設定されていません")

    content = article_text.strip() or rss_summary.strip() or title
    source_label = "記事本文" if article_text.strip() else "概要（RSS）"

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 詳細要約
    detail_prompt = (
        f"以下のArXiv論文のタイトルと{source_label}を読み、日本語で詳しく要約してください。\n"
        "以下の形式で回答してください：\n"
        "【概要】研究の背景・目的を2〜3文で\n"
        "【手法】提案手法を2〜3文で\n"
        "【成果】主な実験結果・貢献を2〜3文で\n\n"
        f"タイトル: {title}\n{source_label}: {content[:4000]}"
    )
    detail_msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": detail_prompt}],
    )
    detail = detail_msg.content[0].text.strip()

    # 一言要約
    oneliner_prompt = (
        f"以下の論文タイトルと概要から、日本語で1文（50字以内）のキャッチコピーを作ってください。\n"
        f"タイトル: {title}\n概要: {content[:500]}"
    )
    oneliner_msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": oneliner_prompt}],
    )
    oneliner = oneliner_msg.content[0].text.strip()

    return {"detail": detail, "oneliner": oneliner, "source": source_label}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log(f"ArXiv cs.AI RSS 取得中: {RSS_URL}")
    articles = fetch_rss(RSS_URL)
    if not articles:
        log("ERROR: 記事を取得できませんでした")
        sys.exit(1)
    log(f"{len(articles)} 件取得")

    results = []
    for i, art in enumerate(articles, 1):
        log(f"\n[{i}/{len(articles)}] {art['title'][:80]}")

        # 記事全文取得
        article_text = ""
        try:
            log(f"  → 記事ページ取得: {art['link']}")
            article_text = fetch_article_text(art["link"])
            log(f"  → {len(article_text)} 文字取得")
        except Exception as e:
            log(f"  → 取得失敗（RSS概要にフォールバック）: {e}")

        # Claude 要約
        try:
            log("  → Claude で要約中...")
            summary = summarize(art["title"], article_text, art["rss_summary"])
            results.append({**art, **summary})
            log(f"  → 要約完了（ソース: {summary['source']}）")
        except Exception as e:
            log(f"  → 要約失敗: {e}")
            traceback.print_exc()
            results.append({**art, "detail": "（要約失敗）", "oneliner": "", "source": "N/A"})

    # Markdown 生成
    today = date.today().isoformat()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_DIR / f"arxiv-summary-{today}.md"

    lines = [
        f"# ArXiv cs.AI 最新論文 要約 ({today})",
        "",
        f"> ソース: {RSS_URL}  ",
        f"> 取得件数: {len(results)} 件  ",
        f"> 要約モデル: claude-haiku-4-5-20251001  ",
        "",
        "---",
        "",
    ]

    for i, r in enumerate(results, 1):
        lines += [
            f"## {i}. {r['title']}",
            "",
        ]
        if r.get("oneliner"):
            lines += [f"> **一言まとめ**: {r['oneliner']}", ""]
        lines += [
            f"**ArXiv リンク**: [{r['link']}]({r['link']})  ",
            f"**要約ソース**: {r['source']}",
            "",
            r["detail"],
            "",
            "---",
            "",
        ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    log(f"\n✅ 出力完了: {out_path}")


if __name__ == "__main__":
    main()
