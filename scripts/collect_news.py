#!/usr/bin/env python3
"""
AI/LLM ニュース収集スクリプト

RSSフィードから最新記事を取得し、docs/news_data.json に追記しながら
docs/news.html と docs/index.html を再生成します。
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
MAX_TRANSLATE_PER_RUN = 30

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
# Summarization
# ---------------------------------------------------------------------------

def fetch_article_text(url: str) -> str:
    if not url:
        return ""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"},
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
            "日本語で2〜3文（150字以内）に要約してください。\n\n"
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
# Fetch & Parse
# ---------------------------------------------------------------------------

def fetch_feed(feed: dict) -> bytes | None:
    url = feed["url"]
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            log("INFO", f"OK   {feed['name']} ({len(data):,} bytes)")
            return data
    except Exception as e:
        reason = traceback.format_exception_only(type(e), e)[-1].strip()
        log("WARN", f"FAIL {feed['name']} | {reason}")
        return None


def parse_feed(data: bytes, feed: dict) -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        log("WARN", f"XML解析エラー ({feed['name']}): {e}")
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    fetched_at = datetime.now(timezone.utc).isoformat()

    def make_item(title, link, desc, date):
        return {
            "title":       (title or "").strip(),
            "link":        (link  or "").strip(),
            "description": (desc  or "").strip(),
            "date":        (date  or "").strip(),
            "source":      feed["name"],
            "category":    feed["category"],
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
# Storage
# ---------------------------------------------------------------------------

def load_existing() -> list[dict]:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log("WARN", f"既存データ読み込み失敗: {e}")
    return []


def load_all_from_jsonl() -> list[dict]:
    """docs/news/*.jsonl 内の全記事を読み込み、URLで重複排除して返す。"""
    articles: list[dict] = []
    seen: set[str] = set()
    for path in sorted(NEWS_DIR.glob("*.jsonl"), reverse=True):
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    a = json.loads(line)
                    link = a.get("link", "")
                    if link and link in seen:
                        continue
                    if link:
                        seen.add(link)
                    articles.append(a)
        except Exception as e:
            log("WARN", f"JSONL読み込み失敗 {path}: {e}")
    articles.sort(key=lambda a: a.get("fetched_at", ""), reverse=True)
    return articles


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
# Daily JSONL + Markdown
# ---------------------------------------------------------------------------

def save_daily_files(articles: list[dict], today_str: str) -> None:
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    today_articles = [a for a in articles if a.get("fetched_at", "")[:10] == today_str]
    if not today_articles:
        log("INFO", "今日の新着記事なし")
        return

    jsonl_path = NEWS_DIR / f"{today_str}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for a in today_articles:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    log("INFO", f"JSONL保存: {jsonl_path} ({len(today_articles)} 件)")

    md_path = NEWS_DIR / f"{today_str}.md"
    categories: dict[str, list[dict]] = {}
    for a in today_articles:
        categories.setdefault(a.get("category", "その他"), []).append(a)

    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# AI/LLM ニュース {today_str}\n\n収集件数: {len(today_articles)} 件\n\n")
        for cat, items in categories.items():
            f.write(f"\n## {cat}\n\n")
            for item in items:
                title      = item.get("title", "(no title)")
                link       = item.get("link", "")
                summary_ja = item.get("summary_ja", "")
                f.write(f"### [{title}]({link})\n\n")
                f.write(f"**日付:** {(item.get('date') or '')[:30]}  \n")
                f.write(f"**ソース:** {item.get('source', '')}  \n\n")
                if summary_ja:
                    f.write(f"{summary_ja}\n\n")
                f.write("---\n\n")
    log("INFO", f"MD保存: {md_path}")


# ---------------------------------------------------------------------------
# HTML: article card helper
# ---------------------------------------------------------------------------

def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())[:300]


def render_card(item: dict, today: str) -> str:
    title      = html.escape(item.get("title") or "(no title)")
    link       = html.escape(item.get("link", ""))
    summary_ja = html.escape(item.get("summary_ja", ""))
    desc       = html.escape(strip_tags(item.get("description", "")))
    date       = html.escape((item.get("date") or "")[:30])
    source     = html.escape(item.get("source", ""))
    fetched_at = item.get("fetched_at", "")[:10]
    is_new     = fetched_at == today
    new_badge  = '<span class="badge-new">NEW</span>' if is_new else ""
    body = (
        f'<p class="summary-ja">{summary_ja}</p>'
        if summary_ja else
        f'<p class="desc">{desc}</p>'
    )
    return f"""<article class="thread-item{' thread-item-new' if is_new else ''}">
  <div class="thread-dot"></div>
  <div class="thread-content">
    <div class="thread-meta">
      <span class="source">{source}</span>
      <span class="date">{date}</span>
      {new_badge}
    </div>
    <h3><a href="{link}" target="_blank" rel="noopener">{title}</a></h3>
    {body}
    <div class="fetched">収集日: {fetched_at}</div>
  </div>
</article>"""


# ---------------------------------------------------------------------------
# HTML: index (daily JSONL viewer)
# ---------------------------------------------------------------------------

def build_index_html(generated_at: str) -> str:
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    dates = sorted(
        set(f.stem for f in NEWS_DIR.glob("*.jsonl")),
        reverse=True,
    )

    # Date tabs
    tab_buttons = ""
    for d in dates:
        active = "active" if d == dates[0] else ""
        tab_buttons += f'<button class="tab-btn {active}" onclick="showTab(\'{d}\',this)">{d}</button>\n'

    # Sections per date
    sections = ""
    for d in dates:
        jsonl_path = NEWS_DIR / f"{d}.jsonl"
        articles = []
        try:
            with jsonl_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        articles.append(json.loads(line))
        except Exception:
            pass

        categories: dict[str, list[dict]] = {}
        for a in articles:
            categories.setdefault(a.get("category", "その他"), []).append(a)

        display = "block" if d == dates[0] else "none"
        cat_sections = ""
        for cat, items in categories.items():
            cards = "\n".join(render_card(a, today) for a in items)
            cat_sections += f'<div class="cat-section"><h3 class="cat-title">{html.escape(cat)} <span class="count">{len(items)}件</span></h3><div class="thread">{cards}</div></div>\n'

        md_link = f'<a href="news/{d}.md" class="file-link">MD</a>' if (NEWS_DIR / f"{d}.md").exists() else ""
        jsonl_link = f'<a href="news/{d}.jsonl" class="file-link">JSONL</a>'
        sections += f"""<section id="tab-{d}" style="display:{display}">
  <div class="section-header">
    <span>📅 {d} &nbsp;·&nbsp; {len(articles)}件</span>
    <div>{md_link}{jsonl_link}</div>
  </div>
  {cat_sections if cat_sections else '<p class="empty">記事なし</p>'}
</section>\n"""

    if not dates:
        sections = '<p class="empty">まだデータがありません。ワークフローを実行してください。</p>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI/LLM ニュース アーカイブ</title>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f1117;color:#e2e8f0;min-height:100vh}}
    header{{background:linear-gradient(135deg,#1a1f2e 0%,#16213e 100%);padding:2rem;border-bottom:1px solid #2d3748}}
    header h1{{font-size:1.8rem;font-weight:700;color:#a78bfa}}
    header p{{color:#94a3b8;margin-top:.4rem;font-size:.85rem}}
    .header-links{{margin-top:1rem;display:flex;gap:1rem}}
    .header-links a{{color:#7dd3fc;font-size:.85rem;text-decoration:none;padding:.35rem .8rem;border:1px solid #2d3748;border-radius:6px}}
    .header-links a:hover{{background:#2d3748}}
    .tabs{{display:flex;flex-wrap:wrap;gap:.5rem;padding:.9rem 2rem;background:#1a1f2e;border-bottom:1px solid #2d3748;position:sticky;top:0;z-index:10}}
    .tab-btn{{padding:.35rem .85rem;border:1px solid #2d3748;border-radius:999px;background:transparent;color:#7dd3fc;font-size:.8rem;cursor:pointer;transition:all .2s}}
    .tab-btn:hover,.tab-btn.active{{background:#7c3aed;border-color:#7c3aed;color:#fff}}
    main{{max-width:800px;margin:0 auto;padding:2rem 1rem}}
    .section-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;padding-bottom:.75rem;border-bottom:1px solid #2d3748}}
    .section-header span{{color:#a78bfa;font-size:1.1rem;font-weight:600}}
    .file-link{{font-size:.8rem;color:#7dd3fc;text-decoration:none;margin-left:.6rem;padding:.2rem .5rem;border:1px solid #2d3748;border-radius:4px}}
    .file-link:hover{{background:#2d3748}}
    .cat-section{{margin-bottom:2.5rem}}
    .cat-title{{font-size:1rem;color:#94a3b8;border-left:3px solid #7c3aed;padding-left:.65rem;margin-bottom:1.2rem;display:flex;align-items:center;gap:.5rem}}
    .count{{font-size:.75rem;color:#64748b;font-weight:400}}
    .thread{{position:relative;padding-left:1.5rem;border-left:2px solid #2d3748}}
    .thread-item{{position:relative;padding:.9rem 1rem .9rem 1.2rem;margin-bottom:.5rem;background:#1a1f2e;border:1px solid #2d3748;border-radius:8px;transition:border-color .2s}}
    .thread-item:hover{{border-color:#7c3aed}}
    .thread-item-new{{border-color:#1d4ed8!important}}
    .thread-dot{{position:absolute;left:-1.85rem;top:1.1rem;width:10px;height:10px;border-radius:50%;background:#7c3aed;border:2px solid #0f1117}}
    .thread-item-new .thread-dot{{background:#1d4ed8}}
    .thread-content{{}}
    .thread-meta{{display:flex;align-items:center;gap:.6rem;font-size:.73rem;color:#64748b;margin-bottom:.4rem;flex-wrap:wrap}}
    .source{{color:#7dd3fc;font-weight:600}}
    .date{{color:#475569}}
    .badge-new{{background:#1d4ed8;color:#fff;font-size:.65rem;font-weight:700;padding:.1rem .4rem;border-radius:4px}}
    .thread-item h3{{font-size:.95rem;line-height:1.45;margin-bottom:.45rem}}
    .thread-item h3 a{{color:#e2e8f0;text-decoration:none}}
    .thread-item h3 a:hover{{color:#a78bfa}}
    .desc{{font-size:.81rem;color:#94a3b8;line-height:1.55;margin-bottom:.4rem}}
    .summary-ja{{font-size:.84rem;color:#c4b5fd;line-height:1.6;margin-bottom:.4rem;background:#1e1b3a;border-left:2px solid #7c3aed;padding:.35rem .6rem;border-radius:0 6px 6px 0}}
    .fetched{{font-size:.7rem;color:#475569;text-align:right}}
    .empty{{color:#64748b;padding:2rem 0;text-align:center}}
    footer{{text-align:center;padding:2rem;color:#475569;font-size:.78rem;border-top:1px solid #2d3748;margin-top:2rem}}
    code{{background:#2d3748;padding:.1rem .4rem;border-radius:4px;color:#7dd3fc}}
  </style>
</head>
<body>
  <header>
    <h1>AI/LLM ニュース アーカイブ</h1>
    <p>最終更新: {html.escape(generated_at)} &nbsp;|&nbsp; 毎日 JST 10:00 自動更新</p>
    <div class="header-links">
      <a href="news.html">全記事ダッシュボード →</a>
    </div>
  </header>
  <nav class="tabs">{tab_buttons}</nav>
  <main>{sections}</main>
  <footer>Powered by Claude Code + GitHub Actions &nbsp;|&nbsp; <code>docs/news/YYYY-MM-DD.jsonl</code></footer>
  <script>
    function showTab(d, btn) {{
      document.querySelectorAll('main > section').forEach(s => s.style.display = 'none');
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      const s = document.getElementById('tab-' + d);
      if (s) s.style.display = 'block';
      btn.classList.add('active');
    }}
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML: news.html (all-time dashboard)
# ---------------------------------------------------------------------------

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
    for i, (cat, items) in enumerate(categories.items()):
        cards = "\n".join(render_card(a, today) for a in items)
        sections += f'<section id="cat-{i}"><h2>{html.escape(cat)} <span class="count">{len(items)}件</span></h2><div class="thread">{cards}</div></section>\n'

    if not articles:
        sections = '<section><p class="empty">ニュースがまだありません。</p></section>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI/LLM ニュースダッシュボード</title>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f1117;color:#e2e8f0;min-height:100vh}}
    header{{background:linear-gradient(135deg,#1a1f2e 0%,#16213e 100%);padding:2rem;border-bottom:1px solid #2d3748}}
    header h1{{font-size:1.8rem;font-weight:700;color:#a78bfa}}
    header p{{color:#94a3b8;margin-top:.4rem;font-size:.85rem}}
    .archive-link{{display:inline-block;margin-top:.8rem;color:#7dd3fc;font-size:.85rem;text-decoration:none;padding:.35rem .8rem;border:1px solid #2d3748;border-radius:6px}}
    .archive-link:hover{{background:#2d3748}}
    .stats{{display:flex;flex-wrap:wrap;gap:.6rem;padding:.8rem 2rem;background:#12151f;border-bottom:1px solid #2d3748;font-size:.8rem}}
    .stat{{padding:.25rem .65rem;border-radius:999px}}
    .stat.ok{{background:#14532d;color:#86efac}}
    .stat.ng{{background:#450a0a;color:#fca5a5}}
    .stat.add{{background:#1e3a5f;color:#7dd3fc}}
    .stat.tot{{background:#2d2d3a;color:#94a3b8}}
    nav{{display:flex;flex-wrap:wrap;gap:.5rem;padding:.9rem 2rem;background:#1a1f2e;border-bottom:1px solid #2d3748;position:sticky;top:0;z-index:10}}
    nav a{{color:#7dd3fc;text-decoration:none;font-size:.8rem;padding:.3rem .7rem;border-radius:999px;border:1px solid #2d3748;transition:background .2s}}
    nav a:hover{{background:#2d3748}}
    nav a small{{color:#64748b}}
    main{{max-width:800px;margin:0 auto;padding:2rem 1rem}}
    section{{margin-bottom:3rem}}
    section h2{{font-size:1.15rem;color:#a78bfa;border-left:3px solid #7c3aed;padding-left:.75rem;margin-bottom:1.25rem;display:flex;align-items:center;gap:.6rem}}
    .count{{font-size:.75rem;color:#64748b;font-weight:400}}
    .thread{{position:relative;padding-left:1.5rem;border-left:2px solid #2d3748}}
    .thread-item{{position:relative;padding:.9rem 1rem .9rem 1.2rem;margin-bottom:.5rem;background:#1a1f2e;border:1px solid #2d3748;border-radius:8px;transition:border-color .2s}}
    .thread-item:hover{{border-color:#7c3aed}}
    .thread-item-new{{border-color:#1d4ed8!important}}
    .thread-dot{{position:absolute;left:-1.85rem;top:1.1rem;width:10px;height:10px;border-radius:50%;background:#7c3aed;border:2px solid #0f1117}}
    .thread-item-new .thread-dot{{background:#1d4ed8}}
    .thread-content{{}}
    .thread-meta{{display:flex;align-items:center;gap:.6rem;font-size:.73rem;color:#64748b;margin-bottom:.4rem;flex-wrap:wrap}}
    .source{{color:#7dd3fc;font-weight:600}}
    .date{{color:#475569}}
    .badge-new{{background:#1d4ed8;color:#fff;font-size:.65rem;font-weight:700;padding:.1rem .4rem;border-radius:4px}}
    .thread-item h3{{font-size:.95rem;line-height:1.45;margin-bottom:.45rem}}
    .thread-item h3 a{{color:#e2e8f0;text-decoration:none}}
    .thread-item h3 a:hover{{color:#a78bfa}}
    .desc{{font-size:.81rem;color:#94a3b8;line-height:1.55;margin-bottom:.4rem}}
    .summary-ja{{font-size:.84rem;color:#c4b5fd;line-height:1.6;margin-bottom:.4rem;background:#1e1b3a;border-left:2px solid #7c3aed;padding:.35rem .6rem;border-radius:0 6px 6px 0}}
    .fetched{{font-size:.7rem;color:#475569;text-align:right}}
    .empty{{text-align:center;padding:4rem 1rem;color:#64748b}}
    footer{{text-align:center;padding:2rem;color:#475569;font-size:.78rem;border-top:1px solid #2d3748;margin-top:2rem}}
    code{{background:#2d3748;padding:.1rem .4rem;border-radius:4px;color:#7dd3fc}}
  </style>
</head>
<body>
  <header>
    <h1>AI/LLM ニュースダッシュボード</h1>
    <p>最終更新: {html.escape(generated_at)} &nbsp;|&nbsp; ArXiv / GAFA企業ブログ / Kaggle などから自動収集</p>
    <a href="index.html" class="archive-link">← 日付別アーカイブ</a>
  </header>
  <div class="stats">{stats_html}</div>
  <nav>{nav}</nav>
  <main>{sections}</main>
  <footer>Powered by Claude Code + GitHub Actions &nbsp;|&nbsp; データ: <code>docs/news/YYYY-MM-DD.jsonl</code></footer>
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
        data = fetch_feed(feed)
        if data is None:
            failure_count += 1
            continue
        items = parse_feed(data, feed)
        all_new.extend(items)
        success_count += 1

    merged, added = merge_articles(existing, all_new)

    if _ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
        to_translate = [a for a in merged if not a.get("summary_ja")][:MAX_TRANSLATE_PER_RUN]
        if to_translate:
            log("INFO", f"日本語要約: {len(to_translate)} 件")
        for a in to_translate:
            article_text = fetch_article_text(a.get("link", ""))
            summary_ja = summarize_in_japanese(a.get("title", ""), a.get("description", ""), article_text)
            if summary_ja:
                a["summary_ja"] = summary_ja
    else:
        log("INFO", "ANTHROPIC_API_KEY 未設定 — 要約スキップ（Claude Code が処理済みの想定）")

    save_data(merged)
    log("INFO", f"保存完了: 合計 {len(merged)} 件 (今回追加 +{added} 件)")

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    save_daily_files(merged, today_str)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run_stats = {"success": success_count, "failure": failure_count, "added": added, "total": len(merged)}

    all_articles = load_all_from_jsonl()
    log("INFO", f"全JSONL統合: {len(all_articles)} 件")

    HTML_FILE.parent.mkdir(parents=True, exist_ok=True)
    HTML_FILE.write_text(build_html(all_articles, generated_at, run_stats), encoding="utf-8")
    log("INFO", f"news.html 生成: {HTML_FILE.stat().st_size // 1024} KB")

    INDEX_FILE.write_text(build_index_html(generated_at), encoding="utf-8")
    log("INFO", f"index.html 生成: {INDEX_FILE.stat().st_size // 1024} KB")

    log("INFO", f"=== 収集終了: 成功 {success_count} / 失敗 {failure_count} フィード ===\n")


if __name__ == "__main__":
    main()
