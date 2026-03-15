#!/usr/bin/env python3
"""Gemini出力からJSONL行を抽出してファイルに保存する。"""
import json
import os
import pathlib
import sys

raw = pathlib.Path('/tmp/gemini_raw.txt').read_text(encoding='utf-8')
jsonl_file = pathlib.Path(os.environ['JSONL_FILE'])
jsonl_file.parent.mkdir(parents=True, exist_ok=True)

lines = []
for line in raw.splitlines():
    line = line.strip()
    try:
        obj = json.loads(line)
        link = obj.get('link', '')
        if isinstance(obj, dict) and 'title' in obj and link and 'example.com' not in link:
            lines.append(json.dumps(obj, ensure_ascii=False))
    except Exception:
        pass

if lines:
    jsonl_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Wrote {len(lines)} articles to {jsonl_file}')
else:
    print('No valid JSONL found. Gemini raw output:', file=sys.stderr)
    print(raw[:3000], file=sys.stderr)
