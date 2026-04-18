# デフォルト画質劣化の修正計画

## Context

v1.0.0 から origin/main にかけてデフォルト（`--fast`/`--hq` なし）モードでダウンロードした動画の画質が劣化した、という報告。

### 原因の特定

コミット `54cf1cf` `perf: エンコード品質と yt-dlp 信頼性設定を改善` にて、h264_videotoolbox の品質パラメータを下記のように変更している:

```diff
- "-q:v", "55",
+ "-q:v", "25",
+ "-allow_sw", "1",
```

削除された `plan/plan.md` のコミット 2 の「根拠」には以下の記述がある:

> `-q:v` は VideoToolbox の品質スケール (0-100、低いほど高品質)。55 は中品質で、25 にすることでハードウェアエンコードの速度を維持しつつ大幅に画質向上

**この前提が完全な誤り**である。FFmpeg の `h264_videotoolbox` エンコーダーは Apple の VideoToolbox API を内部で呼び出し、`-q:v X` は `kVTCompressionPropertyKey_Quality`（0.0〜1.0、**高いほど高品質**）にマップされる（`libavcodec/videotoolboxenc.c` の `quality = global_quality / FF_QP2LAMBDA / 100.0` 変換）。

つまり:

- `-q:v 25` → quality = 0.25（**低画質**）
- `-q:v 55` → quality = 0.55（中画質、v1.0.0 の値）
- `-q:v 75` → quality = 0.75（高画質）

スケールの向きを逆に解釈していた結果、「画質改善のつもりが実際は大幅劣化」となっている。これがユーザー観測（修正後で画質が悪い）と完全に一致する。

フォーマット選択（[src/yt_downloader/downloader.py](../src/yt_downloader/downloader.py) の `build_format_selector`）は `bestvideo+bestaudio/best` のまま変更されていないため、ダウンロード元のフォーマット選択は v1.0.0 と同じ。劣化はエンコード段のみが原因。

### 期待される結果

- デフォルトモードの画質を `--hq` に近い実用品質まで回復する
- h264_videotoolbox のハードウェアエンコード速度は維持する（`--hq` への切り替えはしない）
- `-allow_sw 1` やリトライ設定（`socket_timeout` / `retries` / `fragment_retries`）等、品質に無関係な妥当な改善は維持する

---

## 修正対象ファイル

- [src/yt_downloader/config.py](../src/yt_downloader/config.py) — `ENCODER_PRESETS["normal"]` の `-q:v` 値とコメントを修正

---

## 実装方針

### Normal モード（`ENCODER_PRESETS["normal"]`）の修正

[src/yt_downloader/config.py](../src/yt_downloader/config.py) の `ENCODER_PRESETS["normal"]` を以下の方針で変更:

| パラメータ  | 現状 (origin/main) | 修正後                 | 理由                                                                        |
| ----------- | ------------------ | ---------------------- | --------------------------------------------------------------------------- |
| `-q:v`      | `25`               | `75`                   | VideoToolbox は高い方が高画質。75 は視覚的に `--hq` (crf 18) に近い実用品質 |
| `-allow_sw` | `1`                | `1`（維持）            | ハードウェア制限時のフォールバックとして妥当                                |
| `-b:a`      | `256k`             | `256k`（維持）         | 音声品質に問題なし                                                          |
| コメント    | 「低いほど高品質」 | 「**高いほど高品質**」 | 実際の挙動に合わせて訂正                                                    |

### なぜ `-q:v 75` か

- v1.0.0 時点の 55 は「中画質」。今回「より良く」を求めるなら 55 より少し上げるのが合理的
- 100 に近づけるほどビットレートが跳ね上がるが画質差は頭打ち。75 付近がファイルサイズとのバランスが良い一般的な推奨域
- `--hq` の CRF 18 は「視覚的無劣化」付近を狙うため、ハードウェアエンコードで近づけるなら 70〜80 が目安

