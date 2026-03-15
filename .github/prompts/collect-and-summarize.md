# AI/LLMニュース収集・要約

## ユーザーの興味領域

- LLM・基盤モデルの論文・研究動向
- GAFA（Google / Amazon / Meta / Apple）および主要AI企業の動向
- AIエージェント（LangChain / LangGraph / AutoGen / CrewAI等）
- Kaggle・MLコンペティションの手法・最新情報

## 指示

今日の日付（UTC）を YYYY-MM-DD 形式で取得する。

上記の興味領域に関連する最新のAI/LLMニュース・論文を**最大5件**調査し、各記事を**300字以内**の日本語で要約して `docs/news/YYYY-MM-DD.jsonl` に追記せよ。

- 末尾の「収集済みURL」に含まれるURLはスキップすること
- ファイルが存在しない場合は新規作成する
- 1行1記事のJSONL形式（1行に改行なし）で追記する
- 各行のフォーマット:

```json
{"title": "記事タイトル", "link": "URL", "description": "概要", "date": "公開日", "source": "ソース名", "category": "カテゴリ", "fetched_at": "収集日時ISO8601", "summary_ja": "300字以内の日本語要約"}
```

処理結果を `logs/collect_news.log` に追記する（処理日時・記事数・成否）。
