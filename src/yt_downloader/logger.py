"""yt-dlp 用のカスタムロガー。"""

import sys

from yt_downloader.tracker import DownloadTracker
from yt_downloader.ui import c


class YtDlpLogger:
    """yt-dlp のログ出力を横取りするカスタムロガークラス。

    エラーメッセージを ``DownloadTracker`` に転送して失敗動画を記録する。
    警告は標準エラー出力に表示し、デバッグは抑制する。

    Attributes:
        tracker: ダウンロード結果を追跡する DownloadTracker インスタンス。
    """

    def __init__(self, tracker: DownloadTracker | None) -> None:
        """YtDlpLogger を初期化する。

        Args:
            tracker: 失敗記録を委譲する DownloadTracker インスタンス (省略可)。
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
        if self.tracker is not None:
            self.tracker.record_failure(msg)
