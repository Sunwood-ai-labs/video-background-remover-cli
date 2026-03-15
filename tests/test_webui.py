import json
from pathlib import Path
import os
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from video_background_remover_cli.webui import (
    INTERNAL_LAUNCH_FLAG,
    _build_advanced_rembg_examples,
    _build_output_path_placeholder,
    _build_preview_sections_html,
    _build_resize_ratio_text,
    _build_video_info_text,
    _build_cli_output_target,
    _collect_existing_example_paths,
    _compute_scaled_dimensions,
    _discover_matanyone_run_artifacts,
    _list_detected_tile_resume_run_dirs,
    _parse_points_text,
    _resolve_tile_resume_source,
    _split_frame_sequence_into_tiles,
    _split_size_into_tiles,
    _ui_text,
    build_external_launch_command,
    build_pythonpath,
)
from video_background_remover_cli.background_removal.examples import (
    build_cli_example_cases,
    build_cli_examples_by_mode,
)


class WebUiCommandTests(unittest.TestCase):
    def test_build_external_launch_command_adds_internal_flag(self) -> None:
        command = build_external_launch_command(
            Path(r"C:\Python310\python.exe"),
            ["--port", "9000"],
        )

        self.assertEqual(
            command,
            [
                r"C:\Python310\python.exe",
                "-m",
                "video_background_remover_cli.webui",
                INTERNAL_LAUNCH_FLAG,
                "--port",
                "9000",
            ],
        )

    def test_build_external_launch_command_filters_existing_internal_flag(self) -> None:
        command = build_external_launch_command(
            "python.exe",
            [INTERNAL_LAUNCH_FLAG, "--debug"],
        )

        self.assertEqual(
            command,
            [
                "python.exe",
                "-m",
                "video_background_remover_cli.webui",
                INTERNAL_LAUNCH_FLAG,
                "--debug",
            ],
        )


class PythonPathTests(unittest.TestCase):
    def test_build_pythonpath_prepends_new_paths(self) -> None:
        value = build_pythonpath("existing", "alpha", Path("beta"))

        self.assertEqual(value, os.pathsep.join(["alpha", "beta", "existing"]))

    def test_build_pythonpath_without_existing_value(self) -> None:
        value = build_pythonpath(None, "alpha")

        self.assertEqual(value, "alpha")


