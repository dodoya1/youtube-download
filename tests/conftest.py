"""pytest 共通 fixture。

- non_tty_stdout: sys.stdout.isatty() を False にパッチし、カラーコードを無効化する
- mock_info_dict: yt-dlp の info_dict を模したサンプル辞書
"""

import sys
from collections.abc import Iterator

import pytest


@pytest.fixture
def non_tty_stdout(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """標準出力を非 TTY として扱わせ、ui モジュールのカラーコードを抑制する。"""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False, raising=False)
    yield


@pytest.fixture
def mock_info_dict() -> dict:
    """yt-dlp が progress_hooks に渡す info_dict を模したサンプル。"""
    return {
        "id":          "abc123",
        "title":       "Sample Video",
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
    }
