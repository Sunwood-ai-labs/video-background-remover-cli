from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from video_background_remover_cli.cli import _normalize_animated_output, parse_color


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


class AnimatedOutputTests(unittest.TestCase):
    def test_webp_suffix_is_removed(self) -> None:
        self.assertEqual(_normalize_animated_output("out.webp"), "out")

    def test_non_animated_suffix_is_preserved(self) -> None:
        self.assertEqual(_normalize_animated_output("out.final"), "out.final")


if __name__ == "__main__":
    unittest.main()
