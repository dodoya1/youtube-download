#!/usr/bin/env python3
"""
yt_downloader.py - yt-dlp を使った YouTube 動画ダウンローダー。

QuickTime Player（Mac標準）で再生できる H.264 + AAC / MP4 を優先して
ダウンロードし、非対応コーデックの場合は ffmpeg で変換します。

使い方::

    python yt_downloader.py "<URL>" [オプション]

例::

    python yt_downloader.py "https://youtu.be/xxxxx"
    python yt_downloader.py "https://youtu.be/xxxxx" -q 1080 -f mp4
    python yt_downloader.py "https://www.youtube.com/playlist?list=xxxxx"
    python yt_downloader.py "https://youtu.be/xxxxx" --audio-only

.. note::
    URL に ``?`` が含まれる場合は必ずクォートで囲んでください。
    zsh がワイルドカードとして解釈するためです。
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

# ffmpeg で変換する際の映像品質（CRF: 低いほど高品質、18 は視覚的無劣化に近い）
FFMPEG_CRF = "18"

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
    """
    ANSIカラーコードを付与した文字列を返す。

    標準出力が TTY でない場合（パイプやリダイレクト）はカラーコードを付与しない。

    :param text: 色付けしたい文字列
    :type text: str
    :param keys: COLORS に定義されたキー名（複数指定可）
    :type keys: str
    :return: カラーコード付きの文字列（非 TTY では text をそのまま返す）
    :rtype: str
    """
    if not sys.stdout.isatty():
        return text
    prefix = "".join(COLORS[k] for k in keys)
    return f"{prefix}{text}{COLORS['reset']}"


def info(msg: str) -> None:
    """
    INFOレベルのメッセージを標準出力に表示する。

    :param msg: 表示するメッセージ
    :type msg: str
    :return: None
    """
    print(c(f"[INFO]  {msg}", "cyan"))


def ok(msg: str) -> None:
    """
    成功メッセージを標準出力に表示する。

    :param msg: 表示するメッセージ
    :type msg: str
    :return: None
    """
    print(c(f"[OK]    {msg}", "green", "bold"))


def warn(msg: str) -> None:
    """
    WARNINGレベルのメッセージを標準エラー出力に表示する。

    :param msg: 表示するメッセージ
    :type msg: str
    :return: None
    """
    print(c(f"[WARN]  {msg}", "yellow"), file=sys.stderr)


def error(msg: str) -> None:
    """
    ERRORレベルのメッセージを標準エラー出力に表示する。

    :param msg: 表示するメッセージ
    :type msg: str
    :return: None
    """
    print(c(f"[ERROR] {msg}", "red", "bold"), file=sys.stderr)


# ── フォーマット文字列の構築 ──────────────────────────────────────────────────
def build_format_selector(quality: str) -> str:
    """
    yt-dlp のフォーマットセレクタ文字列を組み立てる。

    QuickTime Player との互換性を最優先し、以下の優先順位でストリームを選択する。

    1. H.264映像 (avc1) + AAC音声 (mp4a) ― 再エンコード不要で最高互換
    2. H.264映像 + 任意音声 ― 音声のみ AAC に変換
    3. 任意映像 + AAC音声 ― 映像のみ H.264 に変換
    4. 任意映像 + 任意音声 ― 両方変換（4K など H.264 非提供時のフォールバック）

    :param quality: 解像度指定。``"best"`` または ``"1080"`` のような数字文字列。
    :type quality: str
    :return: yt-dlp の ``format`` オプションに渡すセレクタ文字列
    :rtype: str
    """
    if quality == "best":
        return (
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]"
            "/bestvideo[vcodec^=avc1]+bestaudio"
            "/bestvideo+bestaudio[acodec^=mp4a]"
            "/bestvideo+bestaudio/best"
        )
    h = quality
    return (
        f"bestvideo[vcodec^=avc1][height<={h}]+bestaudio[acodec^=mp4a]"
        f"/bestvideo[vcodec^=avc1][height<={h}]+bestaudio"
        f"/bestvideo[height<={h}]+bestaudio[acodec^=mp4a]"
        f"/bestvideo[height<={h}]+bestaudio"
        f"/best[height<={h}]/bestvideo+bestaudio/best"
    )


# ── ydl オプションの構築 ──────────────────────────────────────────────────────
def build_ydl_opts(
    quality: str,
    fmt: str,
    audio_only: bool,
    no_playlist: bool,
    outtmpl: str,
) -> dict:
    """
    yt-dlp に渡すオプション辞書を構築する。

    音声のみモードの場合は MP3 320kbps で抽出する。
    動画モードの場合は QuickTime 互換コーデック（H.264 + AAC）を優先し、
    非対応コーデックが混入した場合は ffmpeg で H.264 + AAC に変換する。

    :param quality: 解像度指定（``"best"`` または ``"1080"`` 等）
    :type quality: str
    :param fmt: 出力コンテナ形式（``"mp4"``, ``"mkv"``, ``"webm"``）
    :type fmt: str
    :param audio_only: True の場合は音声のみ MP3 で抽出する
    :type audio_only: bool
    :param no_playlist: True の場合はプレイリスト URL でも先頭1件のみ取得する
    :type no_playlist: bool
    :param outtmpl: yt-dlp の出力ファイル名テンプレート
    :type outtmpl: str
    :return: yt-dlp.YoutubeDL に渡すオプション辞書
    :rtype: dict
    """
    common = {
        "outtmpl":        outtmpl,
        "progress_hooks": [make_progress_hook()],
        "noplaylist":     no_playlist,
        "ignoreerrors":   True,
    }

    if audio_only:
        return {
            **common,
            "format": "bestaudio/best",
            "postprocessors": [{
                "key":              "FFmpegExtractAudio",
                "preferredcodec":   "mp3",
                "preferredquality": "320",
            }],
        }

    return {
        **common,
        "format":              build_format_selector(quality),
        "merge_output_format": fmt,
        # H.264 + AAC でない場合に ffmpeg で変換する
        # -c:v libx264   : H.264 エンコード
        # -crf 18        : 視覚的無劣化に近い高品質（0=無劣化 〜 51=最低品質）
        # -preset slow   : エンコード時間をかけて圧縮率を高める
        # -c:a aac       : AAC エンコード（QuickTime 対応）
        # -movflags      : MP4 先頭にメタデータを配置（Web 再生最適化）
        "postprocessor_args": {
            "ffmpeg": [
                "-c:v", "libx264", "-crf", FFMPEG_CRF, "-preset", "slow",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
            ]
        },
        "postprocessors": [{
            "key":            "FFmpegVideoRemuxer",
            "preferedformat": fmt,
        }],
    }


# ── 進捗フック ─────────────────────────────────────────────────────────────────
def make_progress_hook():
    """
    yt-dlp のダウンロード進捗を表示するフック関数を生成して返す。

    フック関数はダウンロード中にプログレスバーを描画し、
    マージ / 変換フェーズでは処理中メッセージを表示する。

    :return: yt-dlp の ``progress_hooks`` に渡すコールバック関数
    :rtype: callable
    """
    last_filename: list[str | None] = [None]

    def hook(d: dict) -> None:
        """
        yt-dlp から呼ばれる進捗コールバック。

        :param d: yt-dlp が渡す進捗情報辞書
        :type d: dict
        :return: None
        """
        status = d.get("status")
        filename = d.get("filename", "")

        if status == "downloading":
            if filename != last_filename[0]:
                last_filename[0] = filename
                print(c(f"\n  ▶ {Path(filename).name}", "bold"))

            percent = d.get("_percent_str",  "  ?%").strip()
            speed = d.get("_speed_str",    "?/s").strip()
            eta = d.get("_eta_str",      "?").strip()
            total = d.get(
                "_total_bytes_str",
                d.get("_total_bytes_estimate_str", "?"),
            ).strip()
            bar_val = d.get("downloaded_bytes", 0)
            bar_total = d.get("total_bytes") or d.get(
                "total_bytes_estimate") or 1
            bar_width = 30
            filled = int(bar_width * bar_val / bar_total)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(
                f"\r  [{bar}] {c(percent,'green')}  {total}"
                f"  {c(speed,'cyan')}  ETA {eta}   ",
                end="",
                flush=True,
            )

        elif status == "finished":
            print()
            info(f"マージ / 変換中: {Path(filename).name}")

        elif status == "error":
            print()
            error("ダウンロードに失敗しました。")

    return hook


# ── ダウンロード本体 ──────────────────────────────────────────────────────────
def download(
    url: str,
    quality: str,
    fmt: str,
    audio_only: bool,
    no_playlist: bool,
) -> None:
    """
    指定した URL の動画（またはプレイリスト）をダウンロードする。

    ダウンロード先は OUTPUT_DIR 定数で指定されたフォルダ。
    フォルダが存在しない場合は自動的に作成する。

    :param url: ダウンロード対象の YouTube URL
    :type url: str
    :param quality: 解像度指定（``"best"`` または ``"1080"`` 等）
    :type quality: str
    :param fmt: 出力コンテナ形式（``"mp4"``, ``"mkv"``, ``"webm"``）
    :type fmt: str
    :param audio_only: True の場合は音声のみ MP3 で抽出する
    :type audio_only: bool
    :param no_playlist: True の場合はプレイリスト URL でも先頭1件のみ取得する
    :type no_playlist: bool
    :return: None
    :raises SystemExit: ダウンロードエラーまたはユーザー中断時
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outtmpl = str(OUTPUT_DIR / "%(title)s.%(ext)s")

    if audio_only:
        info("モード: 音声のみ (MP3 320kbps)")
    else:
        info(f"モード: 動画  品質={c(quality,'bold')}  形式={c(fmt.upper(),'bold')}")
        info("コーデック: H.264 + AAC 優先（QuickTime 互換）")

    info(f"出力先: {OUTPUT_DIR}/")
    print()

    ydl_opts = build_ydl_opts(quality, fmt, audio_only, no_playlist, outtmpl)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            ret = ydl.download([url])
        print()
        if ret == 0:
            ok("ダウンロード完了！  QuickTime Player で再生できます 🎬")
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
def parse_args() -> argparse.Namespace:
    """
    コマンドライン引数を解析して返す。

    .. note::
        URL に ``?`` が含まれる場合、zsh がワイルドカードとして解釈するため
        必ずクォートで囲む必要がある。

    :return: 解析済みの引数オブジェクト
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        prog="yt_downloader",
        description=c(
            "🎬  yt-dlp を使った YouTube 動画ダウンローダー（QuickTime 対応）", "bold"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
使用例:
  # 最高品質で MP4（QuickTime 再生可能）
  python yt_downloader.py "https://youtu.be/xxxxx"

  # 解像度・形式を指定
  python yt_downloader.py "https://youtu.be/xxxxx" -q 1080 -f mp4

  # プレイリスト全体をダウンロード
  python yt_downloader.py "https://www.youtube.com/playlist?list=xxxxx"

  # 音声のみ MP3
  python yt_downloader.py "https://youtu.be/xxxxx" --audio-only

  # プレイリスト URL でも1本だけ
  python yt_downloader.py "https://youtu.be/xxxxx" --no-playlist

⚠️  URL は必ずクォートで囲んでください（zsh の ? 展開を防ぐため）

指定可能な品質: {', '.join(QUALITY_OPTIONS)}
指定可能な形式: {', '.join(FORMAT_OPTIONS)}
""",
    )

    parser.add_argument(
        "url",
        help='ダウンロードする YouTube URL（必ずクォートで囲む: "https://..."）',
    )
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


def main() -> None:
    """
    エントリーポイント。ヘッダーを表示してダウンロードを開始する。

    :return: None
    """
    print(c("\n══════════════════════════════════════════", "cyan"))
    print(c("  🎬  YouTube Downloader (yt-dlp)         ", "cyan", "bold"))
    print(c("  🍎  QuickTime Player 対応版              ", "cyan"))
    print(c("══════════════════════════════════════════\n", "cyan"))

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
