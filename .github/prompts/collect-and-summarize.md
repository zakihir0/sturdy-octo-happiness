# AI/LLMニュース収集・要約

## ユーザーの興味領域

- LLM・基盤モデルの論文・研究動向
- GAFA（Google / Amazon / Meta / Apple）および主要AI企業の動向
- AIエージェント（LangChain / LangGraph / AutoGen / CrewAI等）
- Kaggle・MLコンペティションの手法・最新情報

## 新着記事

```json
{{NEW_ARTICLES}}
```

## 指示

今日の日付（UTC）を YYYY-MM-DD 形式で取得する。

上記の新着記事から**興味領域に関連する記事を選び**、各記事を**300字以内**の日本語で要約して `docs/news/YYYY-MM-DD.jsonl` に追記せよ。

- ファイルが存在しない場合は新規作成する
- 1行1記事のJSONL形式（1行に改行なし）で追記する
- 各行のフォーマット:

```json
{"title": "記事タイトル", "link": "URL", "description": "RSS概要", "date": "pubDate", "source": "ソース名", "category": "カテゴリ", "fetched_at": "収集日時", "summary_ja": "300字以内の日本語要約"}
```

処理結果を `logs/collect_news.log` に追記する（処理日時・選択記事数・成否）。
