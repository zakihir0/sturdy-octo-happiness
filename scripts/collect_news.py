#!/usr/bin/env python3
"""
AI/LLM ニュース収集スクリプト

RSSフィードから最新記事を取得し、docs/news_data.json に追記しながら
docs/news.html を再生成します。失敗内容は logs/collect_news.log に記録します。
日付別に docs/news/YYYY-MM-DD.jsonl と docs/news/YYYY-MM-DD.md も出力します。
"""

import html
import json
import os
import re
import sys
import traceback
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MAX_TRANSLATE_PER_RUN = 30  # 1回の実行で翻訳する最大件数（コスト抑制）

ROOT       = Path(__file__).parent.parent
DATA_FILE  = ROOT / "docs" / "news_data.json"
HTML_FILE  = ROOT / "docs" / "news.html"
INDEX_FILE = ROOT / "docs" / "index.html"
NEWS_DIR   = ROOT / "docs" / "news"
LOG_FILE   = ROOT / "logs" / "collect_news.log"

FEEDS = [
    {"category": "論文 - AI全般",    "name": "ArXiv cs.AI",      "url": "https://arxiv.org/rss/cs.AI"},
    {"category": "論文 - 機械学習",  "name": "ArXiv cs.LG",      "url": "https://arxiv.org/rss/cs.LG"},
    {"category": "論文 - 言語処理",  "name": "ArXiv cs.CL",      "url": "https://arxiv.org/rss/cs.CL"},
    {"category": "企業ブログ",       "name": "Anthropic",         "url": "https://www.anthropic.com/rss.xml"},
    {"category": "企業ブログ",       "name": "Meta AI",           "url": "https://ai.meta.com/blog/rss/"},
    {"category": "企業ブログ",       "name": "Google DeepMind",   "url": "https://deepmind.google/blog/rss.xml"},
    {"category": "AI全般ニュース",   "name": "TechCrunch AI",     "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"category": "コンペティション", "name": "Kaggle Blog",       "url": "https://medium.com/feed/kaggle-blog"},
]

MAX_ITEMS_PER_FEED = 10


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(level: str, msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{now}] [{level}] {msg}"
    stream = sys.stderr if level in ("WARN", "ERROR") else sys.stdout
    print(line, file=stream)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Article full-text fetch & Japanese summarization via Claude API
# ---------------------------------------------------------------------------

def fetch_article_text(url: str) -> str:
    if not url:
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read(200_000)
            charset = "utf-8"
            ct = resp.headers.get("Content-Type", "")
            if "charset=" in ct:
                charset = ct.split("charset=")[-1].split(";")[0].strip()
            body = raw.decode(charset, errors="replace")
        body = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", body)
        body = re.sub(r"<[^>]+>", " ", body)
        body = html.unescape(body)
        return " ".join(body.split())[:4000]
    except Exception as e:
        reason = traceback.format_exception_only(type(e), e)[-1].strip()
        log("WARN", f"記事取得失敗 {url[:80]} | {reason}")
        return ""


def summarize_in_japanese(title: str, description: str, article_text: str = "") -> str | None:
    if not _ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        return None
    content = (article_text.strip() or description.strip() or title.strip())
    if not content:
        return None
    source_label = "記事本文" if article_text.strip() else "概要"
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = (
            f"以下のAI/機械学習に関する記事のタイトルと{source_label}を読み、"
            "日本語で2〜3文（150字以内）に要約してください。"
            "専門用語はそのまま使い、研究内容・手法・成果の要点を簡潔に伝えてください。\n\n"
            f"タイトル: {title}\n{source_label}: {content[:3000]}"
        )
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        reason = traceback.format_exception_only(type(e), e)[-1].strip()
        log("WARN", f"日本語要約失敗: {reason}")
        return None


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_feed(feed: dict) -> bytes | None:
    url = feed["url"]
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            log("INFO", f"OK   {feed['name']} ({len(data):,} bytes) <- {url}")
            return data
    except Exception as e:
        reason = traceback.format_exception_only(type(e), e)[-1].strip()
        log("WARN", f"FAIL {feed['name']} <- {url} | 原因: {reason}")
        return None


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def parse_feed(data: bytes, feed: dict) -> list[dict]:
    source_name = feed["name"]
    category    = feed["category"]
    items: list[dict] = []

    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        log("WARN", f"XML解析エラー ({source_name}): {e}")
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    fetched_at = datetime.now(timezone.utc).isoformat()

    def make_item(title, link, desc, date):
        return {
            "title":       (title or "").strip(),
            "link":        (link  or "").strip(),
            "description": (desc  or "").strip(),
            "date":        (date  or "").strip(),
            "source":      source_name,
            "category":    category,
            "fetched_at":  fetched_at,
        }

    for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
        dc_ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        items.append(make_item(
            item.findtext("title"),
            item.findtext("link"),
            item.findtext("description") or item.findtext("summary"),
            item.findtext("pubDate") or item.findtext("dc:date", namespaces=dc_ns),
        ))

    if not items:
        for entry in root.findall("atom:entry", ns)[:MAX_ITEMS_PER_FEED]:
            link_el = entry.find("atom:link", ns)
            items.append(make_item(
                entry.findtext("atom:title",   namespaces=ns),
                link_el.get("href") if link_el is not None else "",
                entry.findtext("atom:summary", namespaces=ns) or entry.findtext("atom:content", namespaces=ns),
                entry.findtext("atom:updated", namespaces=ns) or entry.findtext("atom:published", namespaces=ns),
            ))

    return items


# ---------------------------------------------------------------------------
# Persistent storage (JSON)
# ---------------------------------------------------------------------------

def load_existing() -> list[dict]:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log("WARN", f"既存データの読み込み失敗: {e} — 空データで開始します")
    return []


def merge_articles(existing: list[dict], new_items: list[dict]) -> tuple[list[dict], int]:
    seen = {a["link"] for a in existing if a.get("link")}
    added = 0
    for item in new_items:
        if item["link"] and item["link"] not in seen:
            existing.append(item)
            seen.add(item["link"])
            added += 1
    existing.sort(key=lambda a: a.get("fetched_at", ""), reverse=True)
    return existing, added


def save_data(articles: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Daily JSONL + Markdown output
# ---------------------------------------------------------------------------

def save_daily_files(articles: list[dict], today_str: str) -> None:
    """今日収集した記事を JSONL と Markdown で docs/news/ に保存する。"""
    NEWS_DIR.mkdir(parents=True, exist_ok=True)

    today_articles = [a for a in articles if a.get("fetched_at", "")[:10] == today_str]
    if not today_articles:
        log("INFO", "今日の新着記事なし — daily files スキップ")
        return

    # JSONL（1行1記事）
    jsonl_path = NEWS_DIR / f"{today_str}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for a in today_articles:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    log("INFO", f"JSONL保存: {jsonl_path} ({len(today_articles)} 件)")

    # Markdown
    md_path = NEWS_DIR / f"{today_str}.md"
    categories: dict[str, list[dict]] = {}
    for a in today_articles:
        categories.setdefault(a.get("category", "その他"), []).append(a)

    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# AI/LLM ニュース {today_str}\n\n")
        f.write(f"収集件数: {len(today_articles)} 件\n\n")
        for cat, items in categories.items():
            f.write(f"\n## {cat}\n\n")
            for item in items:
                title      = item.get("title", "(no title)")
                link       = item.get("link", "")
                summary_ja = item.get("summary_ja", "")
                date_str   = (item.get("date") or "")[:30]
                source     = item.get("source", "")
                f.write(f"### [{title}]({link})\n\n")
                if date_str:
                    f.write(f"**日付:** {date_str}  \n")
                if source:
                    f.write(f"**ソース:** {source}  \n\n")
                if summary_ja:
                    f.write(f"{summary_ja}\n\n")
                f.write("---\n\n")
    log("INFO", f"MD保存: {md_path}")


# ---------------------------------------------------------------------------
# Archive index.html
# ---------------------------------------------------------------------------

def build_index_html(generated_at: str) -> str:
    """docs/news/ の日付別ファイルを一覧するアーカイブページを生成する。"""
    NEWS_DIR.mkdir(parents=True, exist_ok=True)

    dates = sorted(
        set(f.stem for f in NEWS_DIR.glob("*.md")) |
        set(f.stem for f in NEWS_DIR.glob("*.jsonl")),
        reverse=True,
    )

    rows = ""
    for d in dates:
        md_link    = f'<a href="news/{d}.md">Markdown</a>'    if (NEWS_DIR / f"{d}.md").exists()    else "—"
        jsonl_link = f'<a href="news/{d}.jsonl">JSONL</a>'    if (NEWS_DIR / f"{d}.jsonl").exists() else "—"
        rows += f"<tr><td>{d}</td><td>{md_link}</td><td>{jsonl_link}</td></tr>\n"

    table = (
        f"<table><thead><tr><th>日付</th><th>Markdown</th><th>JSONL</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        if rows else "<p class='empty'>まだ記録がありません。</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI/LLM ニュース アーカイブ</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #0f1117; color: #e2e8f0; min-height: 100vh; }}
    header {{ background: linear-gradient(135deg, #1a1f2e 0%, #16213e 100%);
              padding: 2rem; border-bottom: 1px solid #2d3748; }}
    header h1 {{ font-size: 1.8rem; font-weight: 700; color: #a78bfa; }}
    header p  {{ color: #94a3b8; margin-top: .4rem; font-size: .85rem; }}
    .cta {{ display: inline-block; margin-top: 1rem; padding: .5rem 1.2rem;
            background: #7c3aed; color: #fff; border-radius: 6px; text-decoration: none;
            font-size: .9rem; transition: background .2s; }}
    .cta:hover {{ background: #6d28d9; }}
    main {{ max-width: 760px; margin: 2.5rem auto; padding: 0 1rem; }}
    h2   {{ font-size: 1.15rem; color: #a78bfa; border-left: 3px solid #7c3aed;
            padding-left: .75rem; margin-bottom: 1.25rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: .9rem; }}
    th, td {{ padding: .65rem 1rem; text-align: left; border-bottom: 1px solid #2d3748; }}
    th {{ background: #1a1f2e; color: #94a3b8; font-weight: 600; }}
    tr:hover td {{ background: #1a1f2e; }}
    td a {{ color: #7dd3fc; text-decoration: none; margin-right: .6rem; }}
    td a:hover {{ text-decoration: underline; }}
    .empty {{ color: #64748b; padding: 1rem 0; }}
    footer {{ text-align: center; padding: 2rem; color: #475569; font-size: .78rem;
              border-top: 1px solid #2d3748; margin-top: 3rem; }}
    code {{ background: #2d3748; padding: .1rem .4rem; border-radius: 4px; color: #7dd3fc; }}
  </style>
</head>
<body>
  <header>
    <h1>AI/LLM ニュース アーカイブ</h1>
    <p>最終更新: {html.escape(generated_at)}&nbsp;|&nbsp;毎日 JST 10:00 自動更新</p>
    <a href="news.html" class="cta">最新ダッシュボードを見る &rarr;</a>
  </header>
  <main>
    <h2>日付別アーカイブ</h2>
    {table}
  </main>
  <footer>
    Powered by Claude API + GitHub Actions&nbsp;|&nbsp;
    データ形式: <code>docs/news/YYYY-MM-DD.jsonl</code> &nbsp;/&nbsp; <code>docs/news/YYYY-MM-DD.md</code>
  </footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML generation (dashboard)
# ---------------------------------------------------------------------------

def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())[:300]


def build_html(articles: list[dict], generated_at: str, run_stats: dict) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    categories: dict[str, list[dict]] = {}
    for a in articles:
        categories.setdefault(a.get("category", "その他"), []).append(a)

    success = run_stats.get("success", 0)
    failure = run_stats.get("failure", 0)
    added   = run_stats.get("added", 0)
    total   = run_stats.get("total", len(articles))

    stats_html = (
        f'<span class="stat ok">✓ 取得成功 {success} フィード</span>'
        f'<span class="stat ng">✗ 取得失敗 {failure} フィード</span>'
        f'<span class="stat add">+ 今回追加 {added} 件</span>'
        f'<span class="stat tot">合計 {total} 件蓄積</span>'
    )

    nav = "\n".join(
        f'<a href="#cat-{i}">{html.escape(cat)} <small>({len(items)})</small></a>'
        for i, (cat, items) in enumerate(categories.items())
    )

    sections = ""
    if not articles:
        sections = """<section><div class="empty">
          <p style="font-size:2rem">📡</p>
          <p>ニュースがまだ蓄積されていません。</p>
          <p><code>python scripts/collect_news.py</code> を再実行してください。</p>
        </div></section>"""
    else:
        for i, (cat, items) in enumerate(categories.items()):
            cards = ""
            for item in items:
                title      = html.escape(item.get("title") or "(no title)")
                link       = html.escape(item.get("link", ""))
                desc       = html.escape(strip_tags(item.get("description", "")))
                summary_ja = html.escape(item.get("summary_ja", ""))
                date       = html.escape((item.get("date") or "")[:30])
                source     = html.escape(item.get("source", ""))
                fetched_at = item.get("fetched_at", "")[:10]
                is_new     = fetched_at == today
                new_badge  = '<span class="badge-new">NEW</span>' if is_new else ""
                summary_block = (
                    f'<p class="summary-ja">{summary_ja}</p>'
                    if summary_ja else
                    f'<p class="desc">{desc}</p>'
                )
                cards += f"""
              <article class="card{' card-new' if is_new else ''}">
                <div class="card-meta">
                  <span class="source">{source}</span>
                  <span class="date">{date}</span>
                </div>
                <h3>{new_badge}<a href="{link}" target="_blank" rel="noopener">{title}</a></h3>
                {summary_block}
                <div class="fetched">収集日: {fetched_at}</div>
              </article>"""
            sections += f"""
          <section id="cat-{i}">
            <h2>{html.escape(cat)} <span class="count">{len(items)}件</span></h2>
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
    header p  {{ color: #94a3b8; margin-top: .4rem; font-size: .85rem; }}
    .archive-link {{ display: inline-block; margin-top: .8rem; color: #7dd3fc;
                     font-size: .85rem; text-decoration: none; }}
    .archive-link:hover {{ text-decoration: underline; }}
    .stats {{ display: flex; flex-wrap: wrap; gap: .6rem; padding: .8rem 2rem;
              background: #12151f; border-bottom: 1px solid #2d3748; font-size: .8rem; }}
    .stat      {{ padding: .25rem .65rem; border-radius: 999px; }}
    .stat.ok   {{ background: #14532d; color: #86efac; }}
    .stat.ng   {{ background: #450a0a; color: #fca5a5; }}
    .stat.add  {{ background: #1e3a5f; color: #7dd3fc; }}
    .stat.tot  {{ background: #2d2d3a; color: #94a3b8; }}
    nav {{ display: flex; flex-wrap: wrap; gap: .5rem; padding: .9rem 2rem;
           background: #1a1f2e; border-bottom: 1px solid #2d3748;
           position: sticky; top: 0; z-index: 10; }}
    nav a {{ color: #7dd3fc; text-decoration: none; font-size: .8rem; padding: .3rem .7rem;
             border-radius: 999px; border: 1px solid #2d3748; transition: background .2s; }}
    nav a:hover {{ background: #2d3748; }}
    nav a small {{ color: #64748b; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1rem; }}
    section {{ margin-bottom: 3rem; }}
    section h2 {{ font-size: 1.15rem; color: #a78bfa; border-left: 3px solid #7c3aed;
                  padding-left: .75rem; margin-bottom: 1.25rem; display: flex; align-items: center; gap: .6rem; }}
    .count {{ font-size: .75rem; color: #64748b; font-weight: 400; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1rem; }}
    .card {{ background: #1a1f2e; border: 1px solid #2d3748; border-radius: 10px;
             padding: 1.1rem; transition: border-color .2s, transform .2s; }}
    .card:hover {{ border-color: #7c3aed; transform: translateY(-2px); }}
    .card-new {{ border-color: #1d4ed8 !important; }}
    .card-meta {{ display: flex; justify-content: space-between; font-size: .73rem;
                  color: #64748b; margin-bottom: .45rem; }}
    .source {{ color: #7dd3fc; font-weight: 600; }}
    .badge-new {{ background: #1d4ed8; color: #fff; font-size: .65rem; font-weight: 700;
                  padding: .1rem .4rem; border-radius: 4px; margin-right: .4rem;
                  vertical-align: middle; }}
    .card h3 {{ font-size: .93rem; line-height: 1.45; margin-bottom: .5rem; }}
    .card h3 a {{ color: #e2e8f0; text-decoration: none; }}
    .card h3 a:hover {{ color: #a78bfa; }}
    .desc {{ font-size: .81rem; color: #94a3b8; line-height: 1.55; margin-bottom: .5rem; }}
    .summary-ja {{ font-size: .84rem; color: #c4b5fd; line-height: 1.6; margin-bottom: .5rem;
                   background: #1e1b3a; border-left: 2px solid #7c3aed; padding: .35rem .6rem;
                   border-radius: 0 6px 6px 0; }}
    .fetched {{ font-size: .7rem; color: #475569; text-align: right; }}
    .empty {{ text-align: center; padding: 4rem 1rem; color: #64748b; }}
    .empty p {{ margin-bottom: .6rem; }}
    code {{ background: #2d3748; padding: .1rem .4rem; border-radius: 4px; color: #7dd3fc; }}
    footer {{ text-align: center; padding: 2rem; color: #475569; font-size: .78rem;
              border-top: 1px solid #2d3748; margin-top: 2rem; }}
  </style>
</head>
<body>
  <header>
    <h1>AI/LLM ニュースダッシュボード</h1>
    <p>最終更新: {html.escape(generated_at)} &nbsp;|&nbsp; ArXiv / GAFA企業ブログ / Kaggle などから自動収集・蓄積</p>
    <a href="index.html" class="archive-link">← アーカイブ一覧へ</a>
  </header>
  <div class="stats">{stats_html}</div>
  <nav>{nav}</nav>
  <main>{sections}
  </main>
  <footer>
    Generated by <code>scripts/collect_news.py</code> &mdash; sturdy-octo-happiness &nbsp;|&nbsp;
    データ: <code>docs/news_data.json</code> &nbsp;|&nbsp; ログ: <code>logs/collect_news.log</code>
  </footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    run_start = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log("INFO", f"=== 収集開始 {run_start} ===")

    existing = load_existing()
    log("INFO", f"既存記事: {len(existing)} 件")

    all_new: list[dict] = []
    success_count = 0
    failure_count = 0

    for feed in FEEDS:
        log("INFO", f"取得中: {feed['name']} ({feed['url']})")
        data = fetch_feed(feed)
        if data is None:
            failure_count += 1
            continue
        items = parse_feed(data, feed)
        all_new.extend(items)
        success_count += 1
        log("INFO", f"  -> {len(items)} 件パース完了")

    merged, added = merge_articles(existing, all_new)

    # 日本語要約
    if _ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
        to_translate = [a for a in merged if not a.get("summary_ja")][:MAX_TRANSLATE_PER_RUN]
        if to_translate:
            log("INFO", f"日本語要約: {len(to_translate)} 件を処理します（記事全文取得あり）")
        for a in to_translate:
            article_text = fetch_article_text(a.get("link", ""))
            summary_ja = summarize_in_japanese(
                a.get("title", ""),
                a.get("description", ""),
                article_text,
            )
            if summary_ja:
                a["summary_ja"] = summary_ja
        translated = sum(1 for a in to_translate if a.get("summary_ja"))
        if to_translate:
            log("INFO", f"日本語要約完了: {translated}/{len(to_translate)} 件")
    else:
        if not _ANTHROPIC_AVAILABLE:
            log("INFO", "anthropic パッケージ未インストール — 日本語要約をスキップ")
        elif not ANTHROPIC_API_KEY:
            log("INFO", "ANTHROPIC_API_KEY 未設定 — 日本語要約をスキップ")

    save_data(merged)
    log("INFO", f"保存完了: 合計 {len(merged)} 件 (今回追加 +{added} 件)")

    # 日付別 JSONL + Markdown
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    save_daily_files(merged, today_str)

    # ダッシュボード HTML
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run_stats = {
        "success": success_count,
        "failure": failure_count,
        "added":   added,
        "total":   len(merged),
    }
    html_content = build_html(merged, generated_at, run_stats)
    HTML_FILE.parent.mkdir(parents=True, exist_ok=True)
    HTML_FILE.write_text(html_content, encoding="utf-8")
    log("INFO", f"HTML生成: {HTML_FILE} ({HTML_FILE.stat().st_size // 1024} KB)")

    # アーカイブ index.html
    index_content = build_index_html(generated_at)
    INDEX_FILE.write_text(index_content, encoding="utf-8")
    log("INFO", f"インデックスHTML生成: {INDEX_FILE} ({INDEX_FILE.stat().st_size // 1024} KB)")

    log("INFO", f"=== 収集終了: 成功 {success_count} / 失敗 {failure_count} フィード ===\n")


if __name__ == "__main__":
    main()
