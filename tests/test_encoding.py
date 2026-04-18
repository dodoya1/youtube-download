"""yt_downloader.encoding のユニットテスト。"""

import time

import pytest

from yt_downloader.encoding import EncodingSpinner


class TestLabel:
    def test_initial_label(self) -> None:
        spinner = EncodingSpinner(label="initial")
        assert spinner.label == "initial"

    def test_set_label_updates_thread_safely(self) -> None:
        spinner = EncodingSpinner(label="old")
        spinner.set_label("new")
        assert spinner.label == "new"


class TestLifecycle:
    def test_start_then_stop(
        self, non_tty_stdout: None, capsys: pytest.CaptureFixture[str],
    ) -> None:
        spinner = EncodingSpinner(label="test")
        spinner.start()
        # バックグラウンドスレッドが走る猶予
        time.sleep(0.15)
        assert spinner._thread is not None
        assert spinner._thread.is_alive()
        spinner.stop()
        # stop 後はスレッドが片付いている
        assert spinner._thread is None
        out = capsys.readouterr().out
        assert "エンコード完了" in out

    def test_double_start_is_ignored(self, non_tty_stdout: None) -> None:
        spinner = EncodingSpinner()
        spinner.start()
        first_thread = spinner._thread
        spinner.start()  # 二重 start 防止
        assert spinner._thread is first_thread
        spinner.force_stop()

    def test_force_stop_does_not_print_completion(
        self,
        non_tty_stdout: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        spinner = EncodingSpinner()
        spinner.start()
        time.sleep(0.12)
        spinner.force_stop()
        out = capsys.readouterr().out
        # 完了メッセージは出ない
        assert "エンコード完了" not in out
        assert spinner._thread is None

    def test_force_stop_before_start_is_safe(self) -> None:
        spinner = EncodingSpinner()
        spinner.force_stop()  # 例外なし
        assert spinner._thread is None
