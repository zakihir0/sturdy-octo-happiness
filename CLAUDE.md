# CLAUDE.md

このファイルはClaude Codeがこのリポジトリで作業する際のガイダンスを提供します。

## ユーザー情報と人格定義

### ユーザープロフィール

- **目標**: 大規模言語モデル（LLM）の開発者を目指している
- **活動**: Kaggle・Devpost のコンペティションに積極的に参加
- **関心領域**:
  - GAFA（Google / Amazon / Meta / Apple）および主要AI企業の最新研究動向
  - LLM・基盤モデルの論文・技術ブログ・発表
  - AIエージェントアプリケーションのアーキテクチャとニュース
  - コンペティション向けのMLエンジニアリング手法

### Claudeへの行動指針

1. **情報収集アシスタントとして**
   - ArXiv・Google DeepMind・OpenAI・Meta AI・Anthropicなどの最新論文・ブログを積極的に参照・要約する
   - AIエージェント（LangChain / LangGraph / AutoGen / CrewAI等）の動向を把握し、関連情報を提供する
   - GAFAのAI関連プロダクト・APIの変更や発表を追跡する

2. **コンペティションサポートとして**
   - Kaggleでは EDA → ベースライン → アンサンブル の流れを意識したコードを提案する
   - Devpostでは MVP を素早く構築し、プレゼンに映えるデモを優先する
   - コンペのルール・評価指標を常に確認してから実装方針を提案する

3. **コミュニケーションスタイル**
   - 技術的に正確で簡潔な日本語を使う
   - 論文・ソースへの参照を積極的に示す
   - 実装例やコードスニペットを積極的に提供する

---

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
| コンペティション | Kaggle Blog | `https://medium.com/feed/kaggle-blog` |

### 収集・処理ルール

| 項目 | 仕様 |
|------|------|
| 収集主体 | **Claude Code** が WebFetch ツールで各ソースに直接アクセスし、内容を読み取る |
| 収集件数 | 各フィード最大10件 |
| 重複排除 | 記事URLで判定し、`docs/news_data.json` に未収録のもののみ追加 |
| 日本語翻訳・要約 | Claude Code が記事内容を読んで日本語で2〜3文に要約する（外部API不使用） |
| ファイル書き込み | Claude Code の Write ツールで JSONL・MD・JSON を直接書き込む |
| 実行タイミング | GitHub Actions で毎日 JST 10:00（UTC 01:00）自動実行 |

### 出力ファイル仕様

| ファイル | 内容 | 更新方式 |
|----------|------|---------|
| `docs/news_data.json` | 全記事の累積データ（JSON配列） | 追記（重複なし） |
| `docs/news/YYYY-MM-DD.jsonl` | 当日収集分（1行1記事のJSONL） | 毎日新規作成 |
| `docs/news/YYYY-MM-DD.md` | 当日収集分（カテゴリ別Markdown） | 毎日新規作成 |
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
  "summary_ja":  "Claude Code による日本語要約"
}
```

### Web 公開

| URL | 内容 |
|-----|------|
| `https://zakihir0.github.io/sturdy-octo-happiness/` | アーカイブ一覧（index.html） |
| `https://zakihir0.github.io/sturdy-octo-happiness/news.html` | 全記事ダッシュボード |
| `https://zakihir0.github.io/sturdy-octo-happiness/news/YYYY-MM-DD.md` | 日付別Markdown |
| `https://zakihir0.github.io/sturdy-octo-happiness/news/YYYY-MM-DD.jsonl` | 日付別JSONL |

---

## 実行方法

### GitHub Actions（通常運用）

```
GitHub Actions タブ → "Collect AI News" → Run workflow
```

`collect-news.yml` が `anthropics/claude-code-action` を呼び出し、Claude Code が以下を自律的に実行する：
1. 各ソースの RSS フィードを WebFetch で取得
2. 新着記事を読み取り、日本語で翻訳・要約
3. JSONL・MD・JSON ファイルを Write ツールで保存
4. 変更をコミット・プッシュ

### 必要な Secrets

| Secret名 | 用途 |
|----------|------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code の実行・`@claude` メンション・PR自動レビュー |

---

## 障害対応

### ログ確認手順

収集失敗時は `logs/collect_news.log` の最新ブロック（`=== 収集開始 ===` 〜 `=== 収集終了 ===`）を確認し、`[WARN]` / `[ERROR]` 行から原因を特定する。

### 既知の失敗パターン

| 日付 | フィード | エラー種別 | 原因 | 状態 |
|------|---------|-----------|------|------|
| 2026-03-05 | 全フィード | `URLError: 403 Forbidden` | Claude Code on the web のプロキシがアウトバウンドを遮断 | 未解決（GitHub Actions で実行すること） |

### 対処方針

| エラー種別 | 対処 |
|-----------|------|
| ネットワーク制限（403等） | GitHub Actions で実行する（ローカル・web環境では不可） |
| RSS URL変更 | `collect-news.yml` のプロンプト内 URL リストを更新する |
| WebFetch タイムアウト | フィードURLを代替に変更するか、対象ソースを一時除外する |

---

## リポジトリ構造

```
sturdy-octo-happiness/
├── CLAUDE.md                         # このファイル
├── README.md
├── .claude/
│   └── settings.json                 # Claude Code 設定
├── .github/
│   └── workflows/
│       ├── collect-news.yml          # ニュース収集（毎日 JST 10:00）
│       ├── claude.yml                # @claude メンション連携
│       └── claude-code-review.yml   # PR 自動コードレビュー
├── scripts/
│   └── collect_news.py               # HTML生成ヘルパースクリプト
├── docs/                             # GitHub Pages 公開ディレクトリ
│   ├── index.html                    # アーカイブ一覧（自動生成）
│   ├── news.html                     # 全記事ダッシュボード（自動生成）
│   ├── news_data.json                # 全記事累積データ（自動生成）
│   └── news/
│       ├── YYYY-MM-DD.jsonl          # 日付別 JSONL（自動生成）
│       └── YYYY-MM-DD.md             # 日付別 Markdown（自動生成）
└── logs/
    └── collect_news.log              # 収集ログ（自動生成）
```
