#!/usr/bin/env python3
"""Gemini stream-json出力からJSONL記事行を抽出してファイルに保存する。

--verify-only: 既存のJSONLファイルを読み込み、URLのHTTP検証のみ行う。
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; news-checker/1.0)'}


def check_url(url: str, timeout: int = 10) -> int:
    """URLにHEADリクエストを送り、実際のHTTPステータスコードを返す。"""
    try:
        req = urllib.request.Request(url, method='HEAD', headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def is_valid_url(link: str) -> bool:
    domain = link.split('/')[2] if link.startswith('http') else ''
    return (
        bool(domain)
        and 'example.com' not in domain
        and 'vertexaisearch.cloud.google.com' not in domain
    )


def verify_articles(articles: list[dict]) -> list[dict]:
    """各記事のURLをHTTP検証し、200番台のみ返す。url_statusを実測値で上書き。"""
    verified = []
    for obj in articles:
        url = obj.get('link', '')
        status = check_url(url)
        if 200 <= status < 300:
            obj['url_status'] = status
            verified.append(obj)
        else:
            print(f'Excluded (HTTP {status}): {url}')
    return verified


jsonl_file = pathlib.Path(os.environ['JSONL_FILE'])
jsonl_file.parent.mkdir(parents=True, exist_ok=True)

# --verify-only: 既存のJSONLを読み込んでURL検証だけ行う
if '--verify-only' in sys.argv:
    if not jsonl_file.exists():
        print('No JSONL file to verify.')
        sys.exit(0)
    articles = []
    for line in jsonl_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            articles.append(json.loads(line))
        except Exception:
            pass
    verified = verify_articles(articles)
    jsonl_file.write_text(
        '\n'.join(json.dumps(a, ensure_ascii=False) for a in verified) + '\n'
        if verified else '',
        encoding='utf-8',
    )
    print(f'Verified: {len(verified)} articles kept in {jsonl_file}')
    sys.exit(0)

# 通常モード: stream-json出力からJSONL記事行を抽出
raw = pathlib.Path('/tmp/gemini_raw.txt').read_text(encoding='utf-8')

# stream-json形式からassistantの回答テキストを結合
assistant_parts = []
for line in raw.splitlines():
    line = line.strip()
    try:
        obj = json.loads(line)
        if obj.get('type') == 'message' and obj.get('role') == 'assistant' and 'content' in obj:
            assistant_parts.append(obj['content'])
    except Exception:
        pass

full_response = ''.join(assistant_parts)

# 回答テキストからJSONL記事行を抽出
articles = []
for line in full_response.splitlines():
    line = line.strip()
    try:
        obj = json.loads(line)
        link = obj.get('link', '')
        if isinstance(obj, dict) and 'title' in obj and link and is_valid_url(link):
            articles.append(obj)
    except Exception:
        pass

# HTTP検証
verified = verify_articles(articles)

if verified:
    jsonl_file.write_text(
        '\n'.join(json.dumps(a, ensure_ascii=False) for a in verified) + '\n',
        encoding='utf-8',
    )
    print(f'Wrote {len(verified)} articles to {jsonl_file}')
else:
    print('No valid JSONL found. Assistant response:', file=sys.stderr)
    print(full_response[:3000] if full_response else raw[:3000], file=sys.stderr)
