"""yt_downloader.downloader の build_ydl_opts / download のユニットテスト。"""

from unittest.mock import MagicMock, patch

import pytest

from yt_downloader.downloader import _resolve_output_paths, build_ydl_opts, download
from yt_downloader.encoding import EncodingSpinner
from yt_downloader.tracker import DownloadTracker


@pytest.fixture
def spinner_with_tracker() -> EncodingSpinner:
    return EncodingSpinner(tracker=DownloadTracker())


class TestBuildYdlOpts:
    def test_audio_only_uses_mp3_extractor(self, spinner_with_tracker: EncodingSpinner) -> None:
        opts = build_ydl_opts(
            quality="best",
            fmt="mp4",
            audio_only=True,
            no_playlist=False,
            outtmpl="%(title)s.%(ext)s",
            mode="fast",
            spinner=spinner_with_tracker,
        )
        assert opts["format"] == "bestaudio/best"
        assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
        assert opts["postprocessors"][0]["preferredcodec"] == "mp3"

    def test_fast_mode_stream_copy(self, spinner_with_tracker: EncodingSpinner) -> None:
        opts = build_ydl_opts(
            quality="best", fmt="mp4", audio_only=False, no_playlist=False,
            outtmpl="t.mp4", mode="fast", spinner=spinner_with_tracker,
        )
        assert "-c" in opts["postprocessor_args"]["ffmpeg"]
        assert "copy" in opts["postprocessor_args"]["ffmpeg"]

    def test_normal_mode_uses_videotoolbox(self, spinner_with_tracker: EncodingSpinner) -> None:
        opts = build_ydl_opts(
            quality="best", fmt="mp4", audio_only=False, no_playlist=False,
            outtmpl="t.mp4", mode="normal", spinner=spinner_with_tracker,
        )
        assert "h264_videotoolbox" in opts["postprocessor_args"]["ffmpeg"]

    def test_hq_mode_uses_libx264(self, spinner_with_tracker: EncodingSpinner) -> None:
        opts = build_ydl_opts(
            quality="best", fmt="mp4", audio_only=False, no_playlist=False,
            outtmpl="t.mp4", mode="hq", spinner=spinner_with_tracker,
        )
        assert "libx264" in opts["postprocessor_args"]["ffmpeg"]

    def test_retry_settings_are_present(self, spinner_with_tracker: EncodingSpinner) -> None:
        opts = build_ydl_opts(
            quality="best", fmt="mp4", audio_only=False, no_playlist=False,
            outtmpl="t.mp4", mode="normal", spinner=spinner_with_tracker,
        )
        assert opts["socket_timeout"] == 30
        assert opts["retries"] == 10
        assert opts["fragment_retries"] == 10

    def test_archive_path_sets_break_on_existing(self, spinner_with_tracker: EncodingSpinner) -> None:
        opts = build_ydl_opts(
            quality="best", fmt="mp4", audio_only=False, no_playlist=False,
            outtmpl="t.mp4", mode="fast", spinner=spinner_with_tracker,
            archive_path="/tmp/archive.txt",
        )
        assert opts["download_archive"] == "/tmp/archive.txt"
        assert opts["break_on_existing"] is True

    def test_playlist_items_forwarded(self, spinner_with_tracker: EncodingSpinner) -> None:
        opts = build_ydl_opts(
            quality="best", fmt="mp4", audio_only=False, no_playlist=False,
            outtmpl="t.mp4", mode="fast", spinner=spinner_with_tracker,
            playlist_items="1:5",
        )
        assert opts["playlist_items"] == "1:5"

    def test_merge_format_matches_fmt(self, spinner_with_tracker: EncodingSpinner) -> None:
        for fmt in ("mp4", "mkv", "webm"):
            opts = build_ydl_opts(
                quality="best", fmt=fmt, audio_only=False, no_playlist=False,
                outtmpl=f"t.{fmt}", mode="normal", spinner=spinner_with_tracker,
            )
            assert opts["merge_output_format"] == fmt