class CliHelperTests(unittest.TestCase):
    def test_parse_points_text_accepts_newline_and_semicolon(self) -> None:
        self.assertEqual(
            _parse_points_text("10,20\n30,40;50,60"),
            ["10,20", "30,40", "50,60"],
        )

    def test_parse_points_text_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValueError):
            _parse_points_text("10")

    def test_build_cli_output_target_for_pair_webm(self) -> None:
        target = _build_cli_output_target(
            Path("output") / "case",
            "clip_fg.mp4",
            "matanyone_pair",
            "video",
            "webp",
            "webp",
            "webm",
        )

        self.assertEqual(target, str(Path("output") / "case" / "clip_output.webm"))

    def test_compute_scaled_dimensions_applies_ratio(self) -> None:
        self.assertEqual(_compute_scaled_dimensions(1920, 1080, 0.5), (960, 540))

    def test_build_resize_ratio_text_reports_scaled_size(self) -> None:
        text = _build_resize_ratio_text(
            {"width": 1280, "height": 720},
            0.5,
            "en",
        )

        self.assertEqual(
            text,
            "Resize ratio 0.50 -> 640 x 360 (from 1280 x 720)",
        )

    def test_build_resize_ratio_text_reports_scaled_size_in_japanese(self) -> None:
        text = _build_resize_ratio_text(
            {"width": 1280, "height": 720},
            0.5,
            "ja",
        )

        self.assertEqual(
            text,
            "リサイズ比 0.50 -> 640 x 360 （元: 1280 x 720）",
        )

    def test_build_video_info_text_uses_requested_language(self) -> None:
        text = _build_video_info_text(
            {
                "width": 640,
                "height": 360,
                "frame_count": 24,
                "fps": 12.0,
                "duration": 2.0,
            },
            "en",
        )

        self.assertEqual(
            text,
            "Resolution: 640 x 360\nFrames: 24\nSource FPS: 12.00\nDuration: 2.00s",
        )

    def test_ui_text_falls_back_to_default_language_for_unknown_language(self) -> None:
        self.assertEqual(_ui_text("xx", "app_title"), _ui_text("ja", "app_title"))

    def test_ui_text_exposes_tile_tab_labels(self) -> None:
        self.assertEqual(_ui_text("en", "tab_matanyone2_tile"), "MatAnyone2 Tile")
        self.assertEqual(_ui_text("ja", "tab_matanyone2_tile"), "MatAnyone2 Tile")

    def test_build_output_path_placeholder_uses_requested_folder(self) -> None:
        self.assertEqual(
            _build_output_path_placeholder("advanced_pair", "en"),
            "Leave blank to auto-save under output\\webui\\advanced_pair",
        )

    def test_build_preview_sections_html_renders_both_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            webp_path = Path(tmpdir) / "tile_01_animated.webp"
            gif_path = Path(tmpdir) / "tile_01_animated.gif"
            webp_path.write_bytes(b"webp")
            gif_path.write_bytes(b"gif")

            html = _build_preview_sections_html(
                [
                    ("Animated WebP", [("Animated WebP / Tile 01", str(webp_path))]),
                    ("Animated GIF", [("Animated GIF / Tile 01", str(gif_path))]),
                ]
            )

        self.assertIn("Animated WebP", html)
        self.assertIn("Animated GIF", html)
        self.assertIn("tile_01_animated.webp", html)
        self.assertIn("tile_01_animated.gif", html)

    def test_collect_existing_example_paths_filters_missing_files(self) -> None:
        paths = _collect_existing_example_paths(
            ROOT / "assets" / "star-cat2.mp4",
            ROOT / "assets" / "missing-example.mp4",
        )

        self.assertEqual(paths, [str((ROOT / "assets" / "star-cat2.mp4").resolve())])

    def test_build_advanced_rembg_examples_match_ui_shape(self) -> None:
        examples = _build_advanced_rembg_examples(ROOT)

        self.assertTrue(examples)
        for example in examples:
            self.assertEqual(len(example), 7)
            self.assertTrue(Path(example[1]).exists(), example[1])

    def test_split_size_into_tiles_for_2x2(self) -> None:
        self.assertEqual(
            _split_size_into_tiles((1920, 1080), "2x2"),
            [(960, 540), (960, 540), (960, 540), (960, 540)],
        )

    def test_split_frame_sequence_into_tiles_preserves_tile_order(self) -> None:
        frames = [
            np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3),
            (np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3) + 1) % 255,
        ]

        tiles = _split_frame_sequence_into_tiles(frames, "2x2")

        self.assertEqual(len(tiles), 4)
        for tile_frames in tiles:
            self.assertEqual(len(tile_frames), 2)
            self.assertEqual(tile_frames[0].shape, (2, 3, 3))

        self.assertTrue(np.array_equal(tiles[0][0], frames[0][:2, :3]))
        self.assertTrue(np.array_equal(tiles[1][0], frames[0][:2, 3:]))
        self.assertTrue(np.array_equal(tiles[2][0], frames[0][2:, :3]))
        self.assertTrue(np.array_equal(tiles[3][0], frames[0][2:, 3:]))

    def test_discover_matanyone_run_artifacts_detects_existing_animation_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "clip_animated.webp").write_bytes(b"webp")
            (run_dir / "clip_animated.gif").write_bytes(b"gif")

            artifacts = _discover_matanyone_run_artifacts(str(run_dir))

            self.assertEqual(artifacts["existing_webp"], str(run_dir / "clip_animated.webp"))
            self.assertEqual(artifacts["existing_gif"], str(run_dir / "clip_animated.gif"))

    def test_list_detected_tile_resume_run_dirs_prefers_latest_valid_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results_root = Path(tmpdir)
            video_root = results_root / "matanyone2_video"
            tile_root = results_root / "matanyone2_tile"
            video_root.mkdir()
            tile_root.mkdir()

            older_run = video_root / "older_run"
            older_run.mkdir()
            (older_run / "metadata.json").write_text("{}", encoding="utf-8")
            (older_run / "clip_fg.mp4").write_bytes(b"fg")
            (older_run / "clip_alpha.mp4").write_bytes(b"alpha")

            newer_run = tile_root / "newer_run"
            newer_run.mkdir()
            (newer_run / "metadata.json").write_text("{}", encoding="utf-8")
            (newer_run / "clip_fg.mp4").write_bytes(b"fg")
            (newer_run / "clip_alpha.mp4").write_bytes(b"alpha")

            invalid_run = video_root / "invalid_run"
            invalid_run.mkdir()
            (invalid_run / "metadata.json").write_text("{}", encoding="utf-8")

            os.utime(older_run, (10, 10))
            os.utime(newer_run, (20, 20))
            os.utime(invalid_run, (30, 30))

            detected = _list_detected_tile_resume_run_dirs(results_root)

            self.assertEqual(detected, [str(newer_run.resolve()), str(older_run.resolve())])

    def test_resolve_tile_resume_source_from_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            fg_path = run_dir / "clip_fg.mp4"
            alpha_path = run_dir / "clip_alpha.mp4"
            fg_path.write_bytes(b"fg")
            alpha_path.write_bytes(b"alpha")
            metadata = {
                "source_size": [640, 360],
                "num_output_frames": 24,
                "fps": 12.0,
                "source_name": "clip.mp4",
                "width": 640,
                "height": 360,
            }
            (run_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            (run_dir / "clip_animated.gif").write_bytes(b"gif")

            resolved = _resolve_tile_resume_source(str(run_dir), None, None)

            self.assertEqual(resolved["run_dir"], str(run_dir))
            self.assertEqual(resolved["fg_video_path"], str(fg_path))
            self.assertEqual(resolved["alpha_video_path"], str(alpha_path))
            self.assertEqual(resolved["source_size"], (640, 360))
            self.assertEqual(resolved["metadata"]["width"], 640)
            self.assertEqual(resolved["metadata"]["height"], 360)
            self.assertEqual(resolved["existing_gif"], str(run_dir / "clip_animated.gif"))


class WebUiExampleTests(unittest.TestCase):
    def test_cli_example_cases_point_to_repo_assets(self) -> None:
        examples = build_cli_example_cases(ROOT)

        self.assertTrue(examples)
        for example in examples:
            self.assertTrue(Path(example.manual_input_path).exists(), example.manual_input_path)

    def test_cli_examples_by_mode_match_ui_shapes(self) -> None:
        examples_by_mode = build_cli_examples_by_mode(ROOT)

        self.assertEqual(len(examples_by_mode["regular"][0]), 7)
        self.assertEqual(len(examples_by_mode["matanyone_backend"][0]), 7)
        self.assertEqual(len(examples_by_mode["matanyone_pair"][0]), 9)


if __name__ == "__main__":
    unittest.main()
