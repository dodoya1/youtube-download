"""ダウンロード結果を動画単位で追跡する DownloadTracker クラス。"""

from yt_downloader.ui import c


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

    def has_current(self) -> bool:
        """現在処理中の動画情報が設定されているかどうかを返す。

        Returns:
            set_current() により現在動画が設定済みなら True。
        """
        return bool(self._current)

    @staticmethod
    def _is_recorded(vid_id: str, entries: list[dict]) -> bool:
        """動画 ID が指定リストに記録済みかどうかを判定する。

        Args:
            vid_id: 判定対象の動画 ID。
            entries: 検索対象の記録リスト。

        Returns:
            同じ ID のエントリが存在すれば True。
        """
        return any(v.get("id") == vid_id for v in entries)

    def record_success(self) -> None:
        """現在処理中の動画を成功リストに追加する。

        映像・音声の2ファイルで複数回呼ばれることがあるため、
        動画IDベースで重複チェックを行う。
        """
        if not self._current:
            return
        vid_id = self._current.get("id", "")
        if not self._is_recorded(vid_id, self.succeeded):
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
        if not self._is_recorded(vid_id, self.failed):
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
