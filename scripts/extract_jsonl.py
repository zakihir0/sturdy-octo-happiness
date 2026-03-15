#!/usr/bin/env python3
"""Gemini stream-json出力からJSONL記事行を抽出してファイルに保存する。"""
import json
import os
import pathlib
import sys

raw = pathlib.Path('/tmp/gemini_raw.txt').read_text(encoding='utf-8')
jsonl_file = pathlib.Path(os.environ['JSONL_FILE'])
jsonl_file.parent.mkdir(parents=True, exist_ok=True)

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
lines = []
for line in full_response.splitlines():
    line = line.strip()
    try:
        obj = json.loads(line)
        link = obj.get('link', '')
        domain = link.split('/')[2] if link.startswith('http') else ''
        if (isinstance(obj, dict) and 'title' in obj and link
                and 'example.com' not in domain
                and 'vertexaisearch.cloud.google.com' not in domain):
            lines.append(json.dumps(obj, ensure_ascii=False))
    except Exception:
        pass

if lines:
    jsonl_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Wrote {len(lines)} articles to {jsonl_file}')
else:
    print('No valid JSONL found. Assistant response:', file=sys.stderr)
    print(full_response[:3000] if full_response else raw[:3000], file=sys.stderr)
