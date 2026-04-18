"""ダウンロードのコア: フォーマットセレクタ、yt-dlp オプション、オーケストレーター。"""

import re
import sys
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DateRange, DownloadError

from yt_downloader.config import (
    ARCHIVE_DIR,
    ENCODER_PRESETS,
    OUTPUT_DIR,
)
from yt_downloader.encoding import EncodingSpinner
from yt_downloader.hooks import make_postprocessor_hook, make_progress_hook
from yt_downloader.logger import YtDlpLogger
from yt_downloader.tracker import DownloadTracker
from yt_downloader.ui import c, error, info, ok, warn
from yt_downloader.url import detect_url_type, extract_channel_name


def build_format_selector(quality: str, mode: str = "normal") -> str:
    """yt-dlp のフォーマットセレクタ文字列を組み立てる。

    モードによって選択するコーデックと解像度の戦略が異なる。

    - ``"fast"``   : H.264 + AAC を優先 (ストリームコピー可、最大 1080p)
    - ``"normal"`` : コーデック制限なし・最高品質 (VP9/AV1 含む、ハードウェアエンコード)
    - ``"hq"``     : ``"normal"`` と同じセレクタ (libx264 ソフトウェアエンコード)

    Args:
        quality: 解像度指定。``"best"`` または ``"1080"`` のような数字文字列。
        mode: ダウンロードモード (``"fast"`` / ``"normal"`` / ``"hq"``)。

    Returns:
        yt-dlp の ``format`` オプションに渡すセレクタ文字列。
    """
    if mode == "fast":
        # H.264 + AAC を優先：ストリームコピーで数秒マージ
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

    # normal / hq: コーデック制限なし・最高品質
    if quality == "best":
        return "bestvideo+bestaudio/best"
    h = quality
    return (
        f"bestvideo[height<={h}]+bestaudio"
        f"/best[height<={h}]/bestvideo+bestaudio/best"
    )


def build_ydl_opts(
    quality: str,
    fmt: str,
    audio_only: bool,
    no_playlist: bool,
    outtmpl: str,
    mode: str,
    spinner: EncodingSpinner,
    archive_path: str | None = None,
    date_range: DateRange | None = None,
    playlist_items: str | None = None,
) -> dict:
    """yt-dlp に渡すオプション辞書を構築する。

    モードに応じて ffmpeg のエンコード戦略を切り替える。

    - ``"fast"``   : ストリームコピー (``-c copy``)。再エンコードなし・数秒。
    - ``"normal"`` : ``h264_videotoolbox`` (Apple M1 ハードウェアエンコード)。数分。
    - ``"hq"``     : ``libx264 -preset medium`` (ソフトウェア最高品質)。数十分。

    Args:
        quality: 解像度指定 (``"best"`` または ``"1080"`` 等)。
        fmt: 出力コンテナ形式 (``"mp4"`` / ``"mkv"`` / ``"webm"``)。
        audio_only: True の場合は音声のみ MP3 で抽出する。
        no_playlist: True の場合はプレイリスト URL でも先頭1件のみ取得する。
        outtmpl: yt-dlp の出力ファイル名テンプレート。
        mode: ダウンロードモード (``"fast"`` / ``"normal"`` / ``"hq"``)。
        spinner: エンコード進捗表示用スピナー。
        archive_path: ダウンロード済み動画IDを記録するファイルパス (省略可)。
        date_range: アップロード日のフィルタ範囲 (省略可)。
        playlist_items: ダウンロードする動画のインデックス範囲 (例: ``"1:10"``)。

    Returns:
        yt-dlp.YoutubeDL に渡すオプション辞書。
    """
    yt_logger = YtDlpLogger(spinner.tracker)
    common: dict = {
        "outtmpl":             outtmpl,
        "progress_hooks":      [make_progress_hook(spinner.tracker)],
        "postprocessor_hooks": [make_postprocessor_hook(spinner)],
        "logger":              yt_logger,
        "noplaylist":          no_playlist,
        "ignoreerrors":        True,
        "socket_timeout":      30,
        "retries":             10,
        "fragment_retries":    10,
    }
    if archive_path is not None:
        common = {**common, "download_archive": archive_path, "break_on_existing": True}
    if date_range is not None:
        common = {**common, "daterange": date_range}
    if playlist_items is not None:
        common = {**common, "playlist_items": playlist_items}

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

    opts: dict = {
        **common,
        "format":              build_format_selector(quality, mode),
        "merge_output_format": fmt,
        "postprocessors": [{
            "key":            "FFmpegVideoRemuxer",
            "preferedformat": fmt,
        }],
        "postprocessor_args": {"ffmpeg": list(ENCODER_PRESETS[mode])},
    }

    return opts


