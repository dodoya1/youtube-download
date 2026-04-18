#!/usr/bin/env python3
"""main.py - yt-dlp を使った YouTube 動画ダウンローダー。

事前準備 (初回のみ):

    brew install node      # JS ランタイム（全フォーマット取得に必須）
    brew install ffmpeg    # 動画マージ・変換に必須

使い方:

    python main.py "<URL>" [オプション]

モード:

    デフォルト  最高画質ダウンロード + M1 ハードウェアエンコード（推奨）
    --fast      H.264 ストリームコピー（最大 1080p・数秒）
    --hq        最高画質 + libx264 ソフトウェアエンコード（最高品質・低速）

Note:
    URL に ``?`` が含まれる場合は必ずクォートで囲んでください。
    zsh がワイルドカードとして解釈するためです。
"""

import argparse
import re
import sys
import threading
import time
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DateRange, DownloadError

# ── 定数 ──────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent / "downloads"
ARCHIVE_DIR = OUTPUT_DIR / ".archive"

QUALITY_OPTIONS = ["best", "2160", "1440",
                   "1080", "720", "480", "360", "240", "144"]
FORMAT_OPTIONS = ["mp4", "mkv", "webm"]

# libx264 再エンコード時の品質（CRF: 低いほど高品質、18 は視覚的無劣化に近い）
FFMPEG_CRF = "18"

COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


# ── ダウンロード結果トラッカー ─────────────────────────────────────────────────
class DownloadTracker:
    """プレイリスト全体のダウンロード結果を動画単位で追跡するクラス。

    yt-dlp の progress_hooks と postprocessor_hooks、およびカスタムロガーと
    連携して各動画の成否を記録し、完了後にサマリーを表示する。

    Attributes:
        succeeded: ダウンロード成功した動画の情報リスト (title, url)。
        failed: ダウンロード失敗した動画の情報リスト (title, url, reason)。
    """

    def __init__(self) -> None:
        """DownloadTracker を初期化する。"""
        self.succeeded: list[dict] = []
        self.failed:    list[dict] = []
        self._current:  dict = {}   # 現在処理中の動画情報

    def set_current(self, info_dict: dict) -> None:
        """現在処理中の動画情報を更新する。progress_hook から呼ばれる。

        Args:
            info_dict: yt-dlp の info_dict (title / webpage_url / id を含む)。
        """
        self._current = {
            "title": info_dict.get("title") or info_dict.get("id", "Unknown"),
            "url":   info_dict.get("webpage_url") or info_dict.get("url", ""),
            "id":    info_dict.get("id", ""),
        }

    def record_success(self) -> None:
        """現在処理中の動画を成功リストに追加する。

        映像・音声の2ファイルで複数回呼ばれることがあるため、
        動画IDベースで重複チェックを行う。
        """
        if not self._current:
            return
        vid_id = self._current.get("id", "")
        already = any(v.get("id") == vid_id for v in self.succeeded)
        if not already:
            self.succeeded.append(dict(self._current))

    def record_failure(self, reason: str) -> None:
        """現在処理中の動画を失敗リストに追加する。カスタムロガーから呼ばれる。

        同じ動画IDで複数回エラーが来ることがあるため、IDベースで重複チェックする。
        また、失敗した動画が誤って成功リストに入っている場合は除去する。

        Args:
            reason: yt-dlp が報告したエラーメッセージ。
        """
        if not self._current:
            return
        vid_id = self._current.get("id", "")
        # 誤って成功リストに入っていれば除去
        self.succeeded = [v for v in self.succeeded if v.get("id") != vid_id]
        # 失敗リストへ追加（重複チェック）
        already = any(v.get("id") == vid_id for v in self.failed)
        if not already:
            entry = {**self._current, "reason": reason}
            self.failed.append(entry)

    def print_summary(self) -> None:
        """ダウンロード完了後の結果サマリーをターミナルに出力する。

        成功件数・失敗件数・失敗動画の詳細 (タイトル・URL・エラー理由) を表示する。
        """
        total = len(self.succeeded) + len(self.failed)
        print()
        print(c("══════════════════════════════════════════", "cyan"))
        print(c("  📊  ダウンロード結果サマリー", "cyan", "bold"))
        print(c("══════════════════════════════════════════", "cyan"))
        print(
            f"  合計: {total} 件  "
            f"成功: {c(str(len(self.succeeded)), 'green', 'bold')} 件  "
            f"失敗: {c(str(len(self.failed)), 'red', 'bold') if self.failed else c('0', 'green', 'bold')} 件"
        )

        if self.succeeded:
            print()
            print(c(f"  ✅  成功 ({len(self.succeeded)} 件)", "green", "bold"))
            for i, v in enumerate(self.succeeded, 1):
                print(f"    {i:3}. {v['title']}")

        if self.failed:
            print()
            print(c(f"  ❌  失敗 ({len(self.failed)} 件)", "red", "bold"))
            for i, v in enumerate(self.failed, 1):
                title = v.get("title", "Unknown")
                url = v.get("url",   "")
                reason = v.get("reason", "")
                # エラー理由から先頭の不要なプレフィックスを除去して短くする
                short_reason = reason.split(": ", 2)[-1].split("\n")[0][:80]
                print(f"    {c(str(i).rjust(3), 'red')}. {c(title, 'bold')}")
                if url:
                    print(f"         URL   : {url}")
                print(f"         理由  : {c(short_reason, 'yellow')}")

        print(c("══════════════════════════════════════════", "cyan"))


