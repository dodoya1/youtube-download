"""yt_downloader.config のユニットテスト。"""

from pathlib import Path

from yt_downloader import config


class TestConstants:
    def test_quality_options_include_best_and_common_heights(self) -> None:
        assert "best" in config.QUALITY_OPTIONS
        for h in ("1080", "720", "480"):
            assert h in config.QUALITY_OPTIONS

    def test_format_options(self) -> None:
        assert config.FORMAT_OPTIONS == ["mp4", "mkv", "webm"]

    def test_ffmpeg_crf_is_numeric_string(self) -> None:
        assert config.FFMPEG_CRF.isdigit()

    def test_audio_bitrate_ends_with_k(self) -> None:
        assert config.AUDIO_BITRATE.endswith("k")
        assert config.AUDIO_BITRATE[:-1].isdigit()

    def test_colors_has_required_keys(self) -> None:
        for key in ("green", "yellow", "red", "cyan", "bold", "reset"):
            assert key in config.COLORS

    def test_spinner_frames_non_empty(self) -> None:
        assert len(config.SPINNER_FRAMES) > 0


class TestPaths:
    def test_output_dir_is_project_root_relative(self) -> None:
        # プロジェクトルート直下の downloads/ を指している
        assert isinstance(config.OUTPUT_DIR, Path)
        assert config.OUTPUT_DIR.name == "downloads"

    def test_archive_dir_is_under_output_dir(self) -> None:
        assert config.ARCHIVE_DIR.parent == config.OUTPUT_DIR
        assert config.ARCHIVE_DIR.name == ".archive"

    def test_twitter_dir_is_under_output_dir(self) -> None:
        assert config.TWITTER_DIR.parent == config.OUTPUT_DIR
        assert config.TWITTER_DIR.name == "twitter"


class TestEncoderPresets:
    def test_all_modes_present(self) -> None:
        assert set(config.ENCODER_PRESETS.keys()) == {"fast", "normal", "hq"}

    def test_fast_is_stream_copy(self) -> None:
        preset = config.ENCODER_PRESETS["fast"]
        assert "-c" in preset
        assert "copy" in preset

    def test_normal_uses_videotoolbox(self) -> None:
        preset = config.ENCODER_PRESETS["normal"]
        assert "h264_videotoolbox" in preset
        assert "-allow_sw" in preset

    def test_hq_uses_libx264(self) -> None:
        preset = config.ENCODER_PRESETS["hq"]
        assert "libx264" in preset
        assert config.FFMPEG_CRF in preset

    def test_audio_bitrate_applied_in_reencoding_modes(self) -> None:
        for mode in ("normal", "hq"):
            assert config.AUDIO_BITRATE in config.ENCODER_PRESETS[mode]
