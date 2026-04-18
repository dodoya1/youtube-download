"""yt-dlp の progress_hooks / postprocessor_hooks を生成するファクトリ関数群。"""

from collections.abc import Callable
from pathlib import Path

from yt_downloader.encoding import EncodingSpinner
from yt_downloader.tracker import DownloadTracker
from yt_downloader.ui import c, error


def make_postprocessor_hook(spinner: EncodingSpinner) -> Callable[[dict], None]:
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
                spinner.set_label(f"マージ / エンコード中: {filename}")
                print()  # 改行してからスピナーを開始
                spinner.start()
            elif status == "finished":
                spinner.stop()
                # マージ・変換完了 = その動画のダウンロード成功
                if spinner.tracker is not None:
                    spinner.tracker.record_success()

    return hook


def make_progress_hook(tracker: DownloadTracker | None) -> Callable[[dict], None]:
    """yt-dlp のダウンロード進捗を表示するフック関数を生成して返す。

    進捗を表示しつつ、成功した動画を DownloadTracker に記録する。

    Args:
        tracker: 成功記録を委譲する DownloadTracker インスタンス。

    Returns:
        yt-dlp の ``progress_hooks`` に渡すコールバック関数。
    """
    last_filename: str | None = None

    def hook(d: dict) -> None:
        """yt-dlp から呼ばれる進捗コールバック。

        Args:
            d: yt-dlp が渡す進捗情報辞書。
        """
        nonlocal last_filename
        status = d.get("status")
        filename = d.get("filename", "")
        info_dict = d.get("info_dict", {})

        # 動画情報が取れたタイミングで tracker の現在動画を更新する
        if info_dict and tracker is not None:
            tracker.set_current(info_dict)

        if status == "downloading":
            # ファイルが切り替わったときだけファイル名行を1回だけ表示
            if filename != last_filename:
                last_filename = filename
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
            if tracker is not None and tracker.has_current():
                tracker.record_success()

        elif status == "error":
            print()
            error("ダウンロードに失敗しました。")

    return hook
