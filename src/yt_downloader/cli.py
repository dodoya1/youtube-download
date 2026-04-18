"""コマンドライン引数の解析とエントリーポイント。"""

import argparse
import sys

from yt_downloader.config import FORMAT_OPTIONS, QUALITY_OPTIONS
from yt_downloader.downloader import download
from yt_downloader.ui import c, error, warn


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析して返す。

    モードフラグ (``--fast``, ``--hq``) は排他オプショングループで管理し、
    同時指定はエラーとなる。

    Note:
        URL に ``?`` が含まれる場合、zsh がワイルドカードとして解釈するため
        必ずクォートで囲む必要がある。

    Returns:
        解析済みの引数オブジェクト。
    """
    parser = argparse.ArgumentParser(
        prog="yt-downloader",
        description=c(
            "🎬  yt-dlp を使った YouTube 動画ダウンローダー（QuickTime 対応）", "bold"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
モード:
  デフォルト  最高画質DL + h264_videotoolbox（M1ハード）。数分。【推奨】
  --fast      H.264ストリームコピー。数秒。最大1080p。
  --hq        最高画質DL + libx264 medium。数十分。最高品質。

使用例:
  # 標準モード（推奨）
  python main.py "https://youtu.be/xxxxx"

  # 高速モード
  python main.py "https://youtu.be/xxxxx" --fast

  # 最高品質モード（時間がかかっても良い場合）
  python main.py "https://youtu.be/xxxxx" --hq

  # 解像度を指定
  python main.py "https://youtu.be/xxxxx" -q 1080

  # プレイリスト全体をダウンロード
  python main.py "https://www.youtube.com/playlist?list=xxxxx"

  # チャンネル全動画をダウンロード
  python main.py "https://www.youtube.com/@username/videos"

  # チャンネルから最新 10 件のみ
  python main.py "https://www.youtube.com/@username" --limit 10

  # 2025年以降の動画のみ
  python main.py "https://www.youtube.com/@username" --date-after 20250101

  # 音声のみ MP3
  python main.py "https://youtu.be/xxxxx" --audio-only

  # 複数 URL を一度にダウンロード（全 URL に同じオプションが適用される）
  python main.py "https://youtu.be/aaa" "https://youtu.be/bbb" --fast

⚠️  URL は必ずクォートで囲んでください（zsh の ? 展開を防ぐため）
⚠️  brew install node を実行しておくと全フォーマットが取得できます

指定可能な品質: {', '.join(QUALITY_OPTIONS)}
指定可能な形式: {', '.join(FORMAT_OPTIONS)}
""",
    )

    parser.add_argument(
        "url",
        nargs="+",
        help='ダウンロードする YouTube URL（複数指定可、必ずクォートで囲む: "https://..."）',
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
    parser.add_argument(
        "--date-after",
        metavar="DATE",
        help="指定日以降にアップロードされた動画のみ取得 (形式: YYYYMMDD)",
    )
    parser.add_argument(
        "--date-before",
        metavar="DATE",
        help="指定日以前にアップロードされた動画のみ取得 (形式: YYYYMMDD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="チャンネル/プレイリストから最大 N 件だけダウンロード",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="ダウンロード済み動画を記録し、再実行時にスキップする（チャンネルは自動有効）",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--fast",
        action="store_true",
        help="高速モード: H.264ストリームコピー（再エンコードなし・最大1080p相当）",
    )
    mode_group.add_argument(
        "--hq",
        action="store_true",
        help="最高品質モード: libx264 preset medium（低速・高品質）",
    )

    return parser.parse_args()


def main() -> None:
    """エントリーポイント。ヘッダーを表示してダウンロードを開始する。

    複数 URL が指定された場合は 1 件ずつ順番に処理し、途中で失敗した URL が
    あっても残りの URL は続行する。全件処理後、1 件でも失敗があれば終了
    コード 1 を返す。
    """
    print(c("\n══════════════════════════════════════════", "cyan"))
    print(c("  🎬  YouTube Downloader (yt-dlp)         ", "cyan", "bold"))
    print(c("  🍎  QuickTime Player 対応版              ", "cyan"))
    print(c("══════════════════════════════════════════\n", "cyan"))

    args = parse_args()

    if args.fast:
        mode = "fast"
    elif args.hq:
        mode = "hq"
    else:
        mode = "normal"

    urls: list[str] = args.url
    total = len(urls)
    failed_urls: list[str] = []

    for index, url in enumerate(urls, start=1):
        if total > 1:
            print(c(f"\n━━━ [{index}/{total}] {url} ━━━", "cyan", "bold"))
        try:
            download(
                url=url,
                quality=args.quality,
                fmt=args.format,
                audio_only=args.audio_only,
                no_playlist=args.no_playlist,
                mode=mode,
                date_after=args.date_after,
                date_before=args.date_before,
                limit=args.limit,
                use_archive=args.archive,
            )
        except SystemExit as exc:
            # 130: KeyboardInterrupt は全体中断として即時再送出
            if exc.code == 130:
                raise
            failed_urls.append(url)
            if total > 1:
                warn("このURLは失敗しました。次のURLに進みます。")

    if failed_urls:
        if total > 1:
            error(f"\n失敗した URL ({len(failed_urls)}/{total}):")
            for u in failed_urls:
                error(f"  - {u}")
        sys.exit(1)
