#!/usr/bin/env python3
"""YouTube Downloader エントリーポイント。

`pip install` なしでも `python main.py` で起動できるよう、src レイアウトを
sys.path に追加してから CLI を呼び出す。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from yt_downloader.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
