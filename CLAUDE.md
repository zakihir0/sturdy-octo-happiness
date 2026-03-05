# CLAUDE.md

このファイルはClaude Codeがこのリポジトリで作業する際のガイダンスを提供します。

## プロジェクト概要

**sturdy-octo-happiness** はシンプルなリポジトリです。

## リポジトリ構造

```
sturdy-octo-happiness/
├── README.md
├── CLAUDE.md
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
