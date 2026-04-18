[日本語](README.md) | **English**

# 🎬 yt-dlp YouTube Downloader

A YouTube video/audio downloader built on top of yt-dlp.
Designed with a top priority on producing **MP4 files that play natively in QuickTime Player (macOS default)**.
It supports the M1 Mac hardware encoder (`h264_videotoolbox`) to achieve both high quality and fast processing.

---

## ✨ Features

- 🍎 **Full QuickTime Player compatibility** — outputs H.264 + AAC MP4
- ⚡ **3 encoding modes** — pick the right trade-off between speed and quality
- 📋 **Playlist support** — pass a YouTube playlist URL to download everything at once
- 📺 **Channel support** — download every video on a channel URL, with resume on interruption
- 🔗 **Multiple URLs** — mix videos, playlists, and channels in a single command
- 🎵 **Audio-only extraction** — save just the audio as MP3 320kbps
- 📊 **Real-time progress display** — download and encode progress printed to the terminal
- 🔧 **Flexible resolution & format** — 4K to 144p, MP4 / MKV / WebM

---

## 📋 Requirements

| Tool         | Purpose                                 | Install                                            |
| ------------ | --------------------------------------- | -------------------------------------------------- |
| Python 3.10+ | Runs the script                         | [python.org](https://www.python.org/)              |
| uv           | Virtual env & package management        | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| ffmpeg       | Video/audio merge & conversion          | `brew install ffmpeg`                              |
| Node.js      | Fetching YouTube format list (required) | `brew install node`                                |

> ⚠️ **Without Node.js, yt-dlp cannot retrieve all available formats and video quality drops significantly.**
> Make sure to run `brew install node` before using this tool.

---

## 🚀 Installation

```bash
# 1. Clone the repository (or place the files manually)
git clone https://github.com/yourname/yt-downloader.git
cd yt-downloader

# 2. Install dependencies (first time only)
brew install ffmpeg node

# 3. Create a virtual environment with uv
uv venv

# 4. Activate the virtual environment
source .venv/bin/activate

# 5. Install yt-dlp
uv pip install yt-dlp
```

---

## 📖 Usage

### Basic (recommended — standard mode)

```bash
python main.py "https://youtu.be/xxxxx"
```

Downloads the video at the highest quality using M1 hardware encoding (`h264_videotoolbox`).

### Specify a resolution

```bash
python main.py "https://youtu.be/xxxxx" -q 1080
```

### Fast mode (merge in seconds — up to ~1080p)

```bash
python main.py "https://youtu.be/xxxxx" --fast
```

### Maximum quality mode (libx264, slow)

```bash
python main.py "https://youtu.be/xxxxx" --hq
```

### Download an entire playlist

```bash
python main.py "https://www.youtube.com/playlist?list=xxxxx"
```

### Download every video on a channel

```bash
python main.py "https://www.youtube.com/@username/videos"
```

When you pass a channel URL, videos are saved under `downloads/<channel_name>/`.
Already-downloaded videos are automatically recorded and skipped on re-run.

### Only the latest N videos from a channel

```bash
python main.py "https://www.youtube.com/@username" --limit 10
```

### Filter by date

```bash
# Only videos uploaded in 2025 or later
python main.py "https://www.youtube.com/@username" --date-after 20250101

# Only videos uploaded during 2024
python main.py "https://www.youtube.com/@username" --date-after 20240101 --date-before 20241231
```

### Download just a single video even from a playlist URL

```bash
python main.py "https://youtu.be/xxxxx" --no-playlist
```

### Save audio only as MP3

```bash
python main.py "https://youtu.be/xxxxx" --audio-only
```

### Change the output format

```bash
python main.py "https://youtu.be/xxxxx" -f mkv
```

### Download multiple URLs at once

```bash
python main.py "https://youtu.be/aaa" "https://youtu.be/bbb" "https://youtu.be/ccc"
```

- Pass multiple URLs separated by spaces. **The same options apply to every URL** (`-q`, `--fast`, `--hq`, `--audio-only`, `--date-after`, `--limit`, etc.).
- You can **mix video / playlist / channel URLs**. Each URL's type is detected independently (channels go under `downloads/<channel_name>/`, everything else goes directly under `downloads/`).
- If one URL fails, **the remaining URLs continue processing**. After all URLs are done, the process exits with code `1` if any failures occurred, along with a list of the failed URLs.
- `Ctrl+C` aborts the whole run immediately (exit code `130`).

```bash
# Batch-download multiple videos in fast mode
python main.py "https://youtu.be/aaa" "https://youtu.be/bbb" --fast

# Mix a playlist and a channel in one command
python main.py "https://www.youtube.com/playlist?list=xxx" "https://www.youtube.com/@user"
```

---

## ⚙️ Options

| Option          | Short | Default | Description                                                                            |
| --------------- | ----- | ------- | -------------------------------------------------------------------------------------- |
| `--quality`     | `-q`  | `best`  | Resolution (`best` / `2160` / `1440` / `1080` / `720` / `480` / `360` / `240` / `144`) |
| `--format`      | `-f`  | `mp4`   | Output format (`mp4` / `mkv` / `webm`)                                                 |
| `--fast`        | —     | `false` | Fast mode (H.264 stream copy)                                                          |
| `--hq`          | —     | `false` | Maximum quality mode (libx264 preset medium)                                           |
| `--audio-only`  | —     | `false` | Extract audio only as MP3 320kbps                                                      |
| `--no-playlist` | —     | `false` | Download only the first entry, even from a playlist URL                                |
| `--date-after`  | —     | —       | Only videos uploaded on/after this date (format: `YYYYMMDD`)                           |
| `--date-before` | —     | —       | Only videos uploaded on/before this date (format: `YYYYMMDD`)                          |
| `--limit`       | —     | —       | Download at most N videos from a channel/playlist                                      |
| `--archive`     | —     | `false` | Record downloaded videos and skip them on re-run (enabled automatically for channels)  |

> `--fast` and `--hq` cannot be used together.

---

## 🎛️ Encoding mode comparison

| Mode                       | Command  | Encoder               | Typical time | Max quality | QuickTime |
| -------------------------- | -------- | --------------------- | ------------ | ----------- | --------- |
| Fast                       | `--fast` | Stream copy           | Seconds      | ~1080p      | ✅        |
| **Standard (recommended)** | _(none)_ | **h264_videotoolbox** | **Minutes**  | **4K**      | **✅**    |
| Max quality                | `--hq`   | libx264 medium        | Tens of min. | 4K          | ✅        |

> Actual time depends on video length, resolution, and hardware.
> On an M1 Mac with 8GB RAM, a 3-hour 4K video typically takes 5–15 minutes in standard mode.

---

## 📁 Directory layout

```
yt-downloader/
├── main.py                  # Entry point (thin wrapper)
├── src/
│   └── yt_downloader/       # Package body
│       ├── cli.py           # CLI argument parsing and entry point
│       ├── config.py        # Constants and encoder presets
│       ├── downloader.py    # Download orchestration
│       ├── encoding.py      # EncodingSpinner
│       ├── hooks.py         # yt-dlp hook functions
│       ├── logger.py        # YtDlpLogger
│       ├── tracker.py       # DownloadTracker
│       ├── ui.py            # Terminal output helpers
│       └── url.py           # URL type detection
├── tests/                   # pytest unit tests
├── pyproject.toml           # Package configuration
├── README.md                # Japanese README
├── README-en.md             # This file (English)
├── .venv/                   # Virtual env created by uv (gitignored)
└── downloads/               # Output directory (auto-created)
    ├── video_title [id].mp4 #   Output for single videos / playlists
    ├── username/            #   Per-channel subdirectory
    │   ├── video1 [id].mp4
    │   └── video2 [id].mp4
    └── .archive/            #   Download archive (auto-created)
        └── username.txt
```

---

## ⚠️ Notes

### Quoting URLs

zsh expands `?` in a URL as a glob.
**Always wrap URLs in quotes.**

```bash
# ❌ Fails
python main.py https://youtu.be/xxxxx?si=xxxxxxxx

# ✅ Correct
python main.py "https://youtu.be/xxxxx?si=xxxxxxxx"
```

### Startup procedure each time

```bash
cd yt-downloader
source .venv/bin/activate      # Activate the virtual environment
python main.py "URL"           # Run the download
deactivate                     # Deactivate when you're done
```

### Updating yt-dlp

YouTube changes frequently, and yt-dlp is updated often to keep up.
If downloads stop working, try the following:

```bash
uv pip install --upgrade yt-dlp
```

### About channel downloads

A channel may contain hundreds of videos.
For the first run, we recommend testing with `--limit` before downloading everything.

```bash
# Try 2 videos first
python main.py "https://www.youtube.com/@username" --limit 2 --fast

# Then download everything once you're confident
python main.py "https://www.youtube.com/@username"
```

Even if the process is interrupted, re-running it will automatically skip already-downloaded videos.

### Copyright

This tool is intended for personal use.
Copyright in downloaded content belongs to each respective rights holder.
Please use this tool in compliance with YouTube's Terms of Service.

---

## 🛠️ Troubleshooting

| Symptom                     | Cause                                      | Fix                                      |
| --------------------------- | ------------------------------------------ | ---------------------------------------- |
| `zsh: no matches found`     | `?` in the URL was expanded                | Wrap the URL in quotes                   |
| Quality capped at 1080p     | Node.js is not installed                   | `brew install node`                      |
| `ffmpeg: command not found` | ffmpeg is not installed                    | `brew install ffmpeg`                    |
| Merger never finishes       | Long video being re-encoded in `--hq` mode | Use standard mode (no option)            |
| Won't play in QuickTime     | Output contains VP9/AV1 codec              | Re-download with `--hq` or standard mode |

---

## 📄 License

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
