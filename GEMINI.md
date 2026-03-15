# GEMINI.md

このファイルは Gemini CLI がこのリポジトリで作業する際のガイダンスを提供します。

## 出力ルール

| 項目 | 仕様 |
|------|------|
| 日本語要約 | **300字以内** |
| 出力先 | `docs/news/YYYY-MM-DD_HHMM.jsonl`（実行ごとに新規作成、1行1記事、改行なし） |
| ログ | `logs/collect_news.log` に追記 |

## JSONL 1レコードのフィールド定義

```json
{
  "title":       "記事タイトル（英語原文）",
  "link":        "記事URL",
  "description": "RSS概要テキスト",
  "date":        "pubDate（RSS記載の公開日）",
  "source":      "ソース名（例: ArXiv cs.AI）",
  "category":    "カテゴリ名（例: 論文 - AI全般）",
  "fetched_at":  "収集日時（ISO 8601 UTC）",
  "summary_ja":  "Gemini CLI による日本語要約"
}
```
