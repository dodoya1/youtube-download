# 🎬 yt-dlp YouTube Downloader

yt-dlp を使った YouTube 動画・音声ダウンローダーです。  
**QuickTime Player（Mac 標準）で再生できる MP4** を出力することを最優先に設計されています。  
M1 Mac のハードウェアエンコーダー（`h264_videotoolbox`）に対応しており、高画質と高速処理を両立します。

---

## ✨ 特徴

- 🍎 **QuickTime Player 完全対応** — H.264 + AAC の MP4 を出力
- ⚡ **3 段階のエンコードモード** — 用途に合わせて速さと画質を選択可能
- 📋 **プレイリスト対応** — YouTube のプレイリスト URL をそのまま指定して一括ダウンロード
- 📺 **チャンネル対応** — チャンネル URL で全動画を一括ダウンロード、中断・再開対応
- 🎵 **音声のみ抽出** — MP3 320kbps で音声のみ保存
- 📊 **リアルタイム進捗表示** — ダウンロード・エンコードの進捗をターミナルに表示
- 🔧 **解像度・形式の柔軟な指定** — 4K〜144p、MP4 / MKV / WebM

---

## 📋 必要条件

| ツール           | 用途                                   | インストール                                       |
| ---------------- | -------------------------------------- | -------------------------------------------------- |
| Python 3.10 以上 | スクリプト実行                         | [python.org](https://www.python.org/)              |
| uv               | 仮想環境・パッケージ管理               | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| ffmpeg           | 映像・音声のマージ／変換               | `brew install ffmpeg`                              |
| Node.js          | YouTube フォーマット一覧の取得（必須） | `brew install node`                                |

> ⚠️ **Node.js を入れないと YouTube の全フォーマットが取得できず、画質が著しく低下します。**  
> 必ず `brew install node` を実行してからご利用ください。

---

## 🚀 インストール

```bash
# 1. リポジトリをクローン（またはファイルを配置）
git clone https://github.com/yourname/yt-downloader.git
cd yt-downloader

# 2. 依存ツールをインストール（初回のみ）
brew install ffmpeg node

# 3. uv で仮想環境を作成
uv venv

# 4. 仮想環境を有効化
source .venv/bin/activate

# 5. yt-dlp をインストール
uv pip install yt-dlp
```

---

## 📖 使い方

### 基本（推奨・標準モード）

```bash
python main.py "https://youtu.be/xxxxx"
```

M1 ハードウェアエンコード（`h264_videotoolbox`）で最高画質の動画をダウンロードします。

### 解像度を指定する

```bash
python main.py "https://youtu.be/xxxxx" -q 1080
```

### 高速モード（マージが数秒・最大 1080p 相当）

```bash
python main.py "https://youtu.be/xxxxx" --fast
```

### 最高品質モード（libx264・低速）

```bash
python main.py "https://youtu.be/xxxxx" --hq
```

### プレイリスト全体をダウンロード

```bash
python main.py "https://www.youtube.com/playlist?list=xxxxx"
```

### チャンネル全動画をダウンロード

```bash
python main.py "https://www.youtube.com/@username/videos"
```

チャンネル URL を指定すると `downloads/<チャンネル名>/` にサブディレクトリを作成して保存します。  
ダウンロード済み動画は自動で記録され、再実行時にスキップされます。

### チャンネルから最新 N 件のみ

```bash
python main.py "https://www.youtube.com/@username" --limit 10
```

### 日付で絞り込む

```bash
# 2025年以降の動画のみ
python main.py "https://www.youtube.com/@username" --date-after 20250101

# 2024年中の動画のみ
python main.py "https://www.youtube.com/@username" --date-after 20240101 --date-before 20241231
```

### プレイリスト URL でも 1 本だけダウンロード

```bash
python main.py "https://youtu.be/xxxxx" --no-playlist
```

### 音声のみ MP3 で保存

```bash
python main.py "https://youtu.be/xxxxx" --audio-only
```

### 出力形式を変更する

```bash
python main.py "https://youtu.be/xxxxx" -f mkv
```

---

## ⚙️ オプション一覧

| オプション      | 短縮形 | デフォルト | 説明                                                                                      |
| --------------- | ------ | ---------- | ----------------------------------------------------------------------------------------- |
| `--quality`     | `-q`   | `best`     | 解像度を指定（`best` / `2160` / `1440` / `1080` / `720` / `480` / `360` / `240` / `144`） |
| `--format`      | `-f`   | `mp4`      | 出力形式を指定（`mp4` / `mkv` / `webm`）                                                  |
| `--fast`        | —      | `false`    | 高速モード（H.264 ストリームコピー）                                                      |
| `--hq`          | —      | `false`    | 最高品質モード（libx264 preset slow）                                                     |
| `--audio-only`  | —      | `false`    | 音声のみ MP3 320kbps で抽出                                                               |
| `--no-playlist` | —      | `false`    | プレイリスト URL でも先頭 1 件のみ取得                                                    |
| `--date-after`  | —      | —          | 指定日以降の動画のみ取得（形式: `YYYYMMDD`）                                              |
| `--date-before` | —      | —          | 指定日以前の動画のみ取得（形式: `YYYYMMDD`）                                              |
| `--limit`       | —      | —          | チャンネル/プレイリストから最大 N 件だけダウンロード                                       |
| `--archive`     | —      | `false`    | ダウンロード済み動画を記録し再実行時にスキップ（チャンネルは自動有効）                    |

> `--fast` と `--hq` は同時に指定できません。

---

## 🎛️ エンコードモード比較

| モード           | コマンド | エンコーダー          | 処理時間の目安 | 最大画質   | QuickTime |
| ---------------- | -------- | --------------------- | -------------- | ---------- | --------- |
| 高速             | `--fast` | ストリームコピー      | 数秒           | 1080p 相当 | ✅        |
| **標準（推奨）** | _(なし)_ | **h264_videotoolbox** | **数分**       | **4K**     | **✅**    |
| 最高品質         | `--hq`   | libx264 slow          | 数十分         | 4K         | ✅        |

> 処理時間は動画の長さ・解像度・マシン性能により異なります。  
> M1 Mac 8GB の場合、3 時間の 4K 動画で標準モードは 5〜15 分程度が目安です。

---

## 📁 ディレクトリ構成

```
yt-downloader/
├── main.py              # メインスクリプト
├── README.md            # このファイル
├── .venv/               # uv が作成する仮想環境（Git 管理外）
└── downloads/           # ダウンロードした動画の保存先（自動作成）
    ├── video_title.mp4  #   単一動画・プレイリストの出力先
    ├── username/        #   チャンネル名のサブディレクトリ
    │   ├── video1.mp4
    │   └── video2.mp4
    └── .archive/        #   ダウンロード済み記録（自動作成）
        └── username.txt
```

---

## ⚠️ 注意事項

### URL のクォートについて

zsh は URL に含まれる `?` をワイルドカードとして解釈します。  
**URL は必ず引用符で囲んでください。**

```bash
# ❌ 失敗する
python main.py https://youtu.be/xxxxx?si=xxxxxxxx

# ✅ 正しい
python main.py "https://youtu.be/xxxxx?si=xxxxxxxx"
```

### 毎回の起動手順

```bash
cd yt-downloader
source .venv/bin/activate      # 仮想環境を有効化
python main.py "URL"           # ダウンロード実行
deactivate                     # 作業終了後に無効化
```

### yt-dlp のアップデート

YouTube の仕様変更に伴い、yt-dlp は頻繁にアップデートされます。  
ダウンロードできなくなった場合は以下を実行してください。

```bash
uv pip install --upgrade yt-dlp
```

### チャンネルダウンロードについて

チャンネルには数百本の動画がある場合があります。  
初回は `--limit` で少数テストしてから全動画をダウンロードすることを推奨します。

```bash
# まず 2 件でテスト
python main.py "https://www.youtube.com/@username" --limit 2 --fast

# 問題なければ全動画をダウンロード
python main.py "https://www.youtube.com/@username"
```

中断した場合でも、再実行すればダウンロード済み動画は自動でスキップされます。

### 著作権について

このツールは個人的な利用を目的としています。  
ダウンロードしたコンテンツの著作権は各コンテンツ所有者に帰属します。  
YouTube の利用規約を遵守した上でご使用ください。

---

## 🛠️ トラブルシューティング

| 症状                        | 原因                              | 対処法                                  |
| --------------------------- | --------------------------------- | --------------------------------------- |
| `zsh: no matches found`     | URL の `?` が展開された           | URL をクォートで囲む                    |
| 画質が低い（1080p 止まり）  | Node.js 未インストール            | `brew install node`                     |
| `ffmpeg: command not found` | ffmpeg 未インストール             | `brew install ffmpeg`                   |
| Merger が終わらない         | `--hq` モードで長時間動画を変換中 | 標準モード（オプションなし）を使用      |
| QuickTime で再生できない    | VP9/AV1 コーデックが含まれている  | `--hq` または標準モードで再ダウンロード |

---

## 📄 ライセンス

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