class YtDlpLogger:
    """yt-dlp のログ出力を横取りするカスタムロガークラス。

    エラーメッセージを ``DownloadTracker`` に転送して失敗動画を記録する。
    警告は標準エラー出力に表示し、デバッグは抑制する。

    Attributes:
        tracker: ダウンロード結果を追跡する DownloadTracker インスタンス。
    """

    def __init__(self, tracker: "DownloadTracker") -> None:
        """YtDlpLogger を初期化する。

        Args:
            tracker: 失敗記録を委譲する DownloadTracker インスタンス。
        """
        self.tracker = tracker

    def debug(self, msg: str) -> None:
        """デバッグメッセージを処理する。

        yt-dlp は通常の情報ログも debug() 経由で送るため、種別ごとに処理を分ける。

        - ``[download]`` の進捗行 (``% of`` を含む行) は抑制する。
          progress_hook が ``\\r`` 上書きで1行表示するため二重出力になるのを防ぐ。
        - ``[Merger]`` / ``[info]`` / ``[VideoRemuxer]`` 等の構造的なログは
          進捗バー行を消してから表示する。

        Args:
            msg: yt-dlp からのデバッグメッセージ。
        """
        CLEAR = "\r" + " " * 80 + "\r"

        if not msg.startswith("["):
            return  # 内部デバッグは抑制

        # [download] の進捗行（"% of" を含む）は progress_hook に任せて抑制
        if msg.startswith("[download]") and "% of" in msg:
            return

        # [download] Downloading item N of M はプレイリスト進捗として表示
        if msg.startswith("[download]") and "Downloading item" in msg:
            print(CLEAR, end="")
            print(c("\n" + msg, "cyan"))
            return

        # Merger / VideoRemuxer / info 等: 進捗バー行を消してから表示
        structural = ("[Merger]", "[VideoRemuxer]",
                      "[info]", "[youtube]", "[ffmpeg]")
        if any(msg.startswith(p) for p in structural):
            print(CLEAR, end="")
            print(msg)
            return

        # その他の [ 始まりログはそのまま表示
        print(msg)

    def warning(self, msg: str) -> None:
        """WARNING メッセージを標準エラー出力に表示する。

        Args:
            msg: yt-dlp からの警告メッセージ。
        """
        print(c(f"[WARN]  {msg}", "yellow"), file=sys.stderr)

    def error(self, msg: str) -> None:
        """エラーメッセージを標準エラー出力に表示し、失敗として記録する。

        Args:
            msg: yt-dlp からのエラーメッセージ。
        """
        print(c(f"[ERROR] {msg}", "red"), file=sys.stderr)
        self.tracker.record_failure(msg)


