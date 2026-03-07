#!/usr/bin/env python3
"""
プロンプトテンプレートの {{PENDING_ARTICLES}} を記事JSONで置換して stdout に出力する。

Usage:
    python3 scripts/build_prompt.py <article_file>

- article_file: docs/news/.pending/YYYY-MM-DD/001.json など（1記事分のJSON）
- テンプレートは .github/prompts/generate-summaries.md を使用する
"""
import sys


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <article_file>", file=sys.stderr)
        sys.exit(1)

    article_file = sys.argv[1]
    template_file = ".github/prompts/generate-summaries.md"

    template = open(template_file, encoding="utf-8").read()
    article = open(article_file, encoding="utf-8").read().strip()

    result = template.replace("{{PENDING_ARTICLES}}", article)
    sys.stdout.write(result)


if __name__ == "__main__":
    main()
