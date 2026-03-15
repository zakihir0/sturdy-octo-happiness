# Step 2: 要約生成（1記事）

以下の手順でStep 1が収集した記事の本文を取得し、日本語要約を生成・保存してください。
HTML生成・コミット・プッシュはワークフローが別途実行します。

---

## 処理対象の記事（1件）

```json
{{PENDING_ARTICLES}}
```

---

## 手順 1. 記事本文の取得（対話モード相当のリサーチフロー）

今日の日付（UTC）を YYYY-MM-DD 形式で取得する。

以下の優先順位で本文取得を試みる。**各ステップで十分な本文（500字相当以上）が取得できたら次のステップには進まない。**

### 1-A. ソース別の最適URLでWebFetch

`source` フィールドに応じて最適なURLを構築してWebFetchする：

- **ArXiv系**（source に "ArXiv" を含む場合）:
  1. まず `https://ar5iv.org/abs/<arxiv_id>` を試す（LaTeXレンダリング済みHTML）
  2. 失敗したら `link` フィールドのURLをそのまま使う

- **その他ソース**（Anthropic / Meta AI / Google DeepMind / TechCrunch 等）:
  1. `link` フィールドのURLをWebFetchする

### 1-B. WebSearchによるリカバリ（1-Aで失敗した場合）

1-AのWebFetchが失敗した場合、またはHTMLのノイズが多く本文が読み取れない場合は、
以下の方法でWebSearchを実行して代替コンテンツを取得する：

1. `WebSearch` で `{title} {source}` をクエリとして検索する
2. 検索結果から最も信頼できる記事・解説ページのURLを選ぶ
3. 選んだURLをWebFetchで取得する

### 1-C. descriptionによるフォールバック（1-Aと1-Bがどちらも失敗した場合）

`description` フィールドと自身の学習知識を組み合わせて要約を生成する。
ログには `[WARN] WebFetch/WebSearch 失敗のためdescriptionから生成` と記録する。

---

## 手順 2. 日本語要約の生成

取得した本文から **300字以内** の日本語要約を書く。`description` のコピーにならないよう独自に構成すること。

---

## 手順 3. ファイル保存

`summary_ja` を加えた完全なレコードを `docs/news/YYYY-MM-DD.jsonl` に追記する。
- ファイルが存在しない場合は新規作成する
- 既存の行は変更せず、末尾に1行追加する形で Write ツールを使用する
- 「JSONL 1レコードのフィールド定義」に従うこと

---

## 手順 4. ログの記録

`logs/collect_news.log` に今回の処理結果を追記する。記載内容：
- 処理日時・記事タイトル・成否
- 使用した取得方法（1-A / 1-B / 1-C）
- WebFetch/WebSearch 失敗時はその旨を記録する
