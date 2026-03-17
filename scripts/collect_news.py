#!/usr/bin/env python3
"""HTML生成スクリプト

docs/news/*.jsonl から全記事を読み込み、
docs/news.html と docs/index.html を再生成します。
"""

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT       = Path(__file__).parent.parent
HTML_FILE  = ROOT / "docs" / "news.html"
INDEX_FILE = ROOT / "docs" / "index.html"
NEWS_DIR   = ROOT / "docs" / "news"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(level: str, msg: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{now}] [{level}] {msg}"
    stream = sys.stderr if level in ("WARN", "ERROR") else sys.stdout
    print(line, file=stream)


# ---------------------------------------------------------------------------
# Category normalization
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"LLM", "Agents", "Business", "Infrastructure", "Safety"}

# 旧カテゴリ名からの移行マップ（フォールバック用）
CATEGORY_MAP: dict[str, str] = {
    "LLM Release": "LLM", "LLM Research": "LLM", "LLM/Software": "LLM",
    "Research": "LLM", "Interpretability": "LLM",
    "AIエージェント": "Agents", "AI Agent": "Agents", "AI Agents": "Agents",
    "AI Frameworks": "Agents", "AI/Tech": "Agents", "AI/OpenSource": "Agents",
    "ビジネス": "Business", "企業動向": "Business", "E-commerce": "Business",
    "AI/Business": "Business", "AI/Funding": "Business", "AI/Finance": "Business",
    "Enterprise AI": "Business", "Apple/Google AI": "Business", "Meta AI": "Business",
    "Product": "Business", "Healthcare AI": "Business", "Event": "Business",
    "Hardware/AI": "Infrastructure", "AI/Cloud": "Infrastructure",
    "AI Safety / Alignment": "Safety", "Lawsuit": "Safety",
}


def normalize_category(raw: str) -> str:
    if raw in VALID_CATEGORIES:
        return raw
    return CATEGORY_MAP.get(raw, "Business")


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Shared CSS (HN-style)
# ---------------------------------------------------------------------------

HN_CSS = """
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:Verdana,Geneva,sans-serif;font-size:10pt;background:#f6f6ef;color:#000;min-height:100vh}
    a{color:#000;text-decoration:none}
    a:visited{color:#828282}
    a:hover{text-decoration:underline}

    /* header */
    .hn-header{background:#ff6600;padding:4px 8px;display:flex;align-items:center;gap:12px}
    .hn-header .site-title{font-size:13pt;font-weight:bold;color:#000;white-space:nowrap}
    .hn-header .header-nav{display:flex;gap:8px;font-size:9pt}
    .hn-header .header-nav a{color:#000;padding:0 4px}
    .hn-header .header-nav a:hover{text-decoration:underline}
    .hn-sub{background:#ff6600;height:2px;margin-bottom:8px}

    /* date selector + sort bar */
    .date-bar{padding:6px 12px;background:#f6f6ef;border-bottom:1px solid #e8e8e8;display:flex;align-items:center;gap:12px;font-size:9pt;color:#828282;position:sticky;top:0;z-index:10}
    .date-bar select{font-size:9pt;border:1px solid #ccc;padding:2px 4px;background:#fff;cursor:pointer}
    .date-bar label{white-space:nowrap}

    /* category nav */
    .cat-nav{padding:6px 12px;font-size:8pt;color:#828282;border-bottom:1px solid #e8e8e8;display:flex;flex-wrap:wrap;align-items:center;gap:4px;line-height:2}
    .cat-nav a{color:#828282;margin:0 2px}
    .cat-nav a:hover{text-decoration:underline}
    .cat-nav .sort-ctrl{margin-left:auto;display:flex;align-items:center;gap:4px;white-space:nowrap}
    .cat-nav .sort-ctrl select{font-size:8pt;border:1px solid #ccc;padding:1px 4px;background:#fff;cursor:pointer}

    /* item list */
    .item-list{max-width:900px;margin:0 auto;padding:8px 12px}
    .cat-section{margin-bottom:20px}
    .cat-heading{font-size:9pt;color:#828282;border-top:1px solid #e8e8e8;padding:6px 0 4px;margin-bottom:4px}

    .item{display:flex;gap:4px;padding:5px 0;border-bottom:1px solid #f0f0e8;align-items:flex-start}
    .item:last-child{border-bottom:none}
    .rank{color:#828282;min-width:28px;text-align:right;font-size:9pt;padding-top:2px;flex-shrink:0}
    .item-body{flex:1;min-width:0}
    .title-line{line-height:1.4;margin-bottom:3px}
    .title-link{font-size:10pt;color:#000;word-break:break-word}
    .title-link:visited{color:#828282}
    .domain{font-size:8pt;color:#828282;margin-left:4px}
    .badge-new{font-size:7pt;color:#ff6600;border:1px solid #ff6600;padding:0 2px;margin-left:4px;font-weight:bold;vertical-align:middle}
    .summary{font-size:9pt;color:#444;line-height:1.55;margin:3px 0 4px;padding-left:2px}
    .subtext{font-size:8pt;color:#828282}
    .subtext .sep{margin:0 4px}

    footer{text-align:center;padding:16px;color:#828282;font-size:8pt;border-top:1px solid #e8e8e8;margin-top:12px}
    .empty{color:#828282;padding:20px 0;text-align:center;font-size:9pt}
"""

