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

### Web 公開

| URL | 内容 |
|-----|------|
| `https://zakihir0.github.io/sturdy-octo-happiness/` | アーカイブ一覧（index.html） |
| `https://zakihir0.github.io/sturdy-octo-happiness/news.html` | 全記事ダッシュボード |
| `https://zakihir0.github.io/sturdy-octo-happiness/news/YYYY-MM-DD.jsonl` | 日付別JSONL |

---

## 実行方法

### GitHub Actions（通常運用）

毎日 JST 10:00 に Step 1 が自動起動し、Step 2 → Step 3 と連鎖実行される。
手動実行する場合は各ワークフローを順に `Run workflow` する。

| ステップ | ワークフロー | 内容 |
|----------|------------|------|
| Step 1 | `Step 1 - Collect URLs` | RSS取得・重複排除・中間JSON保存 |
| Step 2 | `Step 2 - Generate Summaries` | 記事本文取得・日本語要約生成・JSONL保存 |
| Step 3 | `Step 3 - Generate HTML` | JSONL読み込み・HTML再生成 |

### 必要な Secrets

| Secret名 | 用途 |
|----------|------|
| `GEMINI_API_KEY` | Gemini CLI の実行（Google AI Studio で取得） |

---

## 障害対応

### ログ確認手順

収集失敗時は `logs/collect_news.log` の最新ブロック（`=== 収集開始 ===` 〜 `=== 収集終了 ===`）を確認し、`[WARN]` / `[ERROR]` 行から原因を特定する。

### 対処方針

| エラー種別 | 対処 |
|-----------|------|
| ネットワーク制限（403等） | GitHub Actions で実行する（ローカル・web環境では不可） |
| RSS URL変更 | `.github/prompts/collect-urls.md` の URL リストを更新する |
| URL取得タイムアウト | Google Search で代替URLを検索して再試行する |

---

## リポジトリ構造

```
sturdy-octo-happiness/
├── GEMINI.md                         # このファイル
├── CLAUDE.md                         # Claude Code 用設定
├── README.md
├── .github/
│   ├── prompts/
│   │   ├── collect-urls.md           # Step 1 プロンプト（RSS収集）
│   │   └── generate-summaries.md     # Step 2 プロンプト（要約生成）
│   └── workflows/
│       ├── collect-urls.yml          # Step 1: RSS収集（毎日 JST 10:00 自動起動）
│       ├── generate-summaries.yml    # Step 2: 要約生成（Step 1 完了後に連鎖）
│       ├── generate-html.yml         # Step 3: HTML生成（Step 2 完了後に連鎖）
│       ├── deploy-pages.yml          # GitHub Pages デプロイ（docs/ 変更時）
│       ├── claude.yml                # @claude メンション連携（Claude Code 専用）
│       └── claude-code-review.yml   # PR 自動コードレビュー（Claude Code 専用）
├── scripts/
│   ├── collect_news.py               # Step 3: HTML生成スクリプト
│   └── build_prompt.py               # Step 2: プロンプト構築スクリプト
├── docs/                             # GitHub Pages 公開ディレクトリ
│   ├── index.html                    # アーカイブ一覧（自動生成）
│   ├── news.html                     # 全記事ダッシュボード（自動生成）
│   ├── news_data.json                # 全記事累積データ（自動生成）
│   └── news/
│       ├── .pending/YYYY-MM-DD/      # 中間ファイル（処理待ち）
│       └── YYYY-MM-DD.jsonl          # 日付別 JSONL（自動生成）
└── logs/
    └── collect_news.log              # 収集ログ（自動生成）
```