### 他のパラメータはいじらない

- `"hq"` プリセット（`-preset medium` / `-crf 18`）は既に高品質設計なので触らない
- `"fast"` プリセット（ストリームコピー）は再エンコードしないため品質問題と無関係
- 共通オプションの `socket_timeout` / `retries` / `fragment_retries` は信頼性改善として妥当なので維持

---

## 変更箇所の詳細

### [src/yt_downloader/config.py](../src/yt_downloader/config.py)

```python
# h264_videotoolbox: Apple M1/M2/M3 のハードウェアエンコーダー
# -q:v 75    : VideoToolbox の品質スケール（高いほど高品質、0〜100）
# -allow_sw  : ハードウェア制限時にソフトウェアへフォールバック
"normal": [
    "-c:v", "h264_videotoolbox",
    "-q:v", "75",
    "-allow_sw", "1",
    "-c:a", "aac", "-b:a", AUDIO_BITRATE,
    "-movflags", "+faststart",
],
```

---

## 実装チェックリスト

- [x] [src/yt_downloader/config.py](../src/yt_downloader/config.py) の `ENCODER_PRESETS["normal"]` の `-q:v` 値を `25` → `75` に変更
- [x] 同ファイル内の該当コメント（`低いほど高品質` → `高いほど高品質`）を修正
- [x] `tests/test_config.py` を確認し、`-q:v` の具体値アサーションがないため既存テストは通ることを確認（現状、h264_videotoolbox の存在のみ検証）
- [x] `uv run pytest` で全テストが通ることを確認（110 件全件グリーン）
- [x] コミット作成

---

## コミット戦略

単一コミット。最小差分・即リバート可能・目的が一つに絞られている。

### Commit 1: `fix: normal モードのエンコード品質を修正 (-q:v スケール誤解釈)`

**変更ファイル**: [src/yt_downloader/config.py](../src/yt_downloader/config.py)

**コミットメッセージ**:

```
fix: normal モードのエンコード品質を修正 (-q:v スケール誤解釈)

h264_videotoolbox の -q:v は「高いほど高品質」だが、以前の perf コミット
(54cf1cf) では「低いほど高品質」と誤認し 55 → 25 に変更していたため、
デフォルトモードのダウンロード動画の画質が大幅に劣化していた。

-q:v を 75 に設定し、コメントも実際の挙動に合わせて訂正する。
HQ モードや fast モードは変更しない。
```

---

## テスト項目

ユーザーが変更の妥当性を確認するためのテスト項目:

- [ ] `uv run pytest` が全件グリーン
- [ ] `python main.py "https://youtu.be/plkG18G7_BY"` でデフォルトモードでダウンロードし、生成 MP4 の画質が修正前 (`downloads/before-...mp4`) と同等以上であること
- [ ] 上記ダウンロードが `--hq` で数十分かかる水準ではなく、数分程度で完了すること（ハードウェアエンコードが有効なままである）
- [ ] 生成 MP4 が QuickTime Player で問題なく再生できること（H.264 + AAC MP4 の出力が維持されていること）
- [ ] `python main.py "https://youtu.be/plkG18G7_BY" --fast` が従来通りストリームコピーで数秒で完了すること（fast モードは未変更）
- [ ] `python main.py "https://youtu.be/plkG18G7_BY" --hq` が従来通り動作すること（hq モードは未変更）

---

## リスクとロールバック

- **リスク**: `-q:v 75` でファイルサイズが v1.0.0（`-q:v 55`）より増える可能性がある。ただし M1 のハードウェアエンコードであり、画質とサイズのトレードオフとしては妥当な範囲。
- **ロールバック**: 単一 1 行変更のため、該当コミットを `git revert` するだけで元に戻せる。
- **代替案（採用しない）**: `--hq` をデフォルトにする案は「処理速度が犠牲になる」ためユーザー要望（速度優先）に反する。今回は却下。