SORT_JS = """
  function sortItems(key, asc) {
    var sections = document.querySelectorAll('.item-list section[style*="block"], .item-list section:not([style])');
    if (!sections.length) sections = document.querySelectorAll('.cat-section');
    sections.forEach(function(sec) {
      var cats = sec.querySelectorAll('.cat-section');
      var targets = cats.length ? cats : [sec];
      targets.forEach(function(cat) {
        var items = Array.from(cat.querySelectorAll('.item'));
        items.sort(function(a, b) {
          var va = a.getAttribute('data-' + key) || '';
          var vb = b.getAttribute('data-' + key) || '';
          return asc ? va.localeCompare(vb) : vb.localeCompare(va);
        });
        items.forEach(function(el) { cat.appendChild(el); });
      });
    });
  }
  function applySort(sel) {
    var v = sel.value;
    if (v === 'title')   sortItems('title', true);
    if (v === 'date')    sortItems('date', false);
    if (v === 'fetched') sortItems('fetched', false);
  }
"""


# ---------------------------------------------------------------------------
# HTML: article item helper
# ---------------------------------------------------------------------------

def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())[:300]


def render_item(item: dict, today: str, rank: int) -> str:
    title      = html.escape(item.get("title") or "(no title)")
    link       = html.escape(item.get("link", ""))
    summary_ja = html.escape(item.get("summary_ja", ""))
    desc       = html.escape(strip_tags(item.get("description", "")))
    date       = html.escape((item.get("date") or "")[:10])
    source     = html.escape(item.get("source", ""))
    category   = html.escape(normalize_category(item.get("category", "")))
    fetched_at = item.get("fetched_at", "")[:10]
    is_new     = fetched_at == today

    new_badge  = '<span class="badge-new">new</span>' if is_new else ""
    domain     = f'<span class="domain">({source})</span>' if source else ""
    body_text  = summary_ja or desc
    summary    = f'<p class="summary">{body_text}</p>' if body_text else ""

    meta_parts = [p for p in [date, category] if p]
    subtext    = '<span class="sep">|</span>'.join(f'<span>{p}</span>' for p in meta_parts)

    return f"""<div class="item" data-title="{title}" data-date="{date}" data-fetched="{html.escape(fetched_at)}">
  <span class="rank">{rank}.</span>
  <div class="item-body">
    <div class="title-line">
      <a href="{link}" class="title-link" target="_blank" rel="noopener">{title}</a>{domain}{new_badge}
    </div>
    {summary}
    <div class="subtext">{subtext}</div>
  </div>
</div>"""


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

    # Date select options
    options = ""
    for d in dates:
        options += f'<option value="{d}">{d}</option>\n'

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
            cat = normalize_category(a.get("category", ""))
            categories.setdefault(cat, []).append(a)

        display = "block" if d == dates[0] else "none"
        rank = 1
        cat_sections = ""
        for cat, items in categories.items():
            cards = ""
            for a in items:
                cards += render_item(a, today, rank) + "\n"
                rank += 1
            jsonl_link = f'<a href="news/{d}.jsonl" style="float:right;color:#828282;font-size:8pt">JSONL</a>'
            cat_sections += f'<div class="cat-section"><div class="cat-heading">{html.escape(cat)} ({len(items)}) {jsonl_link}</div>{cards}</div>\n'

        empty_msg = '<p class="empty">記事なし</p>'
        sections += f'<section id="tab-{d}" style="display:{display}">{cat_sections if cat_sections else empty_msg}</section>\n'

    if not dates:
        sections = '<p class="empty">まだデータがありません。ワークフローを実行してください。</p>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI/LLM News</title>
  <style>{HN_CSS}</style>
