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

Claudeは以下の人格・スタンスでユーザーを支援すること。

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

## ニュース収集ルール

### 収集対象ソース

| カテゴリ | ソース | RSSフィード |
|----------|--------|------------|
| 論文（AI全般） | ArXiv cs.AI | `https://arxiv.org/rss/cs.AI` |
| 論文（機械学習） | ArXiv cs.LG | `https://arxiv.org/rss/cs.LG` |
| 論文（計算・言語） | ArXiv cs.CL | `https://arxiv.org/rss/cs.CL` |
| 企業ブログ | Google DeepMind | `https://deepmind.google/blog/rss.xml` |
| 企業ブログ | Anthropic | `https://www.anthropic.com/rss.xml` |
| 企業ブログ | Meta AI | `https://ai.meta.com/blog/rss/` |
| AI全般ニュース | TechCrunch AI | `https://techcrunch.com/category/artificial-intelligence/feed/` |
| コンペ | Kaggle Blog | `https://medium.com/feed/kaggle-blog` |

### 収集・更新ルール

1. **実行方法**: `python scripts/collect_news.py` で収集し `docs/news.html` を生成する
2. **収集件数**: 各フィードから最大10件、合計80件程度
3. **出力形式**: カテゴリ別に分類したスタンドアロンHTMLページ
4. **更新タイミング**: ユーザーから「ニュースを更新して」と依頼があったとき
5. **要約**: 各記事のタイトル・日付・リンク・概要（summary）を表示する

### Claudeへの収集時の指示

- `python scripts/collect_news.py` を実行して `docs/news.html` を生成する
- 生成後、注目すべき論文・ニュースを3〜5件ピックアップして日本語で要約を提供する
- ArXivの論文はアブストラクトをもとに1〜2文で研究内容を説明する

### 失敗原因の記録ルール

収集実行後、`logs/collect_news.log` に失敗が記録されていた場合、Claudeは以下の手順で対応すること。

1. **ログを確認する**
   - `logs/collect_news.log` の最新実行ブロック（`=== 収集開始 ===` から `=== 収集終了 ===` まで）を読む
   - `[WARN]` / `[ERROR]` 行を抽出して失敗フィードと原因を把握する

2. **原因を分類して CLAUDE.md に記録する**
   - 下記「既知の失敗パターン」テーブルを更新する
   - 新しいエラー種別が出たら行を追加する
   - 解決済みになったら「状態」を `解決済み` に変更する

3. **対処方針を提案する**
   - ネットワーク制限: 環境の制約として記録し、ローカル実行を案内する
   - RSS URL変更: `scripts/collect_news.py` の `FEEDS` リストを修正する
   - タイムアウト: `timeout=15` を延ばすか、フィードURLを代替に差し替える
   - XML解析エラー: フィードのエンコーディングや構造を調査して `parse_feed` を修正する

### 既知の失敗パターン

| 日付 | フィード | エラー種別 | 原因 | 状態 |
|------|---------|-----------|------|------|
| 2026-03-05 | 全フィード | `URLError: Tunnel connection failed: 403 Forbidden` | 実行環境のネットワークプロキシがアウトバウンド接続を遮断 | 未解決（環境制約） |

## プロジェクト概要

**sturdy-octo-happiness** はLLM開発・AIコンペティション参加のための作業リポジトリです。

## リポジトリ構造

```
sturdy-octo-happiness/
├── README.md
├── CLAUDE.md
├── docs/
│   └── news.html           # 収集したニュースのビューワー（自動生成）
├── scripts/
│   └── collect_news.py     # ニュース収集スクリプト
└── .claude/
    ├── settings.json       # Claude Code 設定（SessionStart フック）
    └── hooks/
        └── session-start.sh  # セッション開始時に実行されるフック
```

## 開発環境セットアップ

現在、このプロジェクトに外部依存関係はありません。

## Claude Code フック

### SessionStart フック

`.claude/hooks/session-start.sh` がセッション開始時に自動実行されます。

- リモート環境（Claude Code on the web）でのみ動作します
- 依存関係が追加された場合はこのスクリプトを更新してください

## ブランチ戦略

- `main` / `master`: 本番ブランチ
- `claude/*`: Claude Code による自動作業ブランチ
