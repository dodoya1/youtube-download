# YouTube Downloader リファクタリング計画書

## Context

現在の YouTube ダウンローダーは `main.py` 単一ファイル (1,035行) で構成されている。機能的には動作しているが、以下の課題がある:

- **品質設定が最適でない**: h264_videotoolbox の `-q:v 55` は保守的すぎて画質が低い
- **docstring が非標準**: reStructuredText 形式で、Google style の方が一般的
- **モノリシック構成**: 全コードが1ファイルに集中し、テスト不可能
- **スレッド安全性の問題**: EncodingSpinner に Lock がなく、カプセル化違反あり
- **テストゼロ**: 品質保証の仕組みがない
- **英語ドキュメントなし**: 国際的なアクセシビリティに欠ける

---

## コミット戦略

全8コミット、リスクの低い順に実施。各コミットは独立してレビュー可能。

| #   | コミットメッセージ                                                | 変更対象    | リスク |
| --- | ----------------------------------------------------------------- | ----------- | ------ |
| 1   | `chore: pyproject.toml 追加と .gitignore 拡充`                    | 2ファイル   | なし   |
| 2   | `perf: エンコード品質と yt-dlp 信頼性設定を改善`                  | main.py     | 低     |
| 3   | `docs: docstring を reStructuredText から Google style に変換`    | main.py     | なし   |
| 4   | `refactor: スレッド安全性・カプセル化・型ヒントを修正`            | main.py     | 低     |
| 5   | `refactor: main.py をモジュールパッケージ構成に分割`              | ~12ファイル | 中     |
| 6   | `test: url, ui, config, tracker モジュールのユニットテスト追加`   | 5ファイル   | なし   |
| 7   | `test: encoding, hooks, format_selector, downloader のテスト追加` | 5ファイル   | なし   |
| 8   | `docs: 英語版 README 作成と言語切替リンク追加`                    | 2ファイル   | なし   |

---

## Phase A: インフラ整備

### Commit 1: `chore: pyproject.toml 追加と .gitignore 拡充`

インフラのみ。コード変更なし。

- [x] `pyproject.toml` を新規作成
  - `[project]`: name="yt-downloader", version="1.0.0", requires-python=">=3.10", dependencies=["yt-dlp"]
  - `[project.scripts]`: `yt-downloader = "yt_downloader.cli:main"`
  - `[tool.pytest.ini_options]`: testpaths=["tests"]
  - `[build-system]`: hatchling を使用
  - `[dependency-groups]`: dev = ["pytest", "pytest-cov"]
- [x] `.gitignore` を拡充
  - 追加: `.venv/`, `__pycache__/`, `*.pyc`, `*.pyo`, `.mypy_cache/`, `.pytest_cache/`, `*.egg-info/`, `dist/`, `build/`, `.ruff_cache/`

**変更ファイル**: `pyproject.toml` (新規), `.gitignore` (修正)

---

## Phase B: パフォーマンス・品質チューニング

### Commit 2: `perf: エンコード品質と yt-dlp 信頼性設定を改善`

値変更のみの小さな差分。レビューしやすく、問題発生時にリバート容易。

- [x] **Normal モード** (h264_videotoolbox) の改善
  - `-q:v 55` → `-q:v 25` (大幅な画質向上、速度変化なし)
  - `-allow_sw 1` 追加 (ハードウェアエンコーダーが制限に達した場合のフォールバック)
  - `-b:a 192k` → `-b:a 256k` (音声品質向上)
- [x] **HQ モード** (libx264) の改善
  - `-preset slow` → `-preset medium` (30-40%高速化、品質差はほぼ知覚不能)
  - `-b:a 192k` → `-b:a 256k`
- [x] **yt-dlp 共通オプション**に追加
  - `"socket_timeout": 30` (タイムアウト設定)
  - `"retries": 10` (リトライ回数)
  - `"fragment_retries": 10` (フラグメントリトライ)

**変更ファイル**: `main.py`

**根拠**:

