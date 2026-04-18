"""yt_downloader.downloader.build_format_selector のユニットテスト。"""

import pytest

from yt_downloader.downloader import build_format_selector


class TestBuildFormatSelector:
    def test_normal_best(self) -> None:
        selector = build_format_selector("best", "normal")
        assert "bestvideo+bestaudio" in selector

    def test_normal_with_height(self) -> None:
        selector = build_format_selector("1080", "normal")
        assert "height<=1080" in selector

    def test_hq_uses_same_as_normal(self) -> None:
        assert build_format_selector("best", "hq") == \
            build_format_selector("best", "normal")
        assert build_format_selector("720", "hq") == \
            build_format_selector("720", "normal")

    def test_fast_prefers_avc1_and_mp4a(self) -> None:
        selector = build_format_selector("best", "fast")
        assert "vcodec^=avc1" in selector
        assert "acodec^=mp4a" in selector

    def test_fast_with_height(self) -> None:
        selector = build_format_selector("720", "fast")
        assert "height<=720" in selector
        assert "vcodec^=avc1" in selector

    @pytest.mark.parametrize("quality", ["best", "2160", "1080", "720", "480", "360"])
    @pytest.mark.parametrize("mode", ["fast", "normal", "hq"])
    def test_combinations_return_non_empty_string(self, quality: str, mode: str) -> None:
        selector = build_format_selector(quality, mode)
        assert isinstance(selector, str)
        assert len(selector) > 0
