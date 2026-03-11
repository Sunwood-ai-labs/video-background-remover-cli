"""Bridge helpers for running MatAnyone models from a separate Python runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess


MATANYONE_MODEL_CHOICES = ["MatAnyone 2", "MatAnyone"]
MATANYONE_DEVICE_CHOICES = ["auto", "cpu", "cuda"]
MATANYONE_PROFILE_CHOICES = ["auto", "balanced", "fast", "quality"]
MATANYONE_SAM_MODEL_CHOICES = ["auto", "vit_h", "vit_l", "vit_b"]
DEFAULT_MATANYONE_ROOT = Path(r"D:\Prj\MatAnyone")


@dataclass(frozen=True)
class MatAnyoneRunResult:
    """Resolved output files produced by one MatAnyone CLI run."""

    output_dir: Path
    foreground_path: Path
    alpha_path: Path


def resolve_matanyone_root(explicit_root: str | None = None) -> Path:
    """Resolve the MatAnyone repository path from args, env, or a local default."""
    if explicit_root:
        root = Path(explicit_root)
        if not root.exists():
            raise ValueError(f"MatAnyone repository not found: {root}")
        return root.resolve()

    env_root = os.environ.get("VBR_MATANYONE_ROOT")
    if env_root:
        root = Path(env_root)
        if not root.exists():
            raise ValueError(
                "VBR_MATANYONE_ROOT points to a missing directory: "
                f"{root}"
            )
        return root.resolve()

    if DEFAULT_MATANYONE_ROOT.exists():
        return DEFAULT_MATANYONE_ROOT.resolve()

    raise ValueError(
        "MatAnyone repository not found. Pass --matanyone-root or set "
        "VBR_MATANYONE_ROOT."
    )


def resolve_matanyone_python(
    matanyone_root: Path | None = None,
    explicit_python: str | None = None,
) -> Path:
    """Resolve the Python executable used to launch the MatAnyone package."""
    if explicit_python:
        python_path = Path(explicit_python)
        if not python_path.exists():
            raise ValueError(f"MatAnyone Python executable not found: {python_path}")
        return python_path.resolve()

    env_python = os.environ.get("VBR_MATANYONE_PYTHON")
    if env_python:
        python_path = Path(env_python)
        if not python_path.exists():
            raise ValueError(
                "VBR_MATANYONE_PYTHON points to a missing executable: "
                f"{python_path}"
            )
        return python_path.resolve()

    if matanyone_root is not None:
        default_python = matanyone_root / ".venv" / "Scripts" / "python.exe"
        if default_python.exists():
            return default_python.resolve()

    raise ValueError(
        "MatAnyone Python executable not found. Pass --matanyone-python, set "
        "VBR_MATANYONE_PYTHON, or point --matanyone-root at a repo with a .venv."
    )


@dataclass
class MatAnyoneRunner:
    """Run MatAnyone by importing `matanyone2` inside the target Python runtime."""

    repo_root: Path
    python_executable: Path
    device: str = "auto"
    model_name: str = "MatAnyone 2"
    performance_profile: str = "auto"
    sam_model_type: str = "auto"
    cpu_threads: int | None = None
    frame_limit: int | None = None
    video_target_fps: float | None = 0.0
    output_fps: float | None = None
    select_frame: int = 0
    end_frame: int | None = None
    positive_points: list[str] = field(default_factory=list)
    negative_points: list[str] = field(default_factory=list)

    def resolve_device(self) -> str:
        """Resolve 'auto' by asking the MatAnyone runtime whether CUDA is usable."""
        if self.device != "auto":
            return self.device

        completed = subprocess.run(
            [
                str(self.python_executable),
                "-c",
                "import torch; print('cuda' if torch.cuda.is_available() else 'cpu')",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        device = completed.stdout.strip().lower()
        return device if device in {"cpu", "cuda"} else "cpu"

    def build_payload(self, input_path: str, output_dir: Path) -> dict[str, object]:
        """Build the argument payload passed to the import worker."""
        return {
            "input_path": input_path,
            "device": self.resolve_device(),
            "model": self.model_name,
            "performance_profile": self.performance_profile,
            "sam_model_type": self.sam_model_type,
            "cpu_threads": self.cpu_threads,
            "frame_limit": self.frame_limit,
            "video_target_fps": self.video_target_fps,
            "output_fps": self.output_fps,
            "select_frame": self.select_frame,
            "end_frame": self.end_frame,
            "output_dir": str(output_dir),
            "positive_points": list(self.positive_points),
            "negative_points": list(self.negative_points),
        }

    def run(self, input_path: str, output_dir: str | Path) -> MatAnyoneRunResult:
        """Run MatAnyone via import and return the generated foreground/alpha pair."""
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        payload_path = output_root / "_matanyone_payload.json"
        result_path = output_root / "_matanyone_result.json"
        payload = self.build_payload(input_path, output_root)
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        worker_script = Path(__file__).with_name("matanyone_import_worker.py")
        command = [
            str(self.python_executable),
            str(worker_script),
            str(payload_path),
            str(result_path),
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                "MatAnyone import worker failed. "
                f"Command: {' '.join(command)}\n"
                f"Details: {details}"
            )
        if not result_path.exists():
            raise RuntimeError(
                "MatAnyone import worker finished without writing a result payload."
            )

        result = json.loads(result_path.read_text(encoding="utf-8"))
        return MatAnyoneRunResult(
            output_dir=Path(result["run_output_dir"]),
            foreground_path=Path(result["foreground_path"]),
            alpha_path=Path(result["alpha_path"]),
        )
