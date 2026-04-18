"""定数・設定値・エンコーダープリセットを集約するモジュール。"""

from pathlib import Path

# ── パス定数 ──────────────────────────────────────────────────────────────────
# config.py は src/yt_downloader/ 配下にあるため、プロジェクトルートは3階層上。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = _PROJECT_ROOT / "downloads"
ARCHIVE_DIR = OUTPUT_DIR / ".archive"

# ── 品質・形式の選択肢 ────────────────────────────────────────────────────────
QUALITY_OPTIONS = ["best", "2160", "1440",
                   "1080", "720", "480", "360", "240", "144"]
FORMAT_OPTIONS = ["mp4", "mkv", "webm"]

# ── エンコード設定 ────────────────────────────────────────────────────────────
# libx264 再エンコード時の品質（CRF: 低いほど高品質、18 は視覚的無劣化に近い）
FFMPEG_CRF = "18"

# 音声ビットレート（AAC 再エンコード時）
AUDIO_BITRATE = "256k"

# モードごとの ffmpeg 後処理引数
ENCODER_PRESETS: dict[str, list[str]] = {
    # ストリームコピー: コンテナ詰め替えのみ、数秒で完了
    "fast": ["-c", "copy", "-movflags", "+faststart"],
    # h264_videotoolbox: Apple M1/M2/M3 のハードウェアエンコーダー
    # -q:v 75    : VideoToolbox の品質スケール（高いほど高品質、0〜100）
    # -allow_sw  : ハードウェア制限時にソフトウェアへフォールバック
    "normal": [
        "-c:v", "h264_videotoolbox",
        "-q:v", "75",
        "-allow_sw", "1",
        "-c:a", "aac", "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart",
    ],
    # libx264: ソフトウェアエンコード。最高品質だが M1 でも数十分かかる
    # -crf 18       : 視覚的無劣化に近い高品質（0=無劣化 〜 51=最低）
    # -preset medium: slow と比較して 30-40% 高速、品質差はほぼ知覚不能
    "hq": [
        "-c:v", "libx264", "-crf", FFMPEG_CRF, "-preset", "medium",
        "-c:a", "aac", "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart",
    ],
}

# ── 表示用定数 ────────────────────────────────────────────────────────────────
COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