- `-q:v` は VideoToolbox の品質スケール (0-100、低いほど高品質)。55 は中品質で、25 にすることでハードウェアエンコードの速度を維持しつつ大幅に画質向上
- preset medium は slow の 95% の品質を 60% の時間で実現 (4K 1時間の動画: 45分 → 27分)
- yt-dlp のリトライ設定で不安定なネットワーク環境でのダウンロード信頼性向上

---

## Phase C: Docstring マイグレーション

### Commit 3: `docs: docstring を reStructuredText から Google style に変換`

機械的な変換。ロジック変更なし。コード分割前に実施することで、1ファイルでの差分レビューが容易。

- [x] 全クラス・メソッド・関数の docstring を Google style に変換
  - `:param name:` / `:type name:` → `Args:` セクション内に `name (型): 説明`
  - `:return:` / `:rtype:` → `Returns:` セクションに統合
  - `:raises:` → `Raises:` セクション
- [x] モジュール docstring のファイル名を `yt_downloader.py` → `main.py` に修正
- [x] docstring の説明文は日本語を維持

**変換例**:

```python
# Before (reStructuredText)
def detect_url_type(url: str) -> str:
    """
    YouTube URL の種別を判定する。

    :param url: YouTube URL
    :type url: str
    :return: ``"channel"`` / ``"playlist"`` / ``"video"``
    :rtype: str
    """

# After (Google style)
def detect_url_type(url: str) -> str:
    """YouTube URL の種別を判定する。

    Args:
        url: YouTube URL

    Returns:
        "channel" / "playlist" / "video"
    """
```

**注意**: 型ヒントが関数シグネチャに既にある場合、Args の型は省略する (DRY原則)。

**変更ファイル**: `main.py`

---

## Phase D: リファクタリング (単一ファイル内)

### Commit 4: `refactor: スレッド安全性・カプセル化・型ヒントを修正`

コード分割前に単一ファイル内で修正することで、差分が自己完結的になる。

- [x] **スレッド安全性の修正** (`EncodingSpinner`)
  - `threading.Lock` を追加し、`label` と `_start_ts` の読み書きを保護
  - 二重 `start()` 呼び出し防止ガードを追加
- [x] **カプセル化違反の修正**
  - `DownloadTracker.has_current() -> bool` パブリックメソッド追加 (line 722 の `tracker._current` 直接アクセスを置換)
  - `EncodingSpinner.force_stop()` パブリックメソッド追加 (line 867 の `spinner._stop_evt.set()` 直接アクセスを置換)
  - `EncodingSpinner.set_label(label: str)` メソッド追加 (line 480 の直接属性変更を置換)
- [x] **型ヒントの修正**
  - `callable` (小文字) → `Callable[[dict], None]` (from `collections.abc`)
  - `# type: ignore` コメントの原因を解消
- [x] **クロージャ内の状態ハック修正**
  - `make_progress_hook()` 内の `last_filename: list[str | None] = [None]` → `nonlocal` 変数に変更
- [x] **DRY 違反の修正**
  - `DownloadTracker` 内の重複した ID チェックロジックを `_is_recorded(vid_id, target_list)` プライベートメソッドに抽出
  - 重複している音声ビットレート → 定数 `AUDIO_BITRATE` に

**変更ファイル**: `main.py`

---

## Phase E: コード分割

### Commit 5: `refactor: main.py をモジュールパッケージ構成に分割`

最大の構造変更。`main.py` (1,035行) を 10 モジュールに分割。

- [x] ディレクトリ構造の作成

```
youtube-download/
├── src/
│   └── yt_downloader/
│       ├── __init__.py         # パッケージ初期化、バージョン
│       ├── cli.py              # parse_args(), main() (~130行)
│       ├── config.py           # 定数、エンコーダープリセット (~80行)
│       ├── downloader.py       # download(), build_ydl_opts(), build_format_selector() (~250行)
│       ├── encoding.py         # EncodingSpinner クラス (~100行)
│       ├── hooks.py            # make_progress_hook(), make_postprocessor_hook() (~130行)
│       ├── logger.py           # YtDlpLogger クラス (~70行)
│       ├── tracker.py          # DownloadTracker クラス (~120行)
│       ├── ui.py               # c(), info(), ok(), warn(), error(), fmt_seconds() (~75行)
│       └── url.py              # detect_url_type(), extract_channel_name() (~45行)
├── tests/
│   └── __init__.py
├── main.py                     # 薄いエントリポイント (~10行)
└── ...
```