# ── URL 種別判定 ─────────────────────────────────────────────────────────────
_CHANNEL_PATTERNS = (
    r"youtube\.com/@([\w\-]+)",
    r"youtube\.com/channel/([\w\-]+)",
    r"youtube\.com/c/([\w\-]+)",
    r"youtube\.com/user/([\w\-]+)",
)


def detect_url_type(url: str) -> str:
    """YouTube URL の種別を判定する。

    Args:
        url: YouTube URL。

    Returns:
        "channel" / "playlist" / "video" のいずれか。
    """
    if any(re.search(p, url) for p in _CHANNEL_PATTERNS):
        return "channel"
    if re.search(r"youtube\.com/playlist\?list=", url):
        return "playlist"
    return "video"


def extract_channel_name(url: str) -> str:
    """チャンネル URL からディレクトリ名に使う識別子を抽出する。

    Args:
        url: YouTube チャンネル URL。

    Returns:
        チャンネル識別子 (``@username`` の ``username`` 部分等)。マッチしない場合は
        ``"unknown_channel"``。
    """
    for pattern in _CHANNEL_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return "unknown_channel"


# ── ユーティリティ ────────────────────────────────────────────────────────────
def c(text: str, *keys: str) -> str:
    """ANSIカラーコードを付与した文字列を返す。

    標準出力が TTY でない場合 (パイプやリダイレクト) はカラーコードを付与しない。

    Args:
        text: 色付けしたい文字列。
        *keys: COLORS に定義されたキー名 (複数指定可)。

    Returns:
        カラーコード付きの文字列。非 TTY では text をそのまま返す。
    """
    if not sys.stdout.isatty():
        return text
    prefix = "".join(COLORS[k] for k in keys)
    return f"{prefix}{text}{COLORS['reset']}"


def info(msg: str) -> None:
    """INFO レベルのメッセージを標準出力に表示する。

    Args:
        msg: 表示するメッセージ。
    """
    print(c(f"[INFO]  {msg}", "cyan"))


def ok(msg: str) -> None:
    """成功メッセージを標準出力に表示する。

    Args:
        msg: 表示するメッセージ。
    """
    print(c(f"[OK]    {msg}", "green", "bold"))


def warn(msg: str) -> None:
    """WARNING レベルのメッセージを標準エラー出力に表示する。

    Args:
        msg: 表示するメッセージ。
    """
    print(c(f"[WARN]  {msg}", "yellow"), file=sys.stderr)


def error(msg: str) -> None:
    """ERROR レベルのメッセージを標準エラー出力に表示する。

    Args:
        msg: 表示するメッセージ。
    """
    print(c(f"[ERROR] {msg}", "red", "bold"), file=sys.stderr)


def fmt_seconds(secs: float) -> str:
    """秒数を ``MM:SS`` 形式の文字列に変換する。

    Args:
        secs: 変換する秒数。

    Returns:
        ``MM:SS`` 形式の文字列。
    """
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}"