def _resolve_output_paths(
    url_type: str,
    url: str,
    use_archive: bool,
) -> tuple[Path, str | None, str | None]:
    """URL 種別に応じて出力ディレクトリとアーカイブパスを決定する。

    Args:
        url_type: URL 種別 (``"channel"`` / ``"playlist"`` / ``"video"``)。
        url: 入力 URL。
        use_archive: プレイリストでもアーカイブを使うかのフラグ。

    Returns:
        ``(出力ディレクトリ, アーカイブパス, チャンネル名)`` のタプル。
        アーカイブを使わない場合はアーカイブパスは ``None``。
        チャンネル URL 以外ではチャンネル名は ``None``。
    """
    if url_type == "channel":
        channel_name = extract_channel_name(url)
        out_dir = OUTPUT_DIR / channel_name
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path: str | None = str(ARCHIVE_DIR / f"{channel_name}.txt")
        return out_dir, archive_path, channel_name

    if url_type == "playlist" and use_archive:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        return OUTPUT_DIR, str(ARCHIVE_DIR / "playlists.txt"), None

    return OUTPUT_DIR, None, None


def _build_date_range(
    date_after: str | None,
    date_before: str | None,
) -> DateRange | None:
    """アップロード日フィルタの DateRange を構築する。

    Args:
        date_after: 指定日以降を表す ``YYYYMMDD`` 文字列 (省略可)。
        date_before: 指定日以前を表す ``YYYYMMDD`` 文字列 (省略可)。

    Returns:
        構築された DateRange。両方が省略されていれば ``None``。

    Raises:
        SystemExit: 日付文字列の形式が ``YYYYMMDD`` でない場合。
    """
    for date_str, date_label in (
        (date_after, "--date-after"),
        (date_before, "--date-before"),
    ):
        if date_str is not None and not re.fullmatch(r"\d{8}", date_str):
            error(f"{date_label} の形式が不正です（YYYYMMDD で指定してください）: {date_str}")
            sys.exit(1)

    if date_after is None and date_before is None:
        return None
    # yt-dlp の DateRange はランタイムでは YYYYMMDD 文字列を受け取る仕様だが、
    # 型推論上は date | None と解釈されるため、ここで型チェックを抑止する。
    return DateRange(start=date_after, end=date_before)  # type: ignore[arg-type]


def _print_download_config(
    *,
    url_type: str,
    channel_name: str | None,
    audio_only: bool,
    mode: str,
    quality: str,
    fmt: str,
    archive_path: str | None,
    date_after: str | None,
    date_before: str | None,
    limit: int | None,
    out_dir: Path,
) -> None:
    """ダウンロード設定情報をターミナルに表示する。

    Args:
        url_type: URL 種別。
        channel_name: チャンネル URL から抽出したチャンネル名 (省略可)。
        audio_only: 音声のみ抽出フラグ。
        mode: ダウンロードモード。
        quality: 解像度指定。
        fmt: 出力コンテナ形式。
        archive_path: アーカイブファイルパス (省略可)。
        date_after: 日付フィルタ (以降)。
        date_before: 日付フィルタ (以前)。
        limit: 最大件数 (省略可)。
        out_dir: 出力先ディレクトリ。
    """
    if url_type == "channel" and channel_name is not None:
        info(f"チャンネル検出: {c(channel_name, 'bold')}")

    mode_labels = {
        "fast":   (c("高速", "green"),   c("ストリームコピー（再エンコードなし・最大 1080p）", "green")),
        "normal": (c("標準（推奨）", "yellow"), c("h264_videotoolbox ハードウェアエンコード（M1 最適化）", "yellow")),
        "hq":     (c("最高品質", "red"),  c("libx264 ソフトウェアエンコード（低速・高品質）", "red")),
    }

    if audio_only:
        info("モード: 音声のみ (MP3 320kbps)")
    else:
        mode_label, desc = mode_labels[mode]
        info(f"モード: {mode_label}  品質={c(quality,'bold')}  形式={c(fmt.upper(),'bold')}")
        info(f"エンコード: {desc}")

    if archive_path is not None:
        info(f"アーカイブ: {c(archive_path, 'bold')}  (ダウンロード済み動画はスキップ)")
    if date_after is not None:
        info(f"日付フィルタ: {c(date_after, 'bold')} 以降")
    if date_before is not None:
        info(f"日付フィルタ: {c(date_before, 'bold')} 以前")
    if limit is not None:
        info(f"ダウンロード上限: {c(str(limit), 'bold')} 件")

    info(f"出力先: {out_dir}/")
    print()


