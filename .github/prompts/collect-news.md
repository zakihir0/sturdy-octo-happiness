# AI/LLM ニュース収集プロンプト

以下の手順でAI/LLMニュースを収集・翻訳・ファイル保存してください。
HTML生成・コミット・プッシュはワークフローが別途実行します。

## 1. 既存データの確認

`docs/news_data.json` を Read ツールで読み込み、既存記事のURLセットを把握する。
ファイルが存在しない場合は空の配列として扱う。

## 2. RSSフィードの取得

以下のURLをそれぞれ WebFetch で取得し、各フィードから最大10件の記事を抽出する。
既存URLと重複する記事はスキップする。

| カテゴリ | ソース名 | URL |
|----------|---------|-----|
| 論文 - AI全般 | ArXiv cs.AI | https://arxiv.org/rss/cs.AI |
| 論文 - 機械学習 | ArXiv cs.LG | https://arxiv.org/rss/cs.LG |
| 論文 - 言語処理 | ArXiv cs.CL | https://arxiv.org/rss/cs.CL |
| 企業ブログ | Anthropic | https://www.anthropic.com/rss.xml |
| 企業ブログ | Meta AI | https://ai.meta.com/blog/rss/ |
| 企業ブログ | Google DeepMind | https://deepmind.google/blog/rss.xml |
| AI全般ニュース | TechCrunch AI | https://techcrunch.com/category/artificial-intelligence/feed/ |

## 3. 記事の翻訳・要約

新着記事ごとに、記事URLを WebFetch でアクセスして本文を読み、日本語で2〜3文（150字以内）に要約する。
WebFetch が失敗した場合は RSS の概要テキストで代替する。

## 4. ファイルへの保存

今日の日付（UTC）を YYYY-MM-DD 形式で取得し、以下のファイルを Write ツールで保存する。

### docs/news/YYYY-MM-DD.jsonl

新着記事を1行1レコードのJSONL形式で保存する。各レコードのフィールド：
- title: 英語原題
- link: 記事URL
- description: RSS概要テキスト
- date: RSS記載の公開日
- source: ソース名（例: ArXiv cs.AI）
- category: カテゴリ名（例: 論文 - AI全般）
- fetched_at: 収集日時（ISO 8601 UTC形式）
- summary_ja: 日本語要約

### docs/news/YYYY-MM-DD.md

カテゴリ別に整理したMarkdown形式で保存する。
冒頭に「# AI/LLM ニュース YYYY-MM-DD」「収集件数: N 件」を記載し、
カテゴリ見出し・記事タイトル（リンク）・日付・ソース・日本語要約・区切り線の順で記述する。

### docs/news_data.json

既存の全記事配列に新着記事を追加し、fetched_at 降順でソートして保存する。

## 5. ログの記録

`logs/collect_news.log` に今回の収集結果を追記する。記載内容：
- 収集開始日時・終了日時
- 各フィードの取得成否
- 新着追加件数・合計件数
