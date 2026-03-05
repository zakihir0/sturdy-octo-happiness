"""
scripts/fetch_arxiv.py
ArXiv cs.AI RSS から最新N件の記事全文を取得し
docs/arxiv-raw-YYYY-MM-DD.json として保存する。
要約は Claude Code が別途行う。
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timezone, datetime
from pathlib import Path

RSS_URL = "https://arxiv.org/rss/cs.AI"
FETCH_COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 2
DOCS_DIR = Path(__file__).parent.parent / "docs"
MAX_ARTICLE_CHARS = 8000  # 記事テキストの最大文字数


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def fetch_rss(url: str) -> list[dict]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; ArXivFetcher/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for item in channel.findall("item")[:FETCH_COUNT]:
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or "").strip()
        # HTMLタグを除去してプレーンテキスト化
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = html.unescape(" ".join(desc.split()))
        abs_id = link.split("/abs/")[-1] if "/abs/" in link else ""
        items.append({"title": title, "link": link, "rss_summary": desc, "abs_id": abs_id})
    return items


def fetch_article_text(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; ArXivFetcher/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read(400_000)
        charset = "utf-8"
        ct = resp.headers.get("Content-Type", "")
        if "charset=" in ct:
            charset = ct.split("charset=")[-1].split(";")[0].strip()
        body = raw.decode(charset, errors="replace")
    body = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    return " ".join(body.split())[:MAX_ARTICLE_CHARS]


def main() -> None:
    log(f"ArXiv cs.AI RSS 取得中 ({FETCH_COUNT} 件)")
    articles = fetch_rss(RSS_URL)
    if not articles:
        log("ERROR: 記事を取得できませんでした")
        sys.exit(1)
    log(f"{len(articles)} 件取得完了")

    for i, art in enumerate(articles, 1):
        log(f"[{i}/{len(articles)}] 記事テキスト取得: {art['title'][:70]}")
        try:
            art["article_text"] = fetch_article_text(art["link"])
            log(f"  → {len(art['article_text'])} 文字")
        except Exception as e:
            log(f"  → 取得失敗（RSS概要のみ使用）: {e}")
            art["article_text"] = ""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = DOCS_DIR / f"arxiv-raw-{today}.json"
    out_path.write_text(
        json.dumps({"fetched_at": today, "source": RSS_URL, "articles": articles},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"保存完了: {out_path}")


if __name__ == "__main__":
    main()