- [x] **各モジュールの依存関係** (循環依存なし)

```
config, ui, url (リーフ: 外部依存なし)
    ↓
tracker, logger, encoding (中間: ui, config に依存)
    ↓
hooks (tracker, encoding の型に依存)
    ↓
downloader (ほぼ全モジュールに依存)
    ↓
cli (downloader, config, ui に依存)
```

- [x] **config.py の設計**
  - エンコーダープリセットを辞書で定義:
    ```python
    ENCODER_PRESETS = {
        "fast": ["-c", "copy", "-movflags", "+faststart"],
        "normal": ["-c:v", "h264_videotoolbox", "-q:v", "25", ...],
        "hq": ["-c:v", "libx264", "-crf", FFMPEG_CRF, "-preset", "medium", ...],
    }
    ```
  - `OUTPUT_DIR` のパス解決: `Path(__file__).resolve().parent.parent.parent / "downloads"` (src/yt_downloader/config.py → src/yt_downloader → src → project root)

- [x] **download() 関数の分割** (元 139行 → 各 40行以下)
  - `_resolve_output_paths(url_type, url, use_archive) -> tuple[Path, str | None]`
  - `_build_date_range(date_after, date_before) -> DateRange | None`
  - `_print_download_config(...)` (設定情報の表示)
  - `download()` はこれらを呼ぶオーケストレーターに

- [x] **build_ydl_opts() の簡略化**
  - エンコーダー設定を `config.ENCODER_PRESETS` からルックアップ
  - 3分岐の if/elif/else → 辞書参照に

- [x] **main.py を薄いエントリポイントに**

  ```python
  #!/usr/bin/env python3
  """YouTube Downloader エントリポイント。"""
  import sys
  from pathlib import Path

  sys.path.insert(0, str(Path(__file__).parent / "src"))

  from yt_downloader.cli import main

  if __name__ == "__main__":
      main()
  ```

- [x] `pyproject.toml` を更新 (`[tool.hatch.build.targets.wheel]` で `packages = ["src/yt_downloader"]`)

**変更ファイル**: `main.py` (大幅縮小), `src/yt_downloader/*.py` (全て新規), `pyproject.toml` (修正)

---

## Phase F: テスト

### Commit 6: `test: url, ui, config, tracker モジュールのユニットテスト追加`

外部依存なし (yt-dlp モック不要) のリーフモジュールから。

- [x] `tests/conftest.py` - 共通 fixture
  - `mock_info_dict`: 現実的な yt-dlp info_dict
  - `non_tty_stdout`: `sys.stdout.isatty()` を False にパッチ
- [x] `tests/test_url.py`
  - `detect_url_type()`: チャンネル URL (4パターン), プレイリスト URL, 動画 URL
  - `extract_channel_name()`: 全パターンの抽出、マッチしない場合の "unknown_channel"
- [x] `tests/test_ui.py`
  - `c()`: TTY 時のカラーコード付与、非 TTY 時のスルー
  - `fmt_seconds()`: 0秒, 59秒, 60秒, 3661秒 等の境界値
  - `info()`, `ok()`, `warn()`, `error()`: 出力フォーマットの検証
- [x] `tests/test_config.py`
  - 定数の型・値チェック (`QUALITY_OPTIONS`, `FORMAT_OPTIONS`, `ENCODER_PRESETS`)
  - `OUTPUT_DIR` / `ARCHIVE_DIR` パスの整合性
- [x] `tests/test_tracker.py`
  - `set_current()` → `record_success()` の基本フロー
  - 重複チェック: 同じ ID で2回 `record_success()` → 1件
  - `record_failure()` が成功リストから除去する動作
  - `has_current()` の真偽値テスト
  - `print_summary()` の出力フォーマット (stdout キャプチャ)

**変更ファイル**: `tests/conftest.py`, `tests/test_url.py`, `tests/test_ui.py`, `tests/test_config.py`, `tests/test_tracker.py` (全て新規)

