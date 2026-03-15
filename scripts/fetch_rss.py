#!/usr/bin/env python3
"""RSS フィードを取得して新着記事を JSON 配列として stdout に出力する。"""
import glob
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

RSS_SOURCES = [
    ("ArXiv cs.AI",     "論文 - AI全般",   "https://arxiv.org/rss/cs.AI"),
    ("ArXiv cs.LG",     "論文 - 機械学習",  "https://arxiv.org/rss/cs.LG"),
    ("ArXiv cs.CL",     "論文 - 言語処理",  "https://arxiv.org/rss/cs.CL"),
    ("Anthropic",       "企業ブログ",      "https://www.anthropic.com/rss.xml"),
    ("Meta AI",         "企業ブログ",      "https://ai.meta.com/blog/rss/"),
    ("Google DeepMind", "企業ブログ",      "https://deepmind.google/blog/rss.xml"),
    ("TechCrunch AI",   "AI全般ニュース",   "https://techcrunch.com/category/artificial-intelligence/feed/"),
]
MAX_PER_FEED = 10


def load_existing_urls() -> set:
    urls = set()
    for path in glob.glob("docs/news/*.jsonl"):
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        if "link" in d:
                            urls.add(d["link"])
        except Exception:
            pass
    return urls


def fetch_feed(source: str, category: str, url: str, existing: set, fetched_at: str) -> list:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        articles = []
        for item in root.findall(".//item")[:MAX_PER_FEED]:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            date  = (item.findtext("pubDate") or "").strip()
            if link and link not in existing:
                articles.append({
                    "title": title, "link": link, "description": desc,
                    "date": date, "source": source, "category": category,
                    "fetched_at": fetched_at,
                })
                existing.add(link)
        return articles
    except Exception as e:
        print(f"[WARN] {source} 取得失敗: {e}", file=sys.stderr)
        return []


def main():
    existing = load_existing_urls()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_articles = []
    for source, category, url in RSS_SOURCES:
        all_articles.extend(fetch_feed(source, category, url, existing, fetched_at))
    print(json.dumps(all_articles, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
