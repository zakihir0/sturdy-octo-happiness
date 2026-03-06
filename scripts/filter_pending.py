#!/usr/bin/env python3
"""
未処理の pending 記事だけを stdout に出力する。

Usage:
    python3 scripts/filter_pending.py <pending_file> <final_file>

- pending_file: docs/news/.pending/YYYY-MM-DD.jsonl
- final_file:   docs/news/YYYY-MM-DD.jsonl
- 既に final_file に存在する link を除外して残りを出力する
- 残りがなければ何も出力しない（終了コード 0）
"""
import json
import os
import sys


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <pending_file> <final_file>", file=sys.stderr)
        sys.exit(1)

    pending_file = sys.argv[1]
    final_file = sys.argv[2]

    # 処理済みリンクを収集
    processed = set()
    if os.path.exists(final_file):
        with open(final_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        processed.add(json.loads(line)["link"])
                    except Exception:
                        pass

    # 未処理記事のみ抽出
    remaining = []
    with open(pending_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    art = json.loads(line)
                    if art.get("link") not in processed:
                        remaining.append(line)
                except Exception:
                    remaining.append(line)

    if remaining:
        print("\n".join(remaining))


if __name__ == "__main__":
    main()
