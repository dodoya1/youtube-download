"""YouTube URL の種別判定とチャンネル名抽出ロジック。"""

import re

_CHANNEL_PATTERNS = (
    r"youtube\.com/@([\w\-]+)",
    r"youtube\.com/channel/([\w\-]+)",
    r"youtube\.com/c/([\w\-]+)",
    r"youtube\.com/user/([\w\-]+)",
)


def detect_url_type(url: str) -> str:
    """YouTube URL の種別を判定する。

    Args:
        url: YouTube URL。

    Returns:
        "channel" / "playlist" / "video" のいずれか。
    """
    if any(re.search(p, url) for p in _CHANNEL_PATTERNS):
        return "channel"
    if re.search(r"youtube\.com/playlist\?list=", url):
        return "playlist"
    return "video"


def extract_channel_name(url: str) -> str:
    """チャンネル URL からディレクトリ名に使う識別子を抽出する。

    Args:
        url: YouTube チャンネル URL。

    Returns:
        チャンネル識別子 (``@username`` の ``username`` 部分等)。マッチしない場合は
        ``"unknown_channel"``。
    """
    for pattern in _CHANNEL_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return "unknown_channel"
