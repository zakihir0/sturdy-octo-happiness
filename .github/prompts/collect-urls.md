# Step 1: URL収集

以下の手順でAI/LLMニュースのURLとメタデータを収集し、中間ファイルに保存してください。
要約生成・HTML生成・コミット・プッシュはワークフローが別途実行します。

---

## 手順 1. RSSフィードの取得

「収集対象ソース」に記載された各RSSフィード（各最大10件）を以下の優先順位で取得する。

### 1-A. WebFetch による直接取得

「収集対象ソース」の RSS URL を WebFetch で取得する。成功した場合はそのまま記事を抽出する。

### 1-B. WebSearch によるリカバリ（1-Aが失敗した場合）

WebFetch が失敗（403 / タイムアウト / URL変更等）した場合、以下の手順で代替URLを探す：

1. `WebSearch` で `{ソース名} RSS feed site:` 等のクエリを使い、
   公式の最新 RSS URL を検索する（例: `"Anthropic blog RSS feed"`）
2. 見つかった RSS URL を WebFetch で取得し、記事を抽出する
3. 成功した場合、ログに `[INFO] WebSearch で代替URL発見: {url}` と記録する

### 1-C. 最終フォールバック（1-Aと1-Bが両方失敗した場合）

1. WebSearch で `{ソース名} latest AI news` 等のクエリで直接記事を検索する
2. 検索結果から記事タイトル・URL・概要を抽出して記事リストとして扱う
3. ログに `[WARN] RSS取得失敗のためWebSearchから直接記事収集: {ソース名}` と記録する

## 手順 2. 既存データとの照合（重複排除）

`docs/news/` フォルダ内に存在する全 JSONL ファイル（`YYYY-MM-DD.jsonl`）を Read ツールで読み込み、
全レコードの `link` フィールドを収集して「既存URLセット」を作る。
`docs/news/.pending/` 内の全 JSON ファイルも同様に Read で読み込み、既存URLセットに追加する。
以降の保存処理では、この既存URLセットに含まれる記事はスキップする。

## 手順 3. 中間ファイルへの保存

今日の日付（UTC）を YYYY-MM-DD 形式で取得する。
新着記事を `docs/news/.pending/YYYY-MM-DD/` ディレクトリ内に、**記事1件＝1ファイル** の形式で保存する。
ファイル名はゼロ埋め3桁の連番（`001.json`, `002.json`, ...）を使用する。
各ファイルの内容は1レコード分の通常 JSON 形式（JSONL ではなく改行あり整形 JSON）とする。

保存するフィールド（`summary_ja` は含めない。Step 2 で生成する）:
- `title`: 記事タイトル（英語原文）
- `link`: 記事URL
- `description`: RSS概要テキスト
- `date`: pubDate（RSS記載の公開日）
- `source`: ソース名（例: ArXiv cs.AI）
- `category`: カテゴリ名（例: 論文 - AI全般）
- `fetched_at`: 収集日時（ISO 8601 UTC）

## 手順 4. ログの記録

`logs/collect_news.log` に今回の収集結果を追記する。記載内容：
- 収集開始日時・終了日時
- 各フィードの取得成否
- 新着追加件数（中間ファイルに保存した件数）
