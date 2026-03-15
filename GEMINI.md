# GEMINI.md

このファイルは Gemini CLI がこのリポジトリで作業する際のガイダンスを提供します。

## ユーザーの興味領域

- LLM・基盤モデルの論文・研究動向
- GAFA（Google / Amazon / Meta / Apple）および主要AI企業の動向
- AIエージェント（LangChain / LangGraph / AutoGen / CrewAI等）
- Kaggle・MLコンペティションの手法・最新情報

## 収集・要約ルール

| 項目 | 仕様 |
|------|------|
| 収集件数 | 最大5件/回 |
| 日本語要約 | 300字以内 |
| 出力形式 | 1行1記事のJSONL（改行なし） |
| ログ | `logs/collect_news.log` に追記（処理日時・記事数・成否） |

## JSONL フィールド定義

```json
{"title": "記事タイトル", "link": "URL", "description": "概要", "date": "公開日", "source": "ソース名", "category": "カテゴリ", "fetched_at": "収集日時ISO8601", "summary_ja": "300字以内の日本語要約"}
```

## 実行指示

ワークフローから渡されるプロンプトに従い、以下を実行せよ：

1. 興味領域に関連する最新のAI/LLMニュース・論文を調査する
2. 収集済みURLに含まれる記事はスキップする
3. 各記事を300字以内で日本語要約し、指定された出力先ファイルにJSONL形式で書き出す