### Commit 7: `test: encoding, hooks, format_selector, downloader のテスト追加`

yt-dlp のモックやスレッドを扱うテスト。

- [ ] `tests/test_encoding.py`
  - `EncodingSpinner` の start/stop ライフサイクル
  - `set_label()` のスレッド安全性 (Lock 取得の確認)
  - `force_stop()` でスレッドが確実に終了すること
- [ ] `tests/test_hooks.py`
  - `make_progress_hook()`: downloading/finished/error ステータスの処理
  - `make_postprocessor_hook()`: started/finished イベントでスピナー制御
  - tracker への記録が正しく行われること
- [ ] `tests/test_format_selector.py`
  - `build_format_selector()`: 全モード (fast/normal/hq) x 全品質 (best/1080/720) の組み合わせ
  - 出力文字列に期待するコーデック指定が含まれること
- [ ] `tests/test_downloader.py`
  - `build_ydl_opts()`: 各モードで正しいオプション辞書が構築されること
  - `download()`: `yt_dlp.YoutubeDL` をモックして正常系・エラー系を検証

**変更ファイル**: `tests/test_encoding.py`, `tests/test_hooks.py`, `tests/test_format_selector.py`, `tests/test_downloader.py` (全て新規)

---

## Phase G: ドキュメント

### Commit 8: `docs: 英語版 README 作成と言語切替リンク追加`

- [ ] `README-en.md` を新規作成 (README.md の英語翻訳)
  - セクション構成は README.md と同一
  - ディレクトリ構成は新しい `src/` レイアウトに更新
- [ ] `README.md` の先頭に言語切替リンクを追加
  - `[English](README-en.md) | 日本語`
- [ ] `README-en.md` の先頭にも言語切替リンク
  - `English | [日本語](README.md)`
- [ ] 両 README のディレクトリ構成セクションを新構成に更新

**変更ファイル**: `README.md` (修正), `README-en.md` (新規)

---

## テスト項目

実装完了後、以下を確認してリファクタリングが正しいことを検証する。

### 機能テスト (手動)

- [ ] `python main.py "https://youtu.be/<テスト動画ID>"` で動画がダウンロードできること
- [ ] `python main.py "https://youtu.be/<テスト動画ID>" --fast` で高速モードが動作すること
- [ ] `python main.py "https://youtu.be/<テスト動画ID>" --hq` で高品質モードが動作すること
- [ ] `python main.py "https://youtu.be/<テスト動画ID>" --audio-only` で音声抽出が動作すること
- [ ] ダウンロード済みファイルが `downloads/` に出力されること
- [ ] 進捗バーとスピナーが正しく表示されること
- [ ] エンコード完了メッセージが表示されること

### 品質改善の確認

- [ ] Normal モードでダウンロードした動画の画質が改善されていること (目視確認)
- [ ] HQ モードのエンコード時間が短縮されていること

### 自動テスト

- [ ] `pytest tests/` が全テストパスすること
- [ ] `pytest --cov=yt_downloader tests/` でカバレッジ 80% 以上であること

### コード品質

- [ ] 各モジュールが 400行以下であること
- [ ] 各関数が 50行以下であること
- [ ] 循環インポートが発生しないこと (`python -c "from yt_downloader.cli import main"` が成功)
- [ ] `python main.py --help` が正しいヘルプを表示すること

---

## 重要な実装上の注意

1. **OUTPUT_DIR のパス解決**: `config.py` が `src/yt_downloader/` に移動するため、`Path(__file__).parent` の意味が変わる。`Path(__file__).resolve().parent.parent.parent / "downloads"` でプロジェクトルートを正しく参照すること。

2. **main.py のエントリポイント**: `sys.path.insert(0, str(Path(__file__).parent / "src"))` を追加し、`pip install` なしでも `python main.py` が動作するようにする。

3. **docstring 変換はコード分割前に**: 1ファイルでの機械的差分にすることで、レビュー負荷を最小化する。

4. **リファクタリングもコード分割前に**: スレッド安全性修正やカプセル化修正は、単一ファイル内の方が差分が追いやすい。