class TestDownload:
    def test_invalid_date_format_exits(
        self, non_tty_stdout: None, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "yt_downloader.downloader.OUTPUT_DIR", tmp_path / "downloads")
        monkeypatch.setattr(
            "yt_downloader.downloader.ARCHIVE_DIR", tmp_path / "downloads" / ".archive")
        with pytest.raises(SystemExit) as exc:
            download(
                url="https://youtu.be/abc123",
                quality="best",
                fmt="mp4",
                audio_only=False,
                no_playlist=False,
                mode="fast",
                date_after="2025-01-01",  # 不正な形式
            )
        assert exc.value.code == 1

    def test_successful_download_calls_ytdl(
        self, non_tty_stdout: None, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "yt_downloader.downloader.OUTPUT_DIR", tmp_path / "downloads")
        monkeypatch.setattr(
            "yt_downloader.downloader.ARCHIVE_DIR", tmp_path / "downloads" / ".archive")
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.download.return_value = 0

        with patch("yt_downloader.downloader.yt_dlp.YoutubeDL", return_value=mock_ydl) as m:
            download(
                url="https://youtu.be/abc123",
                quality="best",
                fmt="mp4",
                audio_only=False,
                no_playlist=False,
                mode="fast",
            )
            m.assert_called_once()
            mock_ydl.__enter__.return_value.download.assert_called_once_with(
                ["https://youtu.be/abc123"])

    def test_twitter_video_saved_under_twitter_username_dir(
        self, non_tty_stdout: None, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_dir = tmp_path / "downloads"
        monkeypatch.setattr("yt_downloader.downloader.OUTPUT_DIR", output_dir)
        monkeypatch.setattr(
            "yt_downloader.downloader.ARCHIVE_DIR", output_dir / ".archive")
        monkeypatch.setattr(
            "yt_downloader.downloader.TWITTER_DIR", output_dir / "twitter")

        captured_opts: dict = {}

        def capture_opts(opts):
            captured_opts.update(opts)
            mock = MagicMock()
            mock.__enter__.return_value.download.return_value = 0
            return mock

        with patch("yt_downloader.downloader.yt_dlp.YoutubeDL", side_effect=capture_opts):
            download(
                url="https://x.com/jack/status/20",
                quality="best",
                fmt="mp4",
                audio_only=False,
                no_playlist=False,
                mode="fast",
            )

        assert str(output_dir / "twitter" / "jack") in captured_opts["outtmpl"]

    def test_twitter_spaces_forces_audio_only_and_uses_uploader_template(
        self, non_tty_stdout: None, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        output_dir = tmp_path / "downloads"
        monkeypatch.setattr("yt_downloader.downloader.OUTPUT_DIR", output_dir)
        monkeypatch.setattr(
            "yt_downloader.downloader.ARCHIVE_DIR", output_dir / ".archive")
        monkeypatch.setattr(
            "yt_downloader.downloader.TWITTER_DIR", output_dir / "twitter")

        captured_opts: dict = {}

        def capture_opts(opts):
            captured_opts.update(opts)
            mock = MagicMock()
            mock.__enter__.return_value.download.return_value = 0
            return mock

        with patch("yt_downloader.downloader.yt_dlp.YoutubeDL", side_effect=capture_opts):
            download(
                url="https://x.com/i/spaces/1AbCdEfGhIjKl",
                quality="best",
                fmt="mp4",
                audio_only=False,  # 指定無しでも Spaces なら自動で audio-only になる
                no_playlist=False,
                mode="fast",
            )

        # outtmpl に uploader_id のテンプレートが含まれる
        assert "%(uploader_id)s" in captured_opts["outtmpl"]
        # 音声抽出ポストプロセッサーが有効 = 強制 audio-only が効いている
        assert any(
            p.get("key") == "FFmpegExtractAudio"
            for p in captured_opts["postprocessors"]
        )

    def test_download_error_exits(
        self, non_tty_stdout: None, tmp_path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from yt_dlp.utils import DownloadError
        monkeypatch.setattr(
            "yt_downloader.downloader.OUTPUT_DIR", tmp_path / "downloads")
        monkeypatch.setattr(
            "yt_downloader.downloader.ARCHIVE_DIR", tmp_path / "downloads" / ".archive")
        mock_ydl = MagicMock()
        mock_ydl.__enter__.return_value.download.side_effect = DownloadError(
            "boom")

        with patch("yt_downloader.downloader.yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(SystemExit) as exc:
                download(
                    url="https://youtu.be/abc123",
                    quality="best",
                    fmt="mp4",
                    audio_only=False,
                    no_playlist=False,
                    mode="fast",
                )
            assert exc.value.code == 1
