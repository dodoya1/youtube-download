"""yt_downloader.url のユニットテスト。"""

import pytest

from yt_downloader.url import (
    detect_url_type,
    extract_channel_name,
    extract_twitter_username,
)


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

    @pytest.mark.parametrize("url", [
        "https://x.com/someuser/status/1234567890",
        "https://twitter.com/someuser/status/1234567890",
        "https://x.com/some_user-123/status/9876543210",
        "https://mobile.twitter.com/someuser/status/1234567890",
    ])
    def test_twitter_video(self, url: str) -> None:
        assert detect_url_type(url) == "twitter_video"

    @pytest.mark.parametrize("url", [
        "https://x.com/i/spaces/1AbCdEfGhIjKl",
        "https://twitter.com/i/spaces/1AbCdEfGhIjKl",
    ])
    def test_twitter_spaces(self, url: str) -> None:
        assert detect_url_type(url) == "twitter_spaces"

    def test_twitter_spaces_takes_priority_over_video(self) -> None:
        # i/spaces/ は status/ と衝突しないが念のため優先順序を保証する
        url = "https://x.com/i/spaces/1AbCdEfGhIjKl"
        assert detect_url_type(url) == "twitter_spaces"


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


class TestExtractTwitterUsername:
    @pytest.mark.parametrize("url,expected", [
        ("https://x.com/someuser/status/1234567890", "someuser"),
        ("https://twitter.com/someuser/status/1234567890", "someuser"),
        ("https://x.com/some_user-123/status/9876543210", "some_user-123"),
        ("https://mobile.twitter.com/abc/status/1", "abc"),
    ])
    def test_extraction(self, url: str, expected: str) -> None:
        assert extract_twitter_username(url) == expected

    def test_no_match_returns_fallback(self) -> None:
        assert extract_twitter_username(
            "https://x.com/i/spaces/1AbCdEfGhIjKl") == "unknown_user"
