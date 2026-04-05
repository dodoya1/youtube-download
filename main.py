#!/usr/bin/env python3
"""
yt_downloader.py - yt-dlp を使った YouTube 動画ダウンローダー

使い方:
  python yt_downloader.py <URL> [オプション]

例:
  python yt_downloader.py https://www.youtube.com/watch?v=xxxxx
  python yt_downloader.py https://www.youtube.com/watch?v=xxxxx -q 1080 -f mp4
  python yt_downloader.py https://www.youtube.com/playlist?list=xxxxx -q best
  python yt_downloader.py https://www.youtube.com/watch?v=xxxxx --audio-only
"""

import argparse
import sys
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadError

# ── 定数 ──────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent / "downloads"

QUALITY_OPTIONS = ["best", "2160", "1440",
                   "1080", "720", "480", "360", "240", "144"]
FORMAT_OPTIONS = ["mp4", "mkv", "webm"]

COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}


# ── ユーティリティ ────────────────────────────────────────────────────────────
def c(text: str, *keys: str) -> str:
    """カラー付きテキストを返す（TTY 以外では無効化）"""
    if not sys.stdout.isatty():
        return text
    prefix = "".join(COLORS[k] for k in keys)
    return f"{prefix}{text}{COLORS['reset']}"


def info(msg): print(c(f"[INFO]  {msg}", "cyan"))
def ok(msg): print(c(f"[OK]    {msg}", "green", "bold"))
def warn(msg): print(c(f"[WARN]  {msg}", "yellow"), file=sys.stderr)
def error(msg): print(c(f"[ERROR] {msg}", "red", "bold"), file=sys.stderr)


# ── フォーマット文字列の構築 ──────────────────────────────────────────────────
def build_format_selector(quality: str) -> str:
    """
    yt-dlp の -f フォーマットセレクタを組み立てる。
    'best' なら利用可能な最高品質、数字なら指定解像度以下で最高品質。
    映像と音声を別ストリームで取得して ffmpeg でマージする。
    """
    if quality == "best":
        # bestvideo+bestaudio → 最高品質の映像と音声をマージ
        return "bestvideo+bestaudio/best"
    else:
        h = quality  # e.g. "1080"
        # 指定解像度以下で最高品質、フォールバックあり
        return (
            f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/bestvideo+bestaudio/best"
        )


# ── 進捗フック ─────────────────────────────────────────────────────────────────
def make_progress_hook():
    """ダウンロード進捗を表示するフック関数を返す"""
    last_filename = [None]

    def hook(d):
        status = d.get("status")
        filename = d.get("filename", "")

        if status == "downloading":
            # ファイル名が変わったときだけ表示
            if filename != last_filename[0]:
                last_filename[0] = filename
                short = Path(filename).name
                print(c(f"\n  ▶ {short}", "bold"))

            percent = d.get("_percent_str",  "  ?%").strip()
            speed = d.get("_speed_str",    "?/s").strip()
            eta = d.get("_eta_str",      "?").strip()
            total = d.get("_total_bytes_str", d.get(
                "_total_bytes_estimate_str", "?")).strip()
            bar_val = d.get("downloaded_bytes", 0)
            bar_total = d.get("total_bytes") or d.get(
                "total_bytes_estimate") or 1
            bar_width = 30
            filled = int(bar_width * bar_val / bar_total)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(
                f"\r  [{bar}] {c(percent,'green')}  {total}  {c(speed,'cyan')}  ETA {eta}   ",
                end="",
                flush=True,
            )

        elif status == "finished":
            print()  # 改行
            info(f"マージ / 変換中: {Path(filename).name}")

        elif status == "error":
            print()
            error("ダウンロードに失敗しました。")

    return hook


# ── ダウンロード本体 ──────────────────────────────────────────────────────────
def download(url: str, quality: str, fmt: str, audio_only: bool, no_playlist: bool):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 出力テンプレート: downloads/タイトル.拡張子
    outtmpl = str(OUTPUT_DIR / "%(title)s.%(ext)s")

    # ──── オーディオのみモード ────
    if audio_only:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
            "progress_hooks": [make_progress_hook()],
            "noplaylist": no_playlist,
            "ignoreerrors": True,
        }
        info("モード: 音声のみ (MP3 320kbps)")

    # ──── 動画モード ────
    else:
        ydl_opts = {
            "format": build_format_selector(quality),
            "outtmpl": outtmpl,
            "merge_output_format": fmt,
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": fmt,
            }],
            "progress_hooks": [make_progress_hook()],
            "noplaylist": no_playlist,
            "ignoreerrors": True,
        }
        info(f"モード: 動画  品質={c(quality,'bold')}  形式={c(fmt.upper(),'bold')}")

    info(f"出力先: {OUTPUT_DIR}/")
    print()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            ret = ydl.download([url])
        if ret == 0:
            print()
            ok("ダウンロード完了！")
        else:
            warn("一部の動画でエラーが発生しましたが、処理を続行しました。")
    except DownloadError as e:
        error(f"ダウンロードエラー: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        warn("ユーザーによって中断されました。")
        sys.exit(130)


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        prog="yt_downloader",
        description=c("🎬  yt-dlp を使った YouTube 動画ダウンローダー", "bold"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
使用例:
  # 最高品質で MP4 ダウンロード（デフォルト）
  python yt_downloader.py https://youtu.be/xxxxx

  # 解像度・形式を指定
  python yt_downloader.py https://youtu.be/xxxxx -q 1080 -f mkv

  # プレイリスト全体をダウンロード
  python yt_downloader.py https://www.youtube.com/playlist?list=xxxxx

  # 音声のみ (MP3)
  python yt_downloader.py https://youtu.be/xxxxx --audio-only

  # プレイリスト URL でも最初の1本だけ
  python yt_downloader.py https://youtu.be/xxxxx --no-playlist

指定可能な品質: {', '.join(QUALITY_OPTIONS)}
指定可能な形式: {', '.join(FORMAT_OPTIONS)}
""",
    )

    parser.add_argument("url", help="ダウンロードする YouTube の URL（動画 / プレイリスト）")

    parser.add_argument(
        "-q", "--quality",
        default="best",
        choices=QUALITY_OPTIONS,
        metavar="QUALITY",
        help=f"解像度を指定 ({'/'.join(QUALITY_OPTIONS)})  デフォルト: best",
    )
    parser.add_argument(
        "-f", "--format",
        default="mp4",
        choices=FORMAT_OPTIONS,
        metavar="FORMAT",
        help=f"出力形式を指定 ({'/'.join(FORMAT_OPTIONS)})  デフォルト: mp4",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="音声のみ MP3 形式でダウンロードする",
    )
    parser.add_argument(
        "--no-playlist",
        action="store_true",
        help="プレイリスト URL でも最初の1本だけダウンロードする",
    )

    return parser.parse_args()


def main():
    print(c("\n══════════════════════════════════════", "cyan"))
    print(c("  🎬  YouTube Downloader (yt-dlp)     ", "cyan", "bold"))
    print(c("══════════════════════════════════════\n", "cyan"))

    args = parse_args()
    download(
        url=args.url,
        quality=args.quality,
        fmt=args.format,
        audio_only=args.audio_only,
        no_playlist=args.no_playlist,
    )


if __name__ == "__main__":
    main()
