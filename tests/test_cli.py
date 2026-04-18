"""yt_downloader.cli.main の複数URL対応のテスト。"""

from unittest.mock import patch

import pytest

from yt_downloader import cli


def _run_main(argv: list[str]) -> None:
    with patch("sys.argv", ["main.py", *argv]):
        cli.main()


class TestMainSingleUrl:
    def test_download_called_once(self, non_tty_stdout: None) -> None:
        with patch("yt_downloader.cli.download") as mock_dl:
            _run_main(["https://youtu.be/aaa"])
            assert mock_dl.call_count == 1
            assert mock_dl.call_args.kwargs["url"] == "https://youtu.be/aaa"

    def test_mode_fast_flag(self, non_tty_stdout: None) -> None:
        with patch("yt_downloader.cli.download") as mock_dl:
            _run_main(["https://youtu.be/aaa", "--fast"])
            assert mock_dl.call_args.kwargs["mode"] == "fast"


class TestMainMultipleUrls:
    def test_download_called_for_each_url(self, non_tty_stdout: None) -> None:
        urls = ["https://youtu.be/a", "https://youtu.be/b", "https://youtu.be/c"]
        with patch("yt_downloader.cli.download") as mock_dl:
            _run_main(urls)
            assert mock_dl.call_count == 3
            called_urls = [call.kwargs["url"] for call in mock_dl.call_args_list]
            assert called_urls == urls

    def test_shared_options_applied_to_all(self, non_tty_stdout: None) -> None:
        urls = ["https://youtu.be/a", "https://youtu.be/b"]
        with patch("yt_downloader.cli.download") as mock_dl:
            _run_main([*urls, "--hq", "-q", "1080"])
            for call in mock_dl.call_args_list:
                assert call.kwargs["mode"] == "hq"
                assert call.kwargs["quality"] == "1080"

    def test_failure_continues_and_exits_with_code_1(
        self, non_tty_stdout: None,
    ) -> None:
        urls = ["https://youtu.be/ok1", "https://youtu.be/bad", "https://youtu.be/ok2"]

        def side_effect(*, url: str, **_: object) -> None:
            if url == "https://youtu.be/bad":
                raise SystemExit(1)

        with patch("yt_downloader.cli.download", side_effect=side_effect) as mock_dl:
            with pytest.raises(SystemExit) as exc:
                _run_main(urls)
            assert exc.value.code == 1
            # 3 件すべて呼ばれていること（途中で止まっていない）
            assert mock_dl.call_count == 3

    def test_keyboard_interrupt_propagates_immediately(
        self, non_tty_stdout: None,
    ) -> None:
        urls = ["https://youtu.be/a", "https://youtu.be/b"]

        def side_effect(*, url: str, **_: object) -> None:
            if url == "https://youtu.be/a":
                raise SystemExit(130)

        with patch("yt_downloader.cli.download", side_effect=side_effect) as mock_dl:
            with pytest.raises(SystemExit) as exc:
                _run_main(urls)
            assert exc.value.code == 130
            # 130 は即時中断 → 2件目は呼ばれない
            assert mock_dl.call_count == 1

    def test_all_success_does_not_exit(self, non_tty_stdout: None) -> None:
        urls = ["https://youtu.be/a", "https://youtu.be/b"]
        with patch("yt_downloader.cli.download") as mock_dl:
            _run_main(urls)  # SystemExit が出ないこと
            assert mock_dl.call_count == 2
