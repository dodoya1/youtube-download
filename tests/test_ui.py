"""yt_downloader.ui のユニットテスト。"""

import sys

import pytest

from yt_downloader.ui import c, error, fmt_seconds, info, ok, warn


class TestC:
    def test_non_tty_returns_plain_text(self, non_tty_stdout: None) -> None:
        assert c("hello", "red") == "hello"

    def test_tty_wraps_with_ansi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
        result = c("hello", "red")
        assert "\033[91m" in result
        assert "hello" in result
        assert result.endswith("\033[0m")

    def test_multiple_keys_are_combined(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
        result = c("x", "red", "bold")
        assert "\033[91m" in result
        assert "\033[1m" in result


class TestFmtSeconds:
    @pytest.mark.parametrize("secs,expected", [
        (0,    "00:00"),
        (1,    "00:01"),
        (59,   "00:59"),
        (60,   "01:00"),
        (61,   "01:01"),
        (3599, "59:59"),
        (3600, "60:00"),
        (3661, "61:01"),
    ])
    def test_formatting(self, secs: int, expected: str) -> None:
        assert fmt_seconds(secs) == expected

    def test_truncates_fractional_seconds(self) -> None:
        assert fmt_seconds(59.9) == "00:59"


class TestLogFunctions:
    def test_info_writes_to_stdout(
        self, non_tty_stdout: None, capsys: pytest.CaptureFixture[str],
    ) -> None:
        info("hello")
        captured = capsys.readouterr()
        assert "[INFO]" in captured.out
        assert "hello" in captured.out

    def test_ok_writes_to_stdout(
        self, non_tty_stdout: None, capsys: pytest.CaptureFixture[str],
    ) -> None:
        ok("done")
        captured = capsys.readouterr()
        assert "[OK]" in captured.out
        assert "done" in captured.out

    def test_warn_writes_to_stderr(
        self, non_tty_stdout: None, capsys: pytest.CaptureFixture[str],
    ) -> None:
        warn("careful")
        captured = capsys.readouterr()
        assert "[WARN]" in captured.err
        assert "careful" in captured.err
        assert captured.out == ""

    def test_error_writes_to_stderr(
        self, non_tty_stdout: None, capsys: pytest.CaptureFixture[str],
    ) -> None:
        error("bad")
        captured = capsys.readouterr()
        assert "[ERROR]" in captured.err
        assert "bad" in captured.err
        assert captured.out == ""