def download(
    url: str,
    quality: str,
    fmt: str,
    audio_only: bool,
    no_playlist: bool,
    mode: str,
    date_after: str | None = None,
    date_before: str | None = None,
    limit: int | None = None,
    use_archive: bool = False,
) -> None:
    """指定した URL の動画（またはプレイリスト、チャンネル）をダウンロードする。

    チャンネル URL の場合はサブディレクトリに出力し、ダウンロードアーカイブを
    自動的に有効にして再実行時にダウンロード済み動画をスキップする。

    Args:
        url: ダウンロード対象の YouTube URL。
        quality: 解像度指定（``"best"`` または ``"1080"`` 等）。
        fmt: 出力コンテナ形式（``"mp4"``, ``"mkv"``, ``"webm"``）。
        audio_only: True の場合は音声のみ MP3 で抽出する。
        no_playlist: True の場合はプレイリスト URL でも先頭1件のみ取得する。
        mode: ダウンロードモード（``"fast"``, ``"normal"``, ``"hq"``）。
        date_after: 指定日以降の動画のみ取得（``YYYYMMDD`` 形式）。
        date_before: 指定日以前の動画のみ取得（``YYYYMMDD`` 形式）。
        limit: ダウンロードする最大件数。
        use_archive: プレイリストでもダウンロード済みスキップを有効にする。

    Raises:
        SystemExit: ダウンロードエラーまたはユーザー中断時。
    """
    url_type = detect_url_type(url)

    # チャンネル URL では --no-playlist は無意味（yt-dlp 内部でプレイリスト扱い）
    if url_type == "channel" and no_playlist:
        warn("チャンネル URL では --no-playlist は無視されます")
        no_playlist = False

    out_dir, archive_path, channel_name = _resolve_output_paths(
        url_type, url, use_archive,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    # 同名タイトルの動画が衝突しないよう動画IDを付加する
    outtmpl = str(out_dir / "%(title)s [%(id)s].%(ext)s")

    date_range_obj = _build_date_range(date_after, date_before)
    playlist_items = f"1:{limit}" if limit is not None else None

    _print_download_config(
        url_type=url_type,
        channel_name=channel_name,
        audio_only=audio_only,
        mode=mode,
        quality=quality,
        fmt=fmt,
        archive_path=archive_path,
        date_after=date_after,
        date_before=date_before,
        limit=limit,
        out_dir=out_dir,
    )

    tracker = DownloadTracker()
    spinner = EncodingSpinner(tracker=tracker)
    ydl_opts = build_ydl_opts(
        quality, fmt, audio_only, no_playlist, outtmpl, mode, spinner,
        archive_path=archive_path,
        date_range=date_range_obj,
        playlist_items=playlist_items,
    )

    try:
        # ydl_opts はモード・URL 種別で動的に組み立てるため、yt-dlp の
        # _Params TypedDict に narrow できない。型チェックのみ抑止する。
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
            _ = ydl.download([url])
        # 結果サマリーを表示（プレイリストの場合は特に有用）
        tracker.print_summary()
        if not tracker.failed:
            ok("ダウンロード完了！  QuickTime Player で再生できます 🎬")
        elif tracker.succeeded:
            warn("一部の動画でエラーが発生しましたが、処理を続行しました。")
        else:
            error("すべての動画のダウンロードに失敗しました。")
    except DownloadError as e:
        error(f"ダウンロードエラー: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        spinner.force_stop()  # スピナーが動いていれば停止
        warn("ユーザーによって中断されました。")
        tracker.print_summary()
        sys.exit(130)
