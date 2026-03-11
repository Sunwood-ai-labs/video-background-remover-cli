from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from video_background_remover_cli.cli import (
    _build_run_timestamp,
    _default_output_name,
    _default_output_root,
    _normalize_animated_output,
    build_parser,
    parse_color,
    parse_size,
    resolve_matanyone_inputs,
    resolve_output_target,
)
from video_background_remover_cli.bg_remover import VideoBackgroundRemover


class ParseColorTests(unittest.TestCase):
    def test_named_color(self) -> None:
        self.assertEqual(parse_color("white"), (255, 255, 255))

    def test_rgb_color(self) -> None:
        self.assertEqual(parse_color("12,34,56"), (12, 34, 56))

    def test_transparent_color(self) -> None:
        self.assertIsNone(parse_color("transparent"))

    def test_invalid_color_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_color("300,0,0")


class ParseSizeTests(unittest.TestCase):
    def test_valid_size(self) -> None:
        self.assertEqual(parse_size("300x300"), (300, 300))

    def test_valid_size_with_uppercase_x_and_spaces(self) -> None:
        self.assertEqual(parse_size(" 640X480 "), (640, 480))

    def test_invalid_size_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_size("300")


class ParserTests(unittest.TestCase):
    def test_parser_accepts_matanyone_backend_options(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "input.mp4",
                "--backend",
                "matanyone",
                "--matanyone-model",
                "MatAnyone 2",
                "--positive-point",
                "320,180",
                "--negative-point",
                "16,16",
            ]
        )

        self.assertEqual(args.backend, "matanyone")
        self.assertEqual(args.matanyone_model, "MatAnyone 2")
        self.assertEqual(args.positive_point, ["320,180"])
        self.assertEqual(args.negative_point, ["16,16"])


class AnimatedOutputTests(unittest.TestCase):
    def test_webp_suffix_is_removed(self) -> None:
        self.assertEqual(_normalize_animated_output("out.webp"), "out")

    def test_non_animated_suffix_is_preserved(self) -> None:
        self.assertEqual(_normalize_animated_output("out.final"), "out.final")


class OutputResolutionTests(unittest.TestCase):
    def test_default_video_output_uses_output_folder(self) -> None:
        self.assertEqual(
            resolve_output_target(
                "clips/input.mov",
                None,
                run_timestamp="20260309_010203",
            ),
            str(Path("output") / "input_20260309_010203" / "input_bg_removed.mov"),
        )

    def test_default_animated_output_uses_output_folder(self) -> None:
        self.assertEqual(
            resolve_output_target(
                "clips/input.mov",
                None,
                animated="webp",
                run_timestamp="20260309_010203",
            ),
            str(Path("output") / "input_20260309_010203" / "input_animated"),
        )

    def test_default_interval_output_uses_output_folder(self) -> None:
        self.assertEqual(
            resolve_output_target(
                "clips/input.mov",
                None,
                interval=1.0,
                run_timestamp="20260309_010203",
            ),
            str(Path("output") / "input_20260309_010203" / "input_frames"),
        )

    def test_directory_hint_expands_to_default_video_name(self) -> None:
        self.assertEqual(
            resolve_output_target("clips/input.mov", "exports/"),
            str(Path("exports") / "input_bg_removed.mov"),
        )

    def test_mp4_output_format_forces_mp4_extension(self) -> None:
        self.assertEqual(
            resolve_output_target(
                "clips/input.mov",
                None,
                output_format="mp4",
                run_timestamp="20260309_010203",
            ),
            str(Path("output") / "input_20260309_010203" / "input_bg_removed.mp4"),
        )

    def test_default_output_root_uses_input_stem_folder(self) -> None:
        self.assertEqual(
            _default_output_root("clips/input.mov", run_timestamp="20260309_010203"),
            Path("output") / "input_20260309_010203",
        )

    def test_build_run_timestamp_uses_expected_format(self) -> None:
        self.assertEqual(
            _build_run_timestamp(datetime(2026, 3, 9, 1, 2, 3)),
            "20260309_010203",
        )

    def test_default_output_name_keeps_mp4_fallback(self) -> None:
        self.assertEqual(_default_output_name("clips/input"), "input_bg_removed.mp4")

    def test_matanyone_default_output_name_uses_webp(self) -> None:
        self.assertEqual(
            _default_output_name(
                "assets/MatAnyone/sample_fg.mp4",
                output_format="webp",
                source_mode="matanyone",
            ),
            "sample_transparent.webp",
        )

    def test_matanyone_default_animated_output_name_strips_fg_suffix(self) -> None:
        self.assertEqual(
            _default_output_name(
                "assets/MatAnyone/sample_fg.mp4",
                animated="gif",
                source_mode="matanyone",
            ),
            "sample_transparent_animated",
        )

    def test_matanyone_resolve_output_target_uses_webp_by_default(self) -> None:
        self.assertEqual(
            resolve_output_target(
                "assets/MatAnyone/sample_fg.mp4",
                None,
                output_format="webp",
                run_timestamp="20260309_010203",
                source_mode="matanyone",
            ),
            str(
                Path("output")
                / "sample_fg_20260309_010203"
                / "sample_transparent.webp"
            ),
        )


class MatAnyoneResolutionTests(unittest.TestCase):
    def test_resolve_matanyone_inputs_from_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            fg_path = base / "clip_fg.mp4"
            alpha_path = base / "clip_alpha.mp4"
            fg_path.write_bytes(b"fg")
            alpha_path.write_bytes(b"alpha")

            self.assertEqual(
                resolve_matanyone_inputs(str(base)),
                (str(fg_path), str(alpha_path)),
            )

    def test_resolve_matanyone_inputs_from_fg_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            fg_path = base / "clip_fg.mp4"
            alpha_path = base / "clip_alpha.mp4"
            fg_path.write_bytes(b"fg")
            alpha_path.write_bytes(b"alpha")

            self.assertEqual(
                resolve_matanyone_inputs(str(fg_path)),
                (str(fg_path), str(alpha_path)),
            )


class MatAnyoneCleanupTests(unittest.TestCase):
    def test_combine_matanyone_frames_reduces_green_spill_on_edges(self) -> None:
        remover = VideoBackgroundRemover()
        matte_bgr = np.array([154, 254, 120], dtype=np.uint8)
        fg_frame = np.full((7, 7, 3), matte_bgr, dtype=np.uint8)
        fg_frame[1:6, 1:6] = np.array([120, 210, 135], dtype=np.uint8)
        fg_frame[2:5, 2:5] = np.array([160, 180, 220], dtype=np.uint8)

        alpha_channel = np.zeros((7, 7), dtype=np.uint8)
        alpha_channel[1:6, 1:6] = 200
        alpha_channel[2:5, 2:5] = 255
        alpha_frame = np.dstack([alpha_channel] * 3)

        rgba = remover._combine_matanyone_frames(fg_frame, alpha_frame)
        edge_pixel = rgba[1, 3]
        center_pixel = rgba[3, 3]

        self.assertLessEqual(int(edge_pixel[1]), int(max(edge_pixel[0], edge_pixel[2])) + 10)
        self.assertLess(int(edge_pixel[3]), 200)
        self.assertEqual(int(center_pixel[3]), 255)


if __name__ == "__main__":
    unittest.main()
