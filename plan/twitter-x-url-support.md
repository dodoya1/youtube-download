# Twitter/X URL 対応計画

## Context

現状 `yt-downloader` は YouTube の URL のみをサポートしている (URL 判定が `youtube.com` 決め打ち)。ユーザーは Twitter/X の投稿内動画もダウンロードしたい。

**重要な前提**: このプロジェクトは既に **yt-dlp** を使っており、yt-dlp は **Twitter/X を公式にネイティブサポートしている** (専用の Twitter extractor が active maintain されている)。

- 追加 OSS/ライブラリ導入は **不要**
- Twitter/X API 使用は **不要** (yt-dlp がゲストトークンで非認証アクセス)
- **費用ゼロ**
- 信頼性: yt-dlp 本体 ([github.com/yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp)) は最大手の downloader OSS で、Twitter extractor も数日単位で追随更新されている

よって作業は「**既存コードを YouTube 専用から Twitter/X を含むマルチプラットフォーム対応に薄く拡張する**」こと。

### ユーザー合意済みの方針

| 項目             | 決定                                                             |
| ---------------- | ---------------------------------------------------------------- |
| 対応 URL         | 単一ツイート内の動画 + Twitter Spaces (音声)                     |
| 保存先           | `downloads/twitter/<ユーザー名>/`                                |
| 認証             | 不要。公開ツイートのみでよい (`--cookies-from-browser` は見送り) |
| エンコードモード | 既存の `fast` / `normal` / `hq` をそのまま適用                   |

---

## 対応 URL パターン

| 種別             | URL 例                                                                         | 備考                                                          |
| ---------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| `twitter_video`  | `https://x.com/<user>/status/<id>`<br>`https://twitter.com/<user>/status/<id>` | username は URL から抽出可                                    |
| `twitter_spaces` | `https://x.com/i/spaces/<id>`<br>`https://twitter.com/i/spaces/<id>`           | URL に username を含まない → yt-dlp の `%(uploader_id)s` 使用 |

Spaces は映像なし (音声のみ) のため、内部的に強制 `audio_only=True` 相当で動かす必要がある。

---

## チェックリスト (実装進捗)

### Commit 1: URL 判定

- [x] `src/yt_downloader/url.py` に Twitter/X パターンを追加
- [x] `detect_url_type` に `twitter_video` / `twitter_spaces` を追加
- [x] `extract_twitter_username` 関数を追加
- [x] `tests/test_url.py` に対応テストを追加
- [x] `uv run pytest tests/test_url.py` 緑確認
- [x] コミット

### Commit 2: 保存先解決

- [x] `src/yt_downloader/config.py` に `TWITTER_DIR` 追加
- [x] `_resolve_output_paths` に Twitter 分岐追加
- [x] `tests/test_downloader.py` に Twitter 系出力パステスト追加
- [x] `uv run pytest` 緑確認
- [x] コミット

### Commit 3: Spaces 強制 audio-only

- [x] `download()` 内で Spaces の場合に `audio_only=True` にする
- [x] Spaces 用の outtmpl を `%(uploader_id)s` で組み立てる
- [x] テスト追加
- [x] `uv run pytest` 緑確認
- [x] コミット

### Commit 4: ドキュメント

- [x] `README.md` に Twitter/X サポート追記
- [x] `README-en.md` に Twitter/X サポート追記
- [x] コミット

---

## 変更ファイル

| ファイル                          | 変更内容                                                        |
| --------------------------------- | --------------------------------------------------------------- |
| `src/yt_downloader/url.py`        | Twitter/X 判定と username 抽出を追加                            |
| `src/yt_downloader/config.py`     | `TWITTER_DIR = OUTPUT_DIR / "twitter"` を追加                   |
| `src/yt_downloader/downloader.py` | `_resolve_output_paths` を拡張、Spaces 時の強制 audio-only 処理 |
| `tests/test_url.py`               | Twitter URL 判定・username 抽出テスト追加                       |
| `tests/test_downloader.py`        | Twitter 系 URL の出力パス解決テスト追加                         |
| `README.md` / `README-en.md`      | Twitter/X サポートの記載追加                                    |

---

## 設計詳細

### 1. URL 判定

```python
_TWITTER_VIDEO_PATTERNS = (
    r"(?:twitter|x)\.com/([\w\-]+)/status/\d+",
)
_TWITTER_SPACES_PATTERNS = (
    r"(?:twitter|x)\.com/i/spaces/[\w\-]+",
)
```

判定順: `twitter_spaces` → `twitter_video` → YouTube 系。Twitter 判定を先にすることで `/i/spaces/` が `status/` と混同されない。

### 2. 保存先解決

- **`twitter_video`**: username を URL から抽出 → `downloads/twitter/<username>/`
- **`twitter_spaces`**: URL に username が無いため `out_dir` は `downloads/twitter` とし、`download()` 側で Spaces のみ `outtmpl` を `%(uploader_id)s` で分岐

### 3. Spaces → 強制 audio-only

```python
if url_type == "twitter_spaces" and not audio_only:
    warn("Twitter Spaces は音声のみです。自動的に --audio-only 相当で処理します")
    audio_only = True
```

### 4. CLI の変更

`argparse` レイヤーには変更なし。

### 5. フォーマット選択

既存の `build_format_selector` はフォールバックチェーンを持っているため変更不要。

---

## スコープ外

- ユーザープロフィール全動画の一括ダウンロード
- 認証 cookie 対応
- Twitter のアーカイブ機能

---

## テスト項目

### 自動テスト

- [ ] `uv run pytest tests/test_url.py -v`
- [ ] `uv run pytest tests/test_downloader.py -v`
- [ ] `uv run pytest`（全体）

### 手動 E2E テスト

- [ ] `python main.py "https://x.com/<user>/status/<id>"` で MP4 が `downloads/twitter/<user>/` に保存される
- [ ] 旧ドメイン `twitter.com/<user>/status/<id>` でも同様に動く
- [ ] `--fast` が数秒で完了し QuickTime で再生できる
- [ ] `--audio-only` で MP3 が `downloads/twitter/<user>/` に出力される
- [ ] Spaces URL で自動音声のみ処理、`downloads/twitter/<uploader_id>/` に MP3 保存
- [ ] YouTube URL + Twitter URL 混在指定で双方が別ディレクトリに保存される
- [ ] 存在しない Twitter URL でエラー終了しても他 URL は続行
- [ ] 既存 YouTube 単発 / プレイリスト / チャンネル処理に影響なし

### リグレッション

- [ ] YouTube 単発 `--fast` が従来通り
- [ ] YouTube チャンネル URL が `downloads/<channel>/` に保存される (`downloads/twitter/` に入らない)

---

## コミット戦略

| #   | 種別   | 対象                                         | メッセージ                                                        |
| --- | ------ | -------------------------------------------- | ----------------------------------------------------------------- |
| 1   | `feat` | url.py, test_url.py                          | `feat: Twitter/X URL の種別判定と username 抽出を追加`            |
| 2   | `feat` | config.py, downloader.py, test_downloader.py | `feat: Twitter/X 動画の保存先を downloads/twitter/<user>/ に解決` |
| 3   | `feat` | downloader.py, test_downloader.py            | `feat: Twitter Spaces を自動で音声のみ処理する`                   |
| 4   | `docs` | README.md, README-en.md                      | `docs: Twitter/X サポートを README に記載`                        |