# ── エンコード進捗スピナー ────────────────────────────────────────────────────
class EncodingSpinner:
    """エンコード中の経過時間をリアルタイム表示するスピナークラス。

    バックグラウンドスレッドで動作し、エンコード開始から経過した時間と
    スピナーアニメーションをターミナルに表示する。

    Attributes:
        label: スピナーに表示するラベル文字列。
        tracker: 成功記録を委譲する DownloadTracker インスタンス。
    """

    def __init__(self, label: str = "エンコード中", tracker: "DownloadTracker | None" = None) -> None:
        """EncodingSpinner を初期化する。

        Args:
            label: スピナーに表示するラベル文字列。
            tracker: 成功記録を委譲する DownloadTracker インスタンス (省略可)。
        """
        self.label = label
        self.tracker = tracker
        self._stop_evt = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._start_ts = 0.0

    def start(self) -> None:
        """スピナーを開始する。

        バックグラウンドスレッドを起動して経過時間の表示を開始する。
        """
        self._start_ts = time.time()
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """スピナーを停止する。スレッドを終了させ、完了メッセージを表示する。"""
        self._stop_evt.set()
        self._thread.join()
        elapsed = time.time() - self._start_ts
        # 進捗行をクリアして完了メッセージを表示
        print(f"\r{' ' * 60}\r", end="")
        print(c(f"  ✅  エンコード完了  (所要時間: {fmt_seconds(elapsed)})", "green"))

    def _run(self) -> None:
        """バックグラウンドスレッドのメインループ。

        0.1 秒ごとにスピナーと経過時間を更新して標準出力に書き込む。
        """
        idx = 0
        while not self._stop_evt.is_set():
            elapsed = time.time() - self._start_ts
            frame = SPINNER_FRAMES[idx % len(SPINNER_FRAMES)]
            line = (
                f"\r  {c(frame, 'yellow')}  {c(self.label, 'yellow')}"
                f"  経過: {c(fmt_seconds(elapsed), 'bold')}"
                f"  {c('(Ctrl+C で中断)', 'reset')}   "
            )
            print(line, end="", flush=True)
            idx += 1
            time.sleep(0.1)


# ── 後処理フック ──────────────────────────────────────────────────────────────
def make_postprocessor_hook(spinner: EncodingSpinner):
    """yt-dlp の後処理フック関数を生成して返す。

    FFmpegMergerPP または FFmpegVideoConvertorPP の開始・終了イベントで
    スピナーを制御し、完了時に DownloadTracker へ成功を記録する。

    Args:
        spinner: 制御対象の EncodingSpinner インスタンス (tracker を内包)。

    Returns:
        yt-dlp の ``postprocessor_hooks`` に渡すコールバック関数。
    """
    encoding_pps = {
        "FFmpegMergerPP",
        "FFmpegVideoConvertorPP",
        "FFmpegVideoRemuxerPP",
    }

    def hook(d: dict) -> None:
        """yt-dlp から呼ばれる後処理コールバック。

        Args:
            d: yt-dlp が渡す後処理情報辞書。
        """
        pp = d.get("postprocessor", "")
        status = d.get("status", "")

        if pp in encoding_pps:
            if status == "started":
                filename = Path(
                    d.get("info_dict", {}).get("filepath", "")).name
                label = f"マージ / エンコード中: {filename}"
                spinner.label = label
                print()  # 改行してからスピナーを開始
                spinner.start()
            elif status == "finished":
                spinner.stop()
                # マージ・変換完了 = その動画のダウンロード成功
                if spinner.tracker is not None:
                    spinner.tracker.record_success()

    return hook


# ── フォーマット文字列の構築 ──────────────────────────────────────────────────
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


