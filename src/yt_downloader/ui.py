"""ターミナル表示用のユーティリティ関数群。

色付け、各ログレベルの出力、秒数フォーマットなど、画面表示に関わる
汎用処理をまとめる。外部依存なし。
"""

import sys

from yt_downloader.config import COLORS


def c(text: str, *keys: str) -> str:
    """ANSIカラーコードを付与した文字列を返す。

    標準出力が TTY でない場合 (パイプやリダイレクト) はカラーコードを付与しない。

    Args:
        text: 色付けしたい文字列。
        *keys: COLORS に定義されたキー名 (複数指定可)。

    Returns:
        カラーコード付きの文字列。非 TTY では text をそのまま返す。
    """
    if not sys.stdout.isatty():
        return text
    prefix = "".join(COLORS[k] for k in keys)
    return f"{prefix}{text}{COLORS['reset']}"


def info(msg: str) -> None:
    """INFO レベルのメッセージを標準出力に表示する。

    Args:
        msg: 表示するメッセージ。
    """
    print(c(f"[INFO]  {msg}", "cyan"))


def ok(msg: str) -> None:
    """成功メッセージを標準出力に表示する。

    Args:
        msg: 表示するメッセージ。
    """
    print(c(f"[OK]    {msg}", "green", "bold"))


def warn(msg: str) -> None:
    """WARNING レベルのメッセージを標準エラー出力に表示する。

    Args:
        msg: 表示するメッセージ。
    """
    print(c(f"[WARN]  {msg}", "yellow"), file=sys.stderr)


def error(msg: str) -> None:
    """ERROR レベルのメッセージを標準エラー出力に表示する。

    Args:
        msg: 表示するメッセージ。
    """
    print(c(f"[ERROR] {msg}", "red", "bold"), file=sys.stderr)


def fmt_seconds(secs: float) -> str:
    """秒数を ``MM:SS`` 形式の文字列に変換する。

    Args:
        secs: 変換する秒数。

    Returns:
        ``MM:SS`` 形式の文字列。
    """
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}"
