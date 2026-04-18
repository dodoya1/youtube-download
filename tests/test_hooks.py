"""yt_downloader.hooks のユニットテスト。"""

from unittest.mock import MagicMock

import pytest

from yt_downloader.encoding import EncodingSpinner
from yt_downloader.hooks import make_postprocessor_hook, make_progress_hook
from yt_downloader.tracker import DownloadTracker


class TestProgressHook:
    def test_updates_tracker_on_info_dict(
        self, non_tty_stdout: None, mock_info_dict: dict,
    ) -> None:
        tracker = DownloadTracker()
        hook = make_progress_hook(tracker)
        hook({"status": "downloading", "filename": "x.mp4",
             "info_dict": mock_info_dict})
        assert tracker.has_current() is True

    def test_finished_records_success(
        self, non_tty_stdout: None, mock_info_dict: dict,
    ) -> None:
        tracker = DownloadTracker()
        hook = make_progress_hook(tracker)
        hook({"status": "downloading", "filename": "x.mp4",
             "info_dict": mock_info_dict})
        hook({"status": "finished", "filename": "x.mp4", "info_dict": {}})
        assert len(tracker.succeeded) == 1

    def test_finished_without_current_is_noop(self, non_tty_stdout: None) -> None:
        tracker = DownloadTracker()
        hook = make_progress_hook(tracker)
        hook({"status": "finished", "filename": "x.mp4", "info_dict": {}})
        assert tracker.succeeded == []

    def test_error_status_prints_error(
        self, non_tty_stdout: None, capsys: pytest.CaptureFixture[str],
    ) -> None:
        hook = make_progress_hook(None)
        hook({"status": "error", "filename": "x.mp4", "info_dict": {}})
        err = capsys.readouterr().err
        assert "[ERROR]" in err

    def test_tracker_none_is_safe(self, non_tty_stdout: None, mock_info_dict: dict) -> None:
        hook = make_progress_hook(None)
        # tracker が None でも例外なし
        hook({"status": "downloading", "filename": "x.mp4",
             "info_dict": mock_info_dict})
        hook({"status": "finished",    "filename": "x.mp4", "info_dict": {}})


class TestPostprocessorHook:
    def test_started_sets_label_and_starts_spinner(self, non_tty_stdout: None) -> None:
        spinner = MagicMock(spec=EncodingSpinner)
        spinner.tracker = None
        hook = make_postprocessor_hook(spinner)
        hook({
            "postprocessor": "FFmpegMergerPP",
            "status":        "started",
            "info_dict":     {"filepath": "/tmp/out.mp4"},
        })
        spinner.set_label.assert_called_once()
        spinner.start.assert_called_once()

    def test_finished_stops_spinner_and_records_success(
        self, non_tty_stdout: None, mock_info_dict: dict,
    ) -> None:
        tracker = DownloadTracker()
        tracker.set_current(mock_info_dict)
        spinner = MagicMock(spec=EncodingSpinner)
        spinner.tracker = tracker
        hook = make_postprocessor_hook(spinner)
        hook({"postprocessor": "FFmpegMergerPP", "status": "finished"})
        spinner.stop.assert_called_once()
        assert len(tracker.succeeded) == 1

    def test_non_encoding_postprocessor_is_ignored(self, non_tty_stdout: None) -> None:
        spinner = MagicMock(spec=EncodingSpinner)
        spinner.tracker = None
        hook = make_postprocessor_hook(spinner)
        hook({"postprocessor": "SomeOtherPP", "status": "started"})
        spinner.start.assert_not_called()
        spinner.set_label.assert_not_called()