# ── ydl オプションの構築 ──────────────────────────────────────────────────────
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
    yt_logger = YtDlpLogger(spinner.tracker)  # type: ignore[arg-type]
    common = {
        "outtmpl":             outtmpl,
        # type: ignore[arg-type]
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
    }

    if mode == "fast":
        # ストリームコピー: コンテナ詰め替えのみ、数秒で完了
        opts["postprocessor_args"] = {
            "ffmpeg": ["-c", "copy", "-movflags", "+faststart"]
        }

    elif mode == "normal":
        # h264_videotoolbox: Apple M1/M2/M3 のハードウェアエンコーダー
        # libx264 の 10〜20 倍高速で、品質も実用上十分。
        # -q:v 25    : VideoToolbox の品質スケール（低いほど高品質、0〜100）
        # -allow_sw  : ハードウェア制限時にソフトウェアへフォールバック
        # -c:a aac   : AAC エンコード（QuickTime 対応）
        opts["postprocessor_args"] = {
            "ffmpeg": [
                "-c:v", "h264_videotoolbox",
                "-q:v", "25",
                "-allow_sw", "1",
                "-c:a", "aac", "-b:a", "256k",
                "-movflags", "+faststart",
            ]
        }

    else:  # hq
        # libx264: ソフトウェアエンコード。最高品質だが M1 でも数十分かかる
        # -crf 18       : 視覚的無劣化に近い高品質（0=無劣化 〜 51=最低）
        # -preset medium: slow と比較して 30-40% 高速、品質差はほぼ知覚不能
        opts["postprocessor_args"] = {
            "ffmpeg": [
                "-c:v", "libx264", "-crf", FFMPEG_CRF, "-preset", "medium",
                "-c:a", "aac", "-b:a", "256k",
                "-movflags", "+faststart",
            ]
        }

    return opts


# ── ダウンロード進捗フック ────────────────────────────────────────────────────
def make_progress_hook(tracker: "DownloadTracker | None"):
    """yt-dlp のダウンロード進捗を表示するフック関数を生成して返す。

    進捗を表示しつつ、成功した動画を DownloadTracker に記録する。

    Args:
        tracker: 成功記録を委譲する DownloadTracker インスタンス。

    Returns:
        yt-dlp の ``progress_hooks`` に渡すコールバック関数。
    """
    last_filename: list[str | None] = [None]

    def hook(d: dict) -> None:
        """yt-dlp から呼ばれる進捗コールバック。

        Args:
            d: yt-dlp が渡す進捗情報辞書。
        """
        status = d.get("status")
        filename = d.get("filename", "")
        info_dict = d.get("info_dict", {})

        # 動画情報が取れたタイミングで tracker の現在動画を更新する
        if info_dict and tracker is not None:
            tracker.set_current(info_dict)

        if status == "downloading":
            # ファイルが切り替わったときだけファイル名行を1回だけ表示
            if filename != last_filename[0]:
                last_filename[0] = filename
                short = Path(filename).name
                # 前の進捗バー行を消してからファイル名を出力
                print(f"\r{' ' * 80}\r", end="")
                print(c(f"  ▶ {short}", "bold"))

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
            bar_width = 36
            filled = int(bar_width * bar_val / bar_total)
            bar = "█" * filled + "░" * (bar_width - filled)
            # \r で行頭に戻って上書き → 同じ1行がパーセントだけ変化して見える
            print(
                f"\r  [{bar}] {c(percent,'green')}  {total}"
                f"  {c(speed,'cyan')}  ETA {c(eta,'yellow')}   ",
                end="",
                flush=True,
            )

        elif status == "finished":
            # ダウンロード完了時に進捗バー行を改行して確定表示
            print()
            # ファイル単体のダウンロード成功を仮記録する。
            # プレイリストでは映像・音声の2ファイルで計2回呼ばれるが、
            # record_success は重複チェック済みなので問題ない。
            # postprocessor_hook の "finished" も呼ばれる場合は重複になるが無害。
            if tracker is not None and tracker._current:
                tracker.record_success()

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

    # 出力先とアーカイブパスの決定
    if url_type == "channel":
        channel_name = extract_channel_name(url)
        out_dir = OUTPUT_DIR / channel_name
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path: str | None = str(ARCHIVE_DIR / f"{channel_name}.txt")
    elif url_type == "playlist" and use_archive:
        out_dir = OUTPUT_DIR
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = str(ARCHIVE_DIR / "playlists.txt")
    else:
        out_dir = OUTPUT_DIR
        archive_path = None

    out_dir.mkdir(parents=True, exist_ok=True)
    # 同名タイトルの動画が衝突しないよう動画IDを付加する
    outtmpl = str(out_dir / "%(title)s [%(id)s].%(ext)s")

    # 日付フィルタの構築
    for date_str, date_label in (
        (date_after, "--date-after"), (date_before, "--date-before"),
    ):
        if date_str is not None and not re.fullmatch(r"\d{8}", date_str):
            error(f"{date_label} の形式が不正です（YYYYMMDD で指定してください）: {date_str}")
            sys.exit(1)

    date_range_obj: DateRange | None = None
    if date_after is not None or date_before is not None:
        date_range_obj = DateRange(start=date_after, end=date_before)

    playlist_items = f"1:{limit}" if limit is not None else None

    # 情報表示
    if url_type == "channel":
        info(f"チャンネル検出: {c(channel_name, 'bold')}")

    MODE_LABELS = {
        "fast":   (c("高速", "green"),   c("ストリームコピー（再エンコードなし・最大 1080p）", "green")),
        "normal": (c("標準（推奨）", "yellow"), c("h264_videotoolbox ハードウェアエンコード（M1 最適化）", "yellow")),
        "hq":     (c("最高品質", "red"),  c("libx264 ソフトウェアエンコード（低速・高品質）", "red")),
    }

    if audio_only:
        info("モード: 音声のみ (MP3 320kbps)")
    else:
        mode_label, desc = MODE_LABELS[mode]
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

    tracker = DownloadTracker()
    spinner = EncodingSpinner(tracker=tracker)
    ydl_opts = build_ydl_opts(
        quality, fmt, audio_only, no_playlist, outtmpl, mode, spinner,
        archive_path=archive_path,
        date_range=date_range_obj,
        playlist_items=playlist_items,
    )

    try:
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
        spinner._stop_evt.set()  # スピナーが動いていれば停止
        warn("ユーザーによって中断されました。")
        tracker.print_summary()
        sys.exit(130)


