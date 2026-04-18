"""エンコード進捗を表示する EncodingSpinner。"""

import threading
import time

from yt_downloader.config import SPINNER_FRAMES
from yt_downloader.tracker import DownloadTracker
from yt_downloader.ui import c, fmt_seconds


class EncodingSpinner:
    """エンコード中の経過時間をリアルタイム表示するスピナークラス。

    バックグラウンドスレッドで動作し、エンコード開始から経過した時間と
    スピナーアニメーションをターミナルに表示する。

    Attributes:
        tracker: 成功記録を委譲する DownloadTracker インスタンス。
    """

    def __init__(self, label: str = "エンコード中", tracker: DownloadTracker | None = None) -> None:
        """EncodingSpinner を初期化する。

        Args:
            label: スピナーに表示するラベル文字列。
            tracker: 成功記録を委譲する DownloadTracker インスタンス (省略可)。
        """
        self._label = label
        self.tracker = tracker
        self._stop_evt = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_ts = 0.0
        self._lock = threading.Lock()

    @property
    def label(self) -> str:
        """スピナーに表示するラベル文字列。"""
        with self._lock:
            return self._label

    def set_label(self, label: str) -> None:
        """スピナーのラベルをスレッド安全に更新する。

        Args:
            label: 新しいラベル文字列。
        """
        with self._lock:
            self._label = label

    def start(self) -> None:
        """スピナーを開始する。

        バックグラウンドスレッドを起動して経過時間の表示を開始する。
        既に動作中の場合は何もしない (二重起動防止)。
        """
        if self._thread is not None and self._thread.is_alive():
            return
        with self._lock:
            self._start_ts = time.time()
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """スピナーを停止する。スレッドを終了させ、完了メッセージを表示する。"""
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        with self._lock:
            elapsed = time.time() - self._start_ts
        # 進捗行をクリアして完了メッセージを表示
        print(f"\r{' ' * 60}\r", end="")
        print(c(f"  ✅  エンコード完了  (所要時間: {fmt_seconds(elapsed)})", "green"))

    def force_stop(self) -> None:
        """スピナーを強制停止する。完了メッセージは表示しない。

        KeyboardInterrupt など、例外経路でスレッドを確実に終わらせる用途。
        """
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self) -> None:
        """バックグラウンドスレッドのメインループ。

        0.1 秒ごとにスピナーと経過時間を更新して標準出力に書き込む。
        """
        idx = 0
        while not self._stop_evt.is_set():
            with self._lock:
                elapsed = time.time() - self._start_ts
                label = self._label
            frame = SPINNER_FRAMES[idx % len(SPINNER_FRAMES)]
            line = (
                f"\r  {c(frame, 'yellow')}  {c(label, 'yellow')}"
                f"  経過: {c(fmt_seconds(elapsed), 'bold')}"
                f"  {c('(Ctrl+C で中断)', 'reset')}   "
            )
            print(line, end="", flush=True)
            idx += 1
            time.sleep(0.1)