</head>
<body>
  <div class="hn-header">
    <span class="site-title">AI/LLM News</span>
    <div class="header-nav">
      <a href="news.html">all</a>
      <span>|</span>
      <span style="color:#000;font-size:8pt">{html.escape(generated_at)}</span>
    </div>
  </div>
  <div class="hn-sub"></div>
  <div class="date-bar">
    <label for="date-select">日付:</label>
    <select id="date-select" onchange="showTab(this.value)">{options}</select>
    <label for="sort-select" style="margin-left:8px">並び替え:</label>
    <select id="sort-select" onchange="applySort(this)">
      <option value="fetched">取得日 (新しい順)</option>
      <option value="date">記事日付 (新しい順)</option>
      <option value="title">タイトル (A-Z)</option>
    </select>
  </div>
  <div class="item-list">{sections}</div>
  <footer>Powered by Gemini CLI + GitHub Actions</footer>
  <script>
    function showTab(d) {{
      document.querySelectorAll('.item-list > section').forEach(s => s.style.display = 'none');
      const s = document.getElementById('tab-' + d);
      if (s) s.style.display = 'block';
      applySort(document.getElementById('sort-select'));
    }}
    {SORT_JS}
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML: news.html (all-time dashboard)
# ---------------------------------------------------------------------------

def build_html(articles: list[dict], generated_at: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    categories: dict[str, list[dict]] = {}
    for a in articles:
        cat = normalize_category(a.get("category", ""))
        categories.setdefault(cat, []).append(a)

    cat_links = " | ".join(
        f'<a href="#cat-{i}">{html.escape(cat)} ({len(items)})</a>'
        for i, (cat, items) in enumerate(categories.items())
    )

    sections = ""
    rank = 1
    for i, (cat, items) in enumerate(categories.items()):
        cards = ""
        for a in items:
            cards += render_item(a, today, rank) + "\n"
            rank += 1
        sections += f'<section id="cat-{i}" class="cat-section"><div class="cat-heading">{html.escape(cat)} ({len(items)})</div>{cards}</section>\n'

    if not articles:
        sections = '<p class="empty">ニュースがまだありません。</p>'

    sort_ctrl = """<span class="sort-ctrl">
      <label for="sort-select-all">並び替え:</label>
      <select id="sort-select-all" onchange="applySort(this)">
        <option value="fetched">取得日 (新しい順)</option>
        <option value="date">記事日付 (新しい順)</option>
        <option value="title">タイトル (A-Z)</option>
      </select>
    </span>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI/LLM News — All</title>
  <style>{HN_CSS}</style>
</head>
<body>
  <div class="hn-header">
    <span class="site-title">AI/LLM News</span>
    <div class="header-nav">
      <a href="index.html">daily</a>
      <span>|</span>
      <span style="color:#000;font-size:8pt">{html.escape(generated_at)}</span>
    </div>
  </div>
  <div class="hn-sub"></div>
  <div class="cat-nav">{cat_links}{sort_ctrl}</div>
  <div class="item-list">{sections}</div>
  <footer>Powered by Gemini CLI + GitHub Actions</footer>
  <script>
    {SORT_JS}
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log("INFO", "=== HTML生成開始 ===")

    articles = load_all_from_jsonl()
    log("INFO", f"全JSONL統合: {len(articles)} 件")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    HTML_FILE.parent.mkdir(parents=True, exist_ok=True)
    HTML_FILE.write_text(build_html(articles, generated_at), encoding="utf-8")
    log("INFO", f"news.html 生成: {HTML_FILE.stat().st_size // 1024} KB")

    INDEX_FILE.write_text(build_index_html(generated_at), encoding="utf-8")
    log("INFO", f"index.html 生成: {INDEX_FILE.stat().st_size // 1024} KB")

    log("INFO", "=== HTML生成終了 ===\n")


if __name__ == "__main__":
    main()