# ── CLI ───────────────────────────────────────────────────────────────────────
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
        prog="yt_downloader",
        description=c(
            "🎬  yt-dlp を使った YouTube 動画ダウンローダー（QuickTime 対応）", "bold"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
モード:
  デフォルト  最高画質DL + h264_videotoolbox（M1ハード）。数分。【推奨】
  --fast      H.264ストリームコピー。数秒。最大1080p。
  --hq        最高画質DL + libx264 slow。数十分。最高品質。

使用例:
  # 標準モード（推奨）
  python yt_downloader.py "https://youtu.be/xxxxx"

  # 高速モード
  python yt_downloader.py "https://youtu.be/xxxxx" --fast

  # 最高品質モード（時間がかかっても良い場合）
  python yt_downloader.py "https://youtu.be/xxxxx" --hq

  # 解像度を指定
  python yt_downloader.py "https://youtu.be/xxxxx" -q 1080

  # プレイリスト全体をダウンロード
  python yt_downloader.py "https://www.youtube.com/playlist?list=xxxxx"

  # チャンネル全動画をダウンロード
  python yt_downloader.py "https://www.youtube.com/@username/videos"

  # チャンネルから最新 10 件のみ
  python yt_downloader.py "https://www.youtube.com/@username" --limit 10

  # 2025年以降の動画のみ
  python yt_downloader.py "https://www.youtube.com/@username" --date-after 20250101

  # 音声のみ MP3
  python yt_downloader.py "https://youtu.be/xxxxx" --audio-only

⚠️  URL は必ずクォートで囲んでください（zsh の ? 展開を防ぐため）
⚠️  brew install node を実行しておくと全フォーマットが取得できます

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
        help="最高品質モード: libx264 preset slow（低速・高品質）",
    )

    return parser.parse_args()


def main() -> None:
    """エントリーポイント。ヘッダーを表示してダウンロードを開始する。"""
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

    download(
        url=args.url,
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


if __name__ == "__main__":
    main()
