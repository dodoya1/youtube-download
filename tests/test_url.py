"""yt_downloader.url のユニットテスト。"""

import pytest

from yt_downloader.url import detect_url_type, extract_channel_name


class TestDetectUrlType:
    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/@username",
        "https://www.youtube.com/@username/videos",
        "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx",
        "https://www.youtube.com/c/custom-name",
        "https://www.youtube.com/user/legacy_name",
    ])
    def test_channel_patterns(self, url: str) -> None:
        assert detect_url_type(url) == "channel"

    def test_playlist(self) -> None:
        assert detect_url_type(
            "https://www.youtube.com/playlist?list=PLxxxxx") == "playlist"

    @pytest.mark.parametrize("url", [
        "https://youtu.be/abc123",
        "https://www.youtube.com/watch?v=abc123",
    ])
    def test_video(self, url: str) -> None:
        assert detect_url_type(url) == "video"

    def test_channel_takes_priority_over_video(self) -> None:
        # /@username/watch?v=... のようなケースでもチャンネル判定を優先する
        url = "https://www.youtube.com/@username/videos"
        assert detect_url_type(url) == "channel"


class TestExtractChannelName:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/@username", "username"),
        ("https://www.youtube.com/@username/videos", "username"),
        ("https://www.youtube.com/channel/UCabc123", "UCabc123"),
        ("https://www.youtube.com/c/custom-name", "custom-name"),
        ("https://www.youtube.com/user/legacy_name", "legacy_name"),
    ])
    def test_extraction(self, url: str, expected: str) -> None:
        assert extract_channel_name(url) == expected

    def test_no_match_returns_fallback(self) -> None:
        assert extract_channel_name(
            "https://youtu.be/abc123") == "unknown_channel"
