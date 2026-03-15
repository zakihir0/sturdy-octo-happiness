# GEMINI.md

このファイルは Gemini CLI がこのリポジトリで作業する際のガイダンスを提供します。

## ニュース収集の要件

### 収集対象ソース

| カテゴリ | ソース名 | RSS URL |
|----------|---------|---------|
| 論文 - AI全般 | ArXiv cs.AI | `https://arxiv.org/rss/cs.AI` |
| 論文 - 機械学習 | ArXiv cs.LG | `https://arxiv.org/rss/cs.LG` |
| 論文 - 言語処理 | ArXiv cs.CL | `https://arxiv.org/rss/cs.CL` |
| 企業ブログ | Anthropic | `https://www.anthropic.com/rss.xml` |
| 企業ブログ | Meta AI | `https://ai.meta.com/blog/rss/` |
| 企業ブログ | Google DeepMind | `https://deepmind.google/blog/rss.xml` |
| AI全般ニュース | TechCrunch AI | `https://techcrunch.com/category/artificial-intelligence/feed/` |

### 収集・処理ルール

| 項目 | 仕様 |
|------|------|
| 収集主体 | **Gemini CLI** が URL取得ツールで各ソースに直接アクセスし、内容を読み取る |
| 収集件数 | 各フィード最大10件 |
| 重複排除 | 記事URLで判定し、`docs/news/` フォルダ内の既存 JSONL ファイルに未収録のもののみ追加 |
| 日本語翻訳・要約 | Gemini CLI が記事内容を読んで日本語で **300字以内**で要約する（外部API不使用） |
| URL取得失敗時 | Google Search で代替URLを検索し、再試行する |
| ファイル書き込み | Gemini CLI の Write ツールで JSONL・MD・JSON を直接書き込む |
| 実行タイミング | GitHub Actions で毎日 JST 10:00（UTC 01:00）自動実行 |

### 出力ファイル仕様

| ファイル | 内容 | 更新方式 |
|----------|------|---------|
| `docs/news_data.json` | 全記事の累積データ（JSON配列） | 追記（重複なし） |
| `docs/news/YYYY-MM-DD.jsonl` | 当日収集分（1行1記事のJSONL） | 毎日新規作成 |
| `docs/news.html` | 全記事ダッシュボード（自動生成HTML） | 毎回上書き |
| `docs/index.html` | 日付別アーカイブ一覧（自動生成HTML） | 毎回上書き |
| `logs/collect_news.log` | 収集ログ（成功・失敗・処理結果） | 追記 |

### JSONL 1レコードのフィールド定義

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

