"""yt_downloader.tracker のユニットテスト。"""

import pytest

from yt_downloader.tracker import DownloadTracker


class TestSetCurrentAndHasCurrent:
    def test_has_current_is_false_initially(self) -> None:
        t = DownloadTracker()
        assert t.has_current() is False

    def test_has_current_after_set(self, mock_info_dict: dict) -> None:
        t = DownloadTracker()
        t.set_current(mock_info_dict)
        assert t.has_current() is True

    def test_set_current_falls_back_to_id_when_no_title(self) -> None:
        t = DownloadTracker()
        t.set_current({"id": "xyz"})
        t.record_success()
        assert t.succeeded[0]["title"] == "xyz"


class TestRecordSuccess:
    def test_basic_flow(self, mock_info_dict: dict) -> None:
        t = DownloadTracker()
        t.set_current(mock_info_dict)
        t.record_success()
        assert len(t.succeeded) == 1
        assert t.succeeded[0]["id"] == "abc123"
        assert t.succeeded[0]["title"] == "Sample Video"

    def test_duplicate_id_is_not_recorded_twice(self, mock_info_dict: dict) -> None:
        t = DownloadTracker()
        t.set_current(mock_info_dict)
        t.record_success()
        t.record_success()
        assert len(t.succeeded) == 1

    def test_no_current_is_noop(self) -> None:
        t = DownloadTracker()
        t.record_success()
        assert t.succeeded == []


class TestRecordFailure:
    def test_basic_flow(self, mock_info_dict: dict) -> None:
        t = DownloadTracker()
        t.set_current(mock_info_dict)
        t.record_failure("network error")
        assert len(t.failed) == 1
        assert t.failed[0]["reason"] == "network error"

    def test_duplicate_id_is_not_recorded_twice(self, mock_info_dict: dict) -> None:
        t = DownloadTracker()
        t.set_current(mock_info_dict)
        t.record_failure("err1")
        t.record_failure("err2")
        assert len(t.failed) == 1
        # 最初のエラー理由が保持される
        assert t.failed[0]["reason"] == "err1"

    def test_removes_from_succeeded_list(self, mock_info_dict: dict) -> None:
        t = DownloadTracker()
        t.set_current(mock_info_dict)
        t.record_success()
        assert len(t.succeeded) == 1

        # 同じ動画で失敗が記録されたら成功リストから除去される
        t.record_failure("post-processing failed")
        assert t.succeeded == []
        assert len(t.failed) == 1


class TestPrintSummary:
    def test_empty_summary(
        self, non_tty_stdout: None, capsys: pytest.CaptureFixture[str],
    ) -> None:
        t = DownloadTracker()
        t.print_summary()
        out = capsys.readouterr().out
        assert "ダウンロード結果サマリー" in out
        assert "合計: 0 件" in out

    def test_success_and_failure_counts(
        self,
        non_tty_stdout: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        t = DownloadTracker()
        t.set_current({"id": "v1", "title": "Video 1",
                      "webpage_url": "https://y.be/v1"})
        t.record_success()
        t.set_current({"id": "v2", "title": "Video 2",
                      "webpage_url": "https://y.be/v2"})
        t.record_failure("oops")
        t.print_summary()
        out = capsys.readouterr().out
        assert "合計: 2 件" in out
        assert "Video 1" in out
        assert "Video 2" in out
        assert "oops" in out
