#!/usr/bin/env python3
"""
AI/LLM ニュース収集スクリプト
RSSフィードから最新記事を取得し docs/news.html を生成します。
"""

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import html
import sys

FEEDS = [
    {"category": "論文 - AI全般",    "name": "ArXiv cs.AI", "url": "https://arxiv.org/rss/cs.AI"},
    {"category": "論文 - 機械学習",  "name": "ArXiv cs.LG", "url": "https://arxiv.org/rss/cs.LG"},
    {"category": "論文 - 言語処理",  "name": "ArXiv cs.CL", "url": "https://arxiv.org/rss/cs.CL"},
    {"category": "企業ブログ",       "name": "Anthropic",   "url": "https://www.anthropic.com/rss.xml"},
    {"category": "企業ブログ",       "name": "Meta AI",     "url": "https://ai.meta.com/blog/rss/"},
    {"category": "企業ブログ",       "name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml"},
    {"category": "AI全般ニュース",   "name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"category": "コンペティション", "name": "Kaggle Blog", "url": "https://medium.com/feed/kaggle-blog"},
]

MAX_ITEMS_PER_FEED = 10


def fetch_feed(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}", file=sys.stderr)
        return None


def parse_feed(data: bytes, source_name: str) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        print(f"  [WARN] XML parse error for {source_name}: {e}", file=sys.stderr)
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # RSS 2.0
    for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or item.findtext("summary") or "").strip()
        date  = (item.findtext("pubDate") or item.findtext("dc:date", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}) or "").strip()
        items.append({"title": title, "link": link, "description": desc, "date": date, "source": source_name})

    # Atom
    if not items:
        for entry in root.findall("atom:entry", ns)[:MAX_ITEMS_PER_FEED]:
            title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
            link_el = entry.find("atom:link", ns)
            link  = (link_el.get("href") if link_el is not None else "") or ""
            desc  = (entry.findtext("atom:summary", namespaces=ns) or entry.findtext("atom:content", namespaces=ns) or "").strip()
            date  = (entry.findtext("atom:updated", namespaces=ns) or entry.findtext("atom:published", namespaces=ns) or "").strip()
            items.append({"title": title, "link": link, "description": desc, "date": date, "source": source_name})

    return items


def strip_tags(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())[:300]


def build_html(categories: dict[str, list[dict]], generated_at: str) -> str:
    category_nav = "\n".join(
        f'<a href="#cat-{i}">{html.escape(cat)}</a>'
        for i, cat in enumerate(categories)
    )

    if not any(categories.values()):
        empty_notice = """
        <section>
          <div style="text-align:center;padding:4rem 1rem;color:#64748b;">
            <p style="font-size:2rem;margin-bottom:1rem;">📡</p>
            <p style="font-size:1.1rem;margin-bottom:.5rem;">ニュースを取得できませんでした</p>
            <p style="font-size:.85rem;">ネットワーク接続を確認し、<code>python scripts/collect_news.py</code> を再実行してください。</p>
          </div>
        </section>"""
        return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI/LLM ニュースダッシュボード</title>
<style>body{{background:#0f1117;color:#e2e8f0;font-family:-apple-system,sans-serif;}}
header{{background:#1a1f2e;padding:2rem;border-bottom:1px solid #2d3748;}}
h1{{color:#a78bfa;}}p{{color:#94a3b8;margin-top:.4rem;font-size:.9rem;}}
code{{background:#2d3748;padding:.1rem .4rem;border-radius:4px;color:#7dd3fc;}}</style></head>
<body><header><h1>AI/LLM ニュースダッシュボード</h1>
<p>最終更新試行: {html.escape(generated_at)}</p></header>
<main>{empty_notice}</main></body></html>"""

    sections = ""
    for i, (cat, items) in enumerate(categories.items()):
        cards = ""
        for item in items:
            title = html.escape(item["title"] or "(no title)")
            link  = html.escape(item["link"])
            desc  = html.escape(strip_tags(item["description"]))
            date  = html.escape(item["date"][:30] if item["date"] else "")
            source = html.escape(item["source"])
            cards += f"""
            <article class="card">
              <div class="card-meta"><span class="source">{source}</span><span class="date">{date}</span></div>
              <h3><a href="{link}" target="_blank" rel="noopener">{title}</a></h3>
              <p class="desc">{desc}</p>
            </article>"""
        sections += f"""
        <section id="cat-{i}">
          <h2>{html.escape(cat)}</h2>
          <div class="grid">{cards}
          </div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI/LLM ニュースダッシュボード</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #0f1117; color: #e2e8f0; min-height: 100vh; }}
    header {{ background: linear-gradient(135deg, #1a1f2e 0%, #16213e 100%);
              padding: 2rem; border-bottom: 1px solid #2d3748; }}
    header h1 {{ font-size: 1.8rem; font-weight: 700; color: #a78bfa; }}
    header p  {{ color: #94a3b8; margin-top: .4rem; font-size: .9rem; }}
    nav {{ display: flex; flex-wrap: wrap; gap: .5rem; padding: 1rem 2rem;
           background: #1a1f2e; border-bottom: 1px solid #2d3748; position: sticky; top: 0; z-index: 10; }}
    nav a {{ color: #7dd3fc; text-decoration: none; font-size: .85rem; padding: .3rem .7rem;
             border-radius: 999px; border: 1px solid #2d3748; transition: background .2s; }}
    nav a:hover {{ background: #2d3748; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }}
    section {{ margin-bottom: 3rem; }}
    section h2 {{ font-size: 1.2rem; color: #a78bfa; border-left: 3px solid #7c3aed;
                  padding-left: .75rem; margin-bottom: 1.25rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1rem; }}
    .card {{ background: #1a1f2e; border: 1px solid #2d3748; border-radius: 10px;
             padding: 1.1rem; transition: border-color .2s, transform .2s; }}
    .card:hover {{ border-color: #7c3aed; transform: translateY(-2px); }}
    .card-meta {{ display: flex; justify-content: space-between; font-size: .75rem;
                  color: #64748b; margin-bottom: .5rem; }}
    .source {{ color: #7dd3fc; font-weight: 600; }}
    .card h3 {{ font-size: .95rem; line-height: 1.4; margin-bottom: .5rem; }}
    .card h3 a {{ color: #e2e8f0; text-decoration: none; }}
    .card h3 a:hover {{ color: #a78bfa; }}
    .desc {{ font-size: .82rem; color: #94a3b8; line-height: 1.5; }}
    footer {{ text-align: center; padding: 2rem; color: #475569; font-size: .8rem;
              border-top: 1px solid #2d3748; }}
  </style>
</head>
<body>
  <header>
    <h1>AI/LLM ニュースダッシュボード</h1>
    <p>最終更新: {html.escape(generated_at)} &nbsp;|&nbsp; ArXiv / GAFA企業ブログ / Kaggle などから自動収集</p>
  </header>
  <nav>{category_nav}</nav>
  <main>{sections}
  </main>
  <footer>Generated by scripts/collect_news.py &mdash; sturdy-octo-happiness</footer>
</body>
</html>"""


def main():
    print("ニュースを収集中...")
    categories: dict[str, list[dict]] = {}

    for feed in FEEDS:
        print(f"  取得: {feed['name']} ({feed['url']})")
        data = fetch_feed(feed["url"])
        if data is None:
            continue
        items = parse_feed(data, feed["name"])
        cat = feed["category"]
        categories.setdefault(cat, []).extend(items)
        print(f"    -> {len(items)} 件取得")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_content = build_html(categories, generated_at)

    out_path = Path(__file__).parent.parent / "docs" / "news.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"\n完了: {out_path} を生成しました ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
