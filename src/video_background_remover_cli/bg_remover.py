"""
Background removal module using RMBG-1.4 model.

This uses the same model as Xenova/remove-background-web:
https://huggingface.co/spaces/Xenova/remove-background-web

Process flow:
1. Extract frames from video
2. Remove background from each frame using RMBG-1.4
3. Reconstruct video from processed frames
"""

import os
import shutil
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw
from tqdm import tqdm
from pathlib import Path


class VideoBackgroundRemover:
    """Remove background from video using RMBG-1.4 model."""

    def __init__(self, model_name: str = "isnet-general-use"):
        """Initialize with RMBG-1.4 model.

        Available models:
        - isnet-general-use: General purpose (default, similar to Xenova)
        - u2net: For salient object detection
        - silueta: High quality, slower
        """
        self.model_name = model_name
        self.session = None
        self._rounded_mask_cache: dict[tuple[int, int, int], Image.Image] = {}

    def _get_session(self):
        """Create the rembg session on first use."""
        if self.session is None:
            try:
                from rembg import new_session
            except ImportError as exc:
                raise RuntimeError(
                    "Background removal requires the 'rembg' package. "
                    "Install the CLI dependencies and try again."
                ) from exc
            self.session = new_session(self.model_name)
        return self.session

    def extract_frames(self, video_path: str, output_dir: str) -> list:
        """Extract all frames from video to directory.

        Args:
            video_path: Path to input video
            output_dir: Directory to save frames

        Returns:
            List of frame paths
        """
        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        frame_paths = []
        frame_count = 0

        print(f"Extracting frames to {output_dir}...")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_path = os.path.join(output_dir, f"frame_{frame_count:06d}.png")
            cv2.imwrite(frame_path, frame)
            frame_paths.append(frame_path)
            frame_count += 1

        cap.release()
        print(f"Extracted {frame_count} frames")

        return frame_paths

    def _resize_frame(
        self,
        frame: np.ndarray,
        output_size: tuple[int, int] | None = None,
    ) -> np.ndarray:
        """Resize a frame to the requested output size."""
        if output_size is None:
            return frame

        width, height = output_size
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

    def _normalize_corner_radius(
        self,
        corner_radius: int = 0,
        size: tuple[int, int] | None = None,
    ) -> int:
        """Clamp a corner radius to the valid range for a frame size."""
        if corner_radius < 0:
            raise ValueError("--corner-radius must be 0 or a positive integer.")

        if size is None:
            return corner_radius

        width, height = size
        return min(corner_radius, width // 2, height // 2)

    def _get_rounded_corner_mask(
        self,
        size: tuple[int, int],
        corner_radius: int = 0,
    ) -> Image.Image | None:
        """Build and cache an anti-aliased rounded-rectangle alpha mask."""
        normalized_radius = self._normalize_corner_radius(
            corner_radius,
            size=size,
        )
        if normalized_radius <= 0:
            return None

        width, height = size
        cache_key = (width, height, normalized_radius)
        cached = self._rounded_mask_cache.get(cache_key)
        if cached is not None:
            return cached

        scale = 4
        mask = Image.new("L", (width * scale, height * scale), 0)
        draw = ImageDraw.Draw(mask)
        scaled_radius = normalized_radius * scale
        draw.rounded_rectangle(
            (0, 0, width * scale - 1, height * scale - 1),
            radius=scaled_radius,
            fill=255,
        )
        mask = mask.resize((width, height), Image.Resampling.LANCZOS)
        self._rounded_mask_cache[cache_key] = mask
        return mask

    def _apply_corner_radius(
        self,
        frame: Image.Image,
        corner_radius: int = 0,
    ) -> Image.Image:
        """Apply a transparent rounded-rectangle mask to an RGBA frame."""
        rgba_frame = frame.convert("RGBA")
        mask = self._get_rounded_corner_mask(
            rgba_frame.size,
            corner_radius=corner_radius,
        )
        if mask is None:
            return rgba_frame

        alpha = ImageChops.multiply(rgba_frame.getchannel("A"), mask)
        rounded = rgba_frame.copy()
        rounded.putalpha(alpha)
        return rounded

    def _to_rgba_image(
        self,
        frame: np.ndarray,
        *,
        output_size: tuple[int, int] | None = None,
        remove_background: bool = True,
        corner_radius: int = 0,
    ) -> Image.Image:
        """Convert one video frame into an RGBA PIL image ready for export."""
        frame = self._resize_frame(frame, output_size=output_size)
        if remove_background:
            rgba_frame = Image.fromarray(self.remove_background_from_frame(frame))
        else:
            rgba_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA))

        return self._apply_corner_radius(rgba_frame, corner_radius=corner_radius)

    def _extract_mask_channel(self, mask_frame: np.ndarray) -> np.ndarray:
        """Extract a single alpha channel from a MatAnyone mask frame."""
        if mask_frame.ndim == 2:
            return mask_frame

        if mask_frame.shape[2] == 4:
            return mask_frame[:, :, 3]

        return cv2.cvtColor(mask_frame, cv2.COLOR_BGR2GRAY)

    def _estimate_background_color(
        self,
        fg_frame: np.ndarray,
        alpha_channel: np.ndarray,
    ) -> np.ndarray:
        """Estimate the baked-in background color from transparent mask regions."""
        transparent_pixels = fg_frame[alpha_channel == 0]
        if transparent_pixels.size == 0:
            transparent_pixels = fg_frame[alpha_channel <= 8]
        if transparent_pixels.size == 0:
            return np.array([0.0, 0.0, 0.0], dtype=np.float32)

        return np.median(transparent_pixels, axis=0).astype(np.float32)

    def _decontaminate_foreground(
        self,
        fg_frame: np.ndarray,
        alpha_channel: np.ndarray,
        matte_bgr: np.ndarray | None = None,
    ) -> np.ndarray:
        """Remove baked background color from semi-transparent edge pixels."""
        if matte_bgr is None:
            matte_bgr = self._estimate_background_color(fg_frame, alpha_channel)
        alpha = alpha_channel.astype(np.float32) / 255.0
        alpha_3 = alpha[:, :, None]

        fg_float = fg_frame.astype(np.float32)
        restored = fg_float.copy()
        active_mask = alpha > 0
        if np.any(active_mask):
            safe_alpha = np.clip(alpha_3, 1e-3, 1.0)
            restored = (fg_float - (1.0 - alpha_3) * matte_bgr[None, None, :]) / safe_alpha
            restored = np.clip(restored, 0.0, 255.0)

        restored[alpha <= 0.0] = 0.0
        return restored.astype(np.uint8)

    def _suppress_green_spill(
        self,
        fg_frame: np.ndarray,
        cleaned_fg: np.ndarray,
        alpha_channel: np.ndarray,
        matte_bgr: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Reduce green-screen spill on the MatAnyone edge band."""
        edge_seed = (alpha_channel < 255).astype(np.uint8)
        if not np.any(edge_seed):
            return cleaned_fg, alpha_channel

        edge_band = cv2.dilate(edge_seed, np.ones((3, 3), dtype=np.uint8), iterations=2)
        edge_band = edge_band.astype(bool) & (alpha_channel > 0)
        if not np.any(edge_band):
            return cleaned_fg, alpha_channel

        cleaned_float = cleaned_fg.astype(np.float32)
        source_float = fg_frame.astype(np.float32)
        alpha_float = alpha_channel.astype(np.float32)

        blue = cleaned_float[:, :, 0]
        green = cleaned_float[:, :, 1]
        red = cleaned_float[:, :, 2]
        red_blue_max = np.maximum(red, blue)
        spill = np.clip(green - red_blue_max - 4.0, 0.0, 255.0)

        matte_distance = np.linalg.norm(source_float - matte_bgr[None, None, :], axis=2)
        matte_like = np.clip(1.0 - matte_distance / 90.0, 0.0, 1.0)
        spill_mask = edge_band & ((spill > 0.0) | (matte_like > 0.2))
        if not np.any(spill_mask):
            return cleaned_fg, alpha_channel

        green_limit = (
            0.6 * red_blue_max + 0.2 * red + 0.2 * blue + 10.0
        )
        cleaned_float[:, :, 1][spill_mask] = np.minimum(
            green[spill_mask],
            green_limit[spill_mask],
        )

        boost = spill * 0.45
        cleaned_float[:, :, 2][spill_mask] = np.clip(
            red[spill_mask] + boost[spill_mask],
            0.0,
            255.0,
        )
        cleaned_float[:, :, 0][spill_mask] = np.clip(
            blue[spill_mask] + boost[spill_mask] * 0.2,
            0.0,
            255.0,
        )

        alpha_adjusted = alpha_float.copy()
        alpha_drop = np.clip(
            (spill / 120.0) * 110.0 + matte_like * 70.0,
            0.0,
            180.0,
        )
        alpha_adjusted[spill_mask] = np.clip(
            alpha_adjusted[spill_mask] - alpha_drop[spill_mask],
            0.0,
            255.0,
        )

        return cleaned_float.astype(np.uint8), alpha_adjusted.astype(np.uint8)

    def _combine_matanyone_frames(
        self,
        fg_frame: np.ndarray,
        alpha_frame: np.ndarray,
        output_size: tuple[int, int] | None = None,
    ) -> np.ndarray:
        """Combine MatAnyone foreground and alpha frames into one RGBA frame."""
        fg_frame = self._resize_frame(fg_frame, output_size=output_size)
        alpha_frame = self._resize_frame(alpha_frame, output_size=output_size)

        if fg_frame.shape[:2] != alpha_frame.shape[:2]:
            alpha_frame = cv2.resize(
                alpha_frame,
                (fg_frame.shape[1], fg_frame.shape[0]),
                interpolation=cv2.INTER_AREA,
            )

        alpha_channel = self._extract_mask_channel(alpha_frame)
        matte_bgr = self._estimate_background_color(fg_frame, alpha_channel)
        cleaned_fg = self._decontaminate_foreground(
            fg_frame,
            alpha_channel,
            matte_bgr=matte_bgr,
        )
        cleaned_fg, alpha_channel = self._suppress_green_spill(
            fg_frame,
            cleaned_fg,
            alpha_channel,
            matte_bgr,
        )
        rgba_frame = cv2.cvtColor(cleaned_fg, cv2.COLOR_BGR2RGBA)
        rgba_frame[:, :, 3] = alpha_channel
        rgba_frame[alpha_channel == 0, :3] = 0
        return rgba_frame

    def _open_video_capture(self, video_path: str) -> cv2.VideoCapture:
        """Open a video capture or raise a clear error."""
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        return capture

    def _get_video_background(self, bg_image_path: str | None, size: tuple[int, int]):
        """Load and resize a background image when requested."""
        if not bg_image_path:
            return None

        bg_image = cv2.imread(bg_image_path, cv2.IMREAD_COLOR)
        if bg_image is None:
            raise ValueError(f"Cannot open background image: {bg_image_path}")

        return cv2.resize(bg_image, size, interpolation=cv2.INTER_AREA)

    def _iter_matanyone_frames(
        self,
        fg_video_path: str,
        alpha_video_path: str,
        *,
        target_fps: int | None = None,
        max_frames: int | None = None,
        output_size: tuple[int, int] | None = None,
    ):
        """Yield RGBA frames assembled from MatAnyone foreground and alpha videos."""
        fg_cap = self._open_video_capture(fg_video_path)
        alpha_cap = self._open_video_capture(alpha_video_path)

        fg_fps = fg_cap.get(cv2.CAP_PROP_FPS) or 0.0
        alpha_fps = alpha_cap.get(cv2.CAP_PROP_FPS) or 0.0
        source_fps = fg_fps or alpha_fps
        if source_fps <= 0:
            raise ValueError("Could not determine FPS from the MatAnyone input videos.")

        fg_total_frames = int(fg_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        alpha_total_frames = int(alpha_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_frames = min(fg_total_frames, alpha_total_frames)
        if total_frames <= 0:
            raise ValueError("No frames found in the MatAnyone input videos.")

        if fg_total_frames != alpha_total_frames:
            print(
                "Warning: MatAnyone foreground and alpha videos have different frame counts. "
                f"Using the shorter length ({total_frames} frames)."
            )

        if fg_fps and alpha_fps and abs(fg_fps - alpha_fps) > 0.01:
            print(
                "Warning: MatAnyone foreground and alpha videos have different FPS values. "
                f"Using foreground FPS {fg_fps:.2f}."
            )

        frame_skip = 1
        if target_fps is not None:
            frame_skip = max(1, int(round(source_fps / target_fps)))
        output_fps = source_fps / frame_skip
        duration = total_frames / source_fps

        print(
            f"MatAnyone pair: {total_frames} frames, {source_fps:.2f} fps, {duration:.2f}s"
        )
        if target_fps is not None:
            print(f"Output: {target_fps} fps (skip every {frame_skip} frames)")

        def iterator():
            frame_index = 0
            saved_count = 0
            try:
                with tqdm(total=total_frames, desc="Processing") as pbar:
                    while frame_index < total_frames:
                        fg_ok, fg_frame = fg_cap.read()
                        alpha_ok, alpha_frame = alpha_cap.read()
                        if not fg_ok or not alpha_ok:
                            break

                        if frame_index % frame_skip == 0:
                            rgba_frame = self._combine_matanyone_frames(
                                fg_frame,
                                alpha_frame,
                                output_size=output_size,
                            )
                            yield saved_count, rgba_frame
                            saved_count += 1

                            if max_frames and saved_count >= max_frames:
                                break

                        frame_index += 1
                        pbar.update(1)
            finally:
                fg_cap.release()
                alpha_cap.release()

        return iterator(), output_fps, total_frames

    def _save_matanyone_rgba_frames(
        self,
        fg_video_path: str,
        alpha_video_path: str,
        frames_dir: str,
        *,
        target_fps: int | None = None,
        max_frames: int | None = None,
        output_size: tuple[int, int] | None = None,
    ) -> tuple[list[str], float]:
        """Save MatAnyone RGBA frames as PNGs and return their paths plus output FPS."""
        os.makedirs(frames_dir, exist_ok=True)
        frame_paths = []
        iterator, output_fps, _ = self._iter_matanyone_frames(
            fg_video_path,
            alpha_video_path,
            target_fps=target_fps,
            max_frames=max_frames,
            output_size=output_size,
        )

        for frame_index, rgba_frame in iterator:
            frame_path = os.path.join(frames_dir, f"frame_{frame_index:06d}.png")
            Image.fromarray(rgba_frame).save(frame_path, format="PNG")
            frame_paths.append(frame_path)

        if not frame_paths:
            raise ValueError("No frames extracted from the MatAnyone input videos.")

        return frame_paths, output_fps

    def _load_rgba_frames_as_pil(self, frame_paths: list[str]) -> list[Image.Image]:
        """Load RGBA PNG frames into memory as PIL images."""
        frames: list[Image.Image] = []
        for frame_path in tqdm(frame_paths, desc="Loading frames"):
            with Image.open(frame_path) as frame:
                frames.append(frame.convert("RGBA").copy())
        return frames

    def _get_ffmpeg_executable(self) -> str:
        """Resolve the ffmpeg binary used for transparent WebM export."""
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
        except ImportError as exc:
            raise RuntimeError(
                "Transparent WebM export requires imageio-ffmpeg. "
                "Reinstall the project dependencies and try again."
            ) from exc

        return get_ffmpeg_exe()

    def _encode_png_sequence_to_webm(
        self,
        frames_dir: str,
        output_path: str,
        fps: float,
    ) -> None:
        """Encode RGBA PNG frames into a transparent WebM video."""
        ffmpeg_path = self._get_ffmpeg_executable()
        command = [
            ffmpeg_path,
            "-y",
            "-framerate",
            f"{fps:.6f}",
            "-i",
            os.path.join(frames_dir, "frame_%06d.png"),
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            "-b:v",
            "0",
            "-crf",
            "18",
            output_path,
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise RuntimeError(
                "ffmpeg failed while creating the transparent WebM output. "
                f"Details: {stderr}"
            ) from exc

    def _write_matanyone_mp4(
        self,
        fg_video_path: str,
        alpha_video_path: str,
        output_path: str,
        fps: int | None = None,
        bg_color: tuple | None = None,
        bg_image_path: str | None = None,
        output_size: tuple[int, int] | None = None,
    ) -> None:
        """Write a regular MP4 by compositing MatAnyone alpha onto a visible background."""
        iterator, output_fps, _ = self._iter_matanyone_frames(
            fg_video_path,
            alpha_video_path,
            target_fps=fps,
            output_size=output_size,
        )

        writer = None
        background_image = None

        for _, rgba_frame in iterator:
            if writer is None:
                height, width = rgba_frame.shape[:2]
                background_image = self._get_video_background(
                    bg_image_path,
                    (width, height),
                )
                writer_fps = fps or output_fps
                writer = cv2.VideoWriter(
                    output_path,
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    writer_fps,
                    (width, height),
                )
                if not writer.isOpened():
                    raise ValueError(f"Cannot create MP4 output: {output_path}")
                if bg_color is None and bg_image_path is None:
                    print(
                        "MP4 does not preserve alpha transparency. "
                        "Compositing transparent pixels onto a black background."
                    )

            if background_image is not None:
                bgr_frame = self._apply_background_image(rgba_frame, background_image)
            else:
                bgr_frame = self._apply_background_color(rgba_frame, bg_color or (0, 0, 0))
            writer.write(bgr_frame)

        if writer is None:
            raise ValueError("No frames extracted from the MatAnyone input videos.")

        writer.release()
        print(f"Video saved to {output_path}")

    def remove_background_from_frame(
        self, frame_input, output_path: str = None
    ) -> np.ndarray:
        """Remove background from a single frame using RMBG-1.4.

        Args:
            frame_input: Frame path (str) or numpy array (BGR format)
            output_path: Optional path to save result

        Returns:
            Frame with background removed (RGBA format)
        """
        if isinstance(frame_input, str):
            # Load from file
            pil_image = Image.open(frame_input).convert("RGB")
        else:
            # Convert numpy array (BGR) to PIL Image (RGB)
            rgb_frame = cv2.cvtColor(frame_input, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)

        # Remove background using RMBG-1.4
        try:
            from rembg import remove
        except ImportError as exc:
            raise RuntimeError(
                "Background removal requires the 'rembg' package. "
                "Install the CLI dependencies and try again."
            ) from exc
        output = remove(pil_image, session=self._get_session())

        # Save if output path provided
        if output_path:
            output.save(output_path)

        return np.array(output)

    def process_frames_batch(
        self,
        input_dir: str,
        output_dir: str,
        bg_color: tuple = None,
        bg_image_path: str = None,
    ) -> list:
        """Process all frames in a directory.

        Args:
            input_dir: Directory containing input frames
            output_dir: Directory to save processed frames
            bg_color: Background color as RGB tuple
            bg_image_path: Path to background image

        Returns:
            List of processed frame paths
        """
        os.makedirs(output_dir, exist_ok=True)

        # Get all frame files
        frame_files = sorted(Path(input_dir).glob("frame_*.png"))
        if not frame_files:
            frame_files = sorted(Path(input_dir).glob("*.png"))

        if not frame_files:
            raise ValueError(f"No frames found in {input_dir}")

        # Load background image if provided
        bg_image = None
        if bg_image_path:
            sample = cv2.imread(str(frame_files[0]))
            height, width = sample.shape[:2]
            bg_image = cv2.imread(bg_image_path)
            bg_image = cv2.resize(bg_image, (width, height))

        print(f"Processing {len(frame_files)} frames...")

        output_paths = []
        for frame_path in tqdm(frame_files, desc="Removing background"):
            # Remove background
            result = self.remove_background_from_frame(str(frame_path))

            # Apply background if specified
            if bg_image is not None:
                result = self._apply_background_image(result, bg_image)
            elif bg_color is not None:
                result = self._apply_background_color(result, bg_color)
            else:
                # Keep as RGBA, convert to BGRA for saving
                result = cv2.cvtColor(result, cv2.COLOR_RGBA2BGRA)

            # Save processed frame
            output_path = os.path.join(output_dir, frame_path.name)
            cv2.imwrite(output_path, result)
            output_paths.append(output_path)

        print(f"Processed frames saved to {output_dir}")
        return output_paths

    def frames_to_video(
        self,
        frames_dir: str,
        output_path: str,
        fps: int = 30,
        codec: str = "mp4v",
    ):
        """Reconstruct video from frames.

        Args:
            frames_dir: Directory containing frames
            output_path: Output video path
            fps: Frames per second
            codec: Video codec (mp4v, avc1, etc.)
        """
        frame_files = sorted(Path(frames_dir).glob("frame_*.png"))
        if not frame_files:
            frame_files = sorted(Path(frames_dir).glob("*.png"))

        if not frame_files:
            raise ValueError(f"No frames found in {frames_dir}")

        # Read first frame to get dimensions
        first_frame = cv2.imread(str(frame_files[0]))
        height, width = first_frame.shape[:2]

        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*codec)
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        print(f"Creating video from {len(frame_files)} frames...")

        for frame_path in tqdm(frame_files, desc="Writing video"):
            frame = cv2.imread(str(frame_path))
            out.write(frame)

        out.release()
        print(f"Video saved to {output_path}")

    def to_animated_webp(
        self,
        video_path: str,
        output_path: str,
        fps: int = 10,
        max_frames: int = None,
        output_size: tuple[int, int] | None = None,
        remove_background: bool = True,
        corner_radius: int = 0,
    ):
        """Convert video to animated WebP (like GIF but better quality).

        Args:
            video_path: Input video path
            output_path: Output WebP path
            fps: Output FPS (lower = smaller file, default: 10)
            max_frames: Maximum number of frames (optional)
        """
        self._normalize_corner_radius(corner_radius)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps

        # Calculate frame skip
        frame_skip = max(1, int(video_fps / fps))
        output_fps = video_fps / frame_skip

        print(f"Video: {total_frames} frames, {video_fps:.2f} fps, {duration:.2f}s")
        print(f"Output: {fps} fps (skip every {frame_skip} frames)")

        frames = []
        frame_count = 0
        frames_output_dir = self._prepare_animation_frames_dir(output_path)
        print(f"Saving processed frames to {frames_output_dir}")

        with tqdm(total=total_frames, desc="Processing") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % frame_skip == 0:
                    result_pil = self._to_rgba_image(
                        frame,
                        output_size=output_size,
                        remove_background=remove_background,
                        corner_radius=corner_radius,
                    )
                    frames.append(result_pil)
                    result_pil.save(
                        os.path.join(frames_output_dir, f"frame_{len(frames)-1:04d}.png"),
                        format="PNG",
                    )

                    if max_frames and len(frames) >= max_frames:
                        break

                frame_count += 1
                pbar.update(1)

        cap.release()

        if not frames:
            raise ValueError("No frames extracted")

        # Calculate duration per frame in milliseconds
        duration_ms = int(1000 / output_fps)

        # Save as animated WebP
        print(f"Saving {len(frames)} frames as animated WebP...")
        frames[0].save(
            output_path,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,  # 0 = infinite loop
            lossless=False,
            quality=85,
        )

        print(f"Animated WebP saved to {output_path}")

    def _prepare_animation_frames_dir(self, output_path: str) -> str:
        """Create a persistent directory for processed animation frames."""
        output_root, _ = os.path.splitext(output_path)
        frames_output_dir = f"{output_root}_frames"
        if os.path.exists(frames_output_dir):
            shutil.rmtree(frames_output_dir)
        os.makedirs(frames_output_dir, exist_ok=True)
        return frames_output_dir

    def _build_gif_master_palette(
        self,
        frames: list[Image.Image],
        transparent_rgb: tuple[int, int, int],
        matte_rgb: tuple[int, int, int],
    ) -> list[int]:
        """Build a shared GIF palette with index 0 reserved for transparency."""
        sample_count = min(16, len(frames))
        sample_indices = np.linspace(0, len(frames) - 1, sample_count, dtype=int)

        sample_width = max(1, min(frames[0].width, 128))
        sample_height = max(1, min(frames[0].height, 128))
        columns = min(4, sample_count)
        rows = int(np.ceil(sample_count / columns))

        palette_sheet = Image.new(
            "RGB", (columns * sample_width, rows * sample_height), matte_rgb
        )
        matte_rgba = matte_rgb + (255,)

        for sheet_index, frame_index in enumerate(sample_indices):
            row = sheet_index // columns
            col = sheet_index % columns

            composited = Image.alpha_composite(
                Image.new("RGBA", frames[frame_index].size, matte_rgba),
                frames[frame_index],
            ).convert("RGB")
            composited = composited.resize((sample_width, sample_height))
            palette_sheet.paste(composited, (col * sample_width, row * sample_height))

        palette_source = palette_sheet.quantize(colors=255, dither=Image.Dither.NONE)
        source_palette = palette_source.getpalette()[: 255 * 3]

        master_palette = list(transparent_rgb)
        master_palette.extend(source_palette)
        master_palette.extend([0] * (768 - len(master_palette)))
        return master_palette[:768]

    def _convert_rgba_frames_to_gif(
        self,
        frames: list[Image.Image],
        matte_rgb: tuple[int, int, int] = (0, 0, 0),
        transparent_rgb: tuple[int, int, int] = (255, 0, 255),
        alpha_threshold: int = 8,
    ) -> list[Image.Image]:
        """Convert RGBA frames into palette GIF frames with a stable transparent index."""
        master_palette = self._build_gif_master_palette(
            frames, transparent_rgb=transparent_rgb, matte_rgb=matte_rgb
        )
        palette_image = Image.new("P", (1, 1))
        palette_image.putpalette(master_palette)

        matte_rgba = matte_rgb + (255,)
        palette_array = np.array(master_palette, dtype=np.int16).reshape(256, 3)
        opaque_palette = palette_array[1:]

        gif_frames = []
        for frame in frames:
            alpha = np.array(frame.getchannel("A"), dtype=np.uint8)
            transparent_mask = alpha <= alpha_threshold

            composited = Image.alpha_composite(
                Image.new("RGBA", frame.size, matte_rgba), frame
            ).convert("RGB")
            quantized = composited.quantize(
                palette=palette_image, dither=Image.Dither.NONE
            )

            frame_indices = np.array(quantized, dtype=np.uint8)
            frame_indices[transparent_mask] = 0

            # Reassign any opaque pixels that accidentally landed on the transparent index.
            opaque_zero_mask = (~transparent_mask) & (frame_indices == 0)
            if np.any(opaque_zero_mask):
                rgb_pixels = np.array(composited, dtype=np.uint8)[opaque_zero_mask]
                unique_colors, inverse = np.unique(
                    rgb_pixels.reshape(-1, 3), axis=0, return_inverse=True
                )
                distances = (
                    (
                        unique_colors[:, None, :].astype(np.int32)
                        - opaque_palette[None, :, :].astype(np.int32)
                    )
                    ** 2
                ).sum(axis=2)
                nearest_palette_indices = (
                    np.argmin(distances, axis=1).astype(np.uint8) + 1
                )
                frame_indices[opaque_zero_mask] = nearest_palette_indices[inverse]

            gif_frame = Image.fromarray(frame_indices, mode="P")
            gif_frame.putpalette(master_palette)
            gif_frame.info["transparency"] = 0
            gif_frame.info["disposal"] = 2
            gif_frames.append(gif_frame)

        return gif_frames

    def _convert_rgba_frame_to_gif(
        self,
        frame: Image.Image,
        master_palette: list[int],
        palette_image: Image.Image,
        matte_rgb: tuple[int, int, int] = (0, 0, 0),
        alpha_threshold: int = 8,
    ) -> Image.Image:
        """Convert one RGBA frame into a palette GIF frame."""
        matte_rgba = matte_rgb + (255,)
        palette_array = np.array(master_palette, dtype=np.int16).reshape(256, 3)
        opaque_palette = palette_array[1:]

        alpha = np.array(frame.getchannel("A"), dtype=np.uint8)
        transparent_mask = alpha <= alpha_threshold

        composited = Image.alpha_composite(
            Image.new("RGBA", frame.size, matte_rgba), frame
        ).convert("RGB")
        quantized = composited.quantize(
            palette=palette_image, dither=Image.Dither.NONE
        )

        frame_indices = np.array(quantized, dtype=np.uint8)
        frame_indices[transparent_mask] = 0

        # Reassign any opaque pixels that accidentally landed on the transparent index.
        opaque_zero_mask = (~transparent_mask) & (frame_indices == 0)
        if np.any(opaque_zero_mask):
            rgb_pixels = np.array(composited, dtype=np.uint8)[opaque_zero_mask]
            unique_colors, inverse = np.unique(
                rgb_pixels.reshape(-1, 3), axis=0, return_inverse=True
            )
            distances = (
                (
                    unique_colors[:, None, :].astype(np.int32)
                    - opaque_palette[None, :, :].astype(np.int32)
                )
                ** 2
            ).sum(axis=2)
            nearest_palette_indices = (
                np.argmin(distances, axis=1).astype(np.uint8) + 1
            )
            frame_indices[opaque_zero_mask] = nearest_palette_indices[inverse]

        gif_frame = Image.fromarray(frame_indices, mode="P")
        gif_frame.putpalette(master_palette)
        gif_frame.info["transparency"] = 0
        gif_frame.info["disposal"] = 2
        return gif_frame

    def _save_animated_gif(
        self,
        frames: list[Image.Image],
        output_path: str,
        duration_ms: int,
    ):
        """Save frames as animated GIF using a dedicated pipeline."""
        gif_frames = self._convert_rgba_frames_to_gif(frames)
        gif_frames[0].save(
            output_path,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration_ms,
            loop=0,
            transparency=0,
            disposal=2,
            optimize=False,
        )

        print(f"Animated GIF saved to {output_path}")

    def to_animated_gif(
        self,
        video_path: str,
        output_path: str,
        fps: int = 10,
        max_frames: int = None,
        output_size: tuple[int, int] | None = None,
        remove_background: bool = True,
        corner_radius: int = 0,
    ):
        """Convert video to animated GIF with a GIF-specific low-memory pipeline."""
        self._normalize_corner_radius(corner_radius)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps

        frame_skip = max(1, int(video_fps / fps))
        output_fps = video_fps / frame_skip
        duration_ms = int(1000 / output_fps)

        print(f"Video: {total_frames} frames, {video_fps:.2f} fps, {duration:.2f}s")
        print(f"Output: {fps} fps (skip every {frame_skip} frames)")

        temp_paths = []
        frames_output_dir = self._prepare_animation_frames_dir(output_path)
        print(f"Saving processed frames to {frames_output_dir}")

        frame_count = 0
        saved_count = 0

        with tqdm(total=total_frames, desc="Processing") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % frame_skip == 0:
                    result = self._to_rgba_image(
                        frame,
                        output_size=output_size,
                        remove_background=remove_background,
                        corner_radius=corner_radius,
                    )
                    frame_path = os.path.join(frames_output_dir, f"frame_{saved_count:04d}.png")
                    result.save(frame_path, format="PNG")
                    temp_paths.append(frame_path)
                    saved_count += 1

                    if max_frames and saved_count >= max_frames:
                        break

                frame_count += 1
                pbar.update(1)

        cap.release()

        if not temp_paths:
            raise ValueError("No frames extracted")

        print(f"Saving {len(temp_paths)} frames as animated GIF...")

        sample_count = min(16, len(temp_paths))
        sample_indices = np.linspace(0, len(temp_paths) - 1, sample_count, dtype=int)
        sample_frames = []
        for frame_index in tqdm(
            sample_indices,
            desc="Loading GIF palette samples",
            total=sample_count,
        ):
            with Image.open(temp_paths[frame_index]) as sample_frame:
                sample_frames.append(sample_frame.convert("RGBA"))

        master_palette = self._build_gif_master_palette(
            sample_frames,
            transparent_rgb=(255, 0, 255),
            matte_rgb=(0, 0, 0),
        )
        palette_image = Image.new("P", (1, 1))
        palette_image.putpalette(master_palette)

        gif_frames = []
        for frame_path in tqdm(
            temp_paths,
            desc="Converting GIF frames",
            total=len(temp_paths),
        ):
            with Image.open(frame_path) as rgba_frame:
                gif_frames.append(
                    self._convert_rgba_frame_to_gif(
                        rgba_frame.convert("RGBA"),
                        master_palette=master_palette,
                        palette_image=palette_image,
                        matte_rgb=(0, 0, 0),
                    )
                )

        gif_frames[0].save(
            output_path,
            format="GIF",
            save_all=True,
            append_images=gif_frames[1:],
            duration=duration_ms,
            loop=0,
            transparency=0,
            disposal=2,
            optimize=False,
        )

        print(f"Animated GIF saved to {output_path}")

    def to_animated(
        self,
        video_path: str,
        output_path: str,
        fps: int = 10,
        max_frames: int = None,
        format: str = "webp",
        output_size: tuple[int, int] | None = None,
        remove_background: bool = True,
        corner_radius: int = 0,
    ):
        """Convert video to animated WebP or GIF.

        Args:
            video_path: Input video path
            output_path: Output path
            fps: Output FPS (lower = smaller file, default: 10)
            max_frames: Maximum number of frames (optional)
            format: Output format - "webp" or "gif"
        """
        if format == "gif":
            self.to_animated_gif(
                video_path=video_path,
                output_path=output_path,
                fps=fps,
                max_frames=max_frames,
                output_size=output_size,
                remove_background=remove_background,
                corner_radius=corner_radius,
            )
            return

        self._normalize_corner_radius(corner_radius)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps

        # Calculate frame skip
        frame_skip = max(1, int(video_fps / fps))
        output_fps = video_fps / frame_skip

        print(f"Video: {total_frames} frames, {video_fps:.2f} fps, {duration:.2f}s")
        print(f"Output: {fps} fps (skip every {frame_skip} frames)")

        frames = []
        frame_count = 0
        frames_output_dir = self._prepare_animation_frames_dir(output_path)
        print(f"Saving processed frames to {frames_output_dir}")

        with tqdm(total=total_frames, desc="Processing") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % frame_skip == 0:
                    result_pil = self._to_rgba_image(
                        frame,
                        output_size=output_size,
                        remove_background=remove_background,
                        corner_radius=corner_radius,
                    )

                    frames.append(result_pil)
                    result_pil.save(
                        os.path.join(frames_output_dir, f"frame_{len(frames)-1:04d}.png"),
                        format="PNG",
                    )

                    if max_frames and len(frames) >= max_frames:
                        break

                frame_count += 1
                pbar.update(1)

        cap.release()

        if not frames:
            raise ValueError("No frames extracted")

        # Calculate duration per frame in milliseconds
        duration_ms = int(1000 / output_fps)

        # Save as animated format
        format_upper = format.upper()
        print(f"Saving {len(frames)} frames as animated {format_upper}...")

        if format == "webp":
            frames[0].save(
                output_path,
                format=format_upper,
                save_all=True,
                append_images=frames[1:],
                duration=duration_ms,
                loop=0,  # 0 = infinite loop
                lossless=False,
                quality=85,
            )
            print(f"Animated {format_upper} saved to {output_path}")

    def to_animated_from_mask_pair(
        self,
        fg_video_path: str,
        alpha_video_path: str,
        output_path: str,
        fps: int = 10,
        max_frames: int = None,
        format: str = "webp",
        output_size: tuple[int, int] | None = None,
        corner_radius: int = 0,
        bounce: bool = False,
    ) -> None:
        """Convert a MatAnyone foreground+alpha pair into animated WebP or GIF.

        Args:
            bounce: If True, add reversed frames at the end for ping-pong loop effect.
        """
        self._normalize_corner_radius(corner_radius)
        frames_output_dir = self._prepare_animation_frames_dir(output_path)
        print(f"Saving processed frames to {frames_output_dir}")
        frame_paths, output_fps = self._save_matanyone_rgba_frames(
            fg_video_path,
            alpha_video_path,
            frames_output_dir,
            target_fps=fps,
            max_frames=max_frames,
            output_size=output_size,
        )
        frames = [
            self._apply_corner_radius(frame, corner_radius=corner_radius)
            for frame in self._load_rgba_frames_as_pil(frame_paths)
        ]

        # Add bounce effect (ping-pong loop)
        if bounce and len(frames) > 1:
            print(f"Adding bounce effect (ping-pong loop)...")
            frames = frames + frames[-2:0:-1]  # Reverse excluding first and last
            print(f"Total frames after bounce: {len(frames)}")

        duration_ms = int(1000 / output_fps)
        format_upper = format.upper()
        print(f"Saving {len(frames)} frames as animated {format_upper}...")

        if format == "gif":
            self._save_animated_gif(
                frames,
                output_path,
                duration_ms=duration_ms,
            )
            return

        frames[0].save(
            output_path,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            lossless=False,
            quality=85,
        )
        print(f"Animated {format_upper} saved to {output_path}")

    def extract_matanyone_frames_interval(
        self,
        fg_video_path: str,
        alpha_video_path: str,
        output_dir: str,
        interval_sec: float = 1.0,
        format: str = "webp",
        output_size: tuple[int, int] | None = None,
        corner_radius: int = 0,
    ) -> list[str]:
        """Extract transparent frames from a MatAnyone pair at a fixed interval."""
        self._normalize_corner_radius(corner_radius)
        fg_cap = self._open_video_capture(fg_video_path)
        alpha_cap = self._open_video_capture(alpha_video_path)
        os.makedirs(output_dir, exist_ok=True)

        fps = fg_cap.get(cv2.CAP_PROP_FPS) or alpha_cap.get(cv2.CAP_PROP_FPS)
        total_frames = min(
            int(fg_cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            int(alpha_cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        )
        if fps <= 0:
            raise ValueError("Could not determine FPS from the MatAnyone input videos.")

        duration = total_frames / fps
        frame_interval = max(1, int(round(fps * interval_sec)))

        print(f"MatAnyone pair: {total_frames} frames, {fps:.2f} fps, {duration:.2f}s")
        print(f"Extracting every {interval_sec}s (every {frame_interval} frames)")

        output_paths = []
        frame_count = 0
        saved_count = 0

        try:
            with tqdm(total=total_frames, desc="Processing") as pbar:
                while frame_count < total_frames:
                    fg_ok, fg_frame = fg_cap.read()
                    alpha_ok, alpha_frame = alpha_cap.read()
                    if not fg_ok or not alpha_ok:
                        break

                    if frame_count % frame_interval == 0:
                        timestamp = frame_count / fps
                        rgba_frame = self._combine_matanyone_frames(
                            fg_frame,
                            alpha_frame,
                            output_size=output_size,
                        )
                        rgba_image = self._apply_corner_radius(
                            Image.fromarray(rgba_frame),
                            corner_radius=corner_radius,
                        )
                        output_path = os.path.join(
                            output_dir,
                            f"frame_{saved_count:04d}_t{timestamp:.1f}s.{format}",
                        )
                        rgba_image.save(output_path, format=format.upper())
                        output_paths.append(output_path)
                        saved_count += 1

                    frame_count += 1
                    pbar.update(1)
        finally:
            fg_cap.release()
            alpha_cap.release()

        print(f"\nSaved {saved_count} frames to {output_dir}")
        return output_paths

    def process_matanyone_video(
        self,
        fg_video_path: str,
        alpha_video_path: str,
        output_path: str,
        fps: int = None,
        bg_color: tuple = None,
        bg_image_path: str = None,
        keep_frames: bool = False,
        work_dir: str = None,
        output_size: tuple[int, int] | None = None,
    ) -> None:
        """Convert a MatAnyone foreground+alpha pair into transparent WebM or flattened MP4."""
        output_suffix = Path(output_path).suffix.lower()

        if output_suffix == ".webm":
            if work_dir is None:
                work_dir = os.path.join(os.path.dirname(output_path), "matanyone_frames")

            try:
                print("\n[Step 1/2] Rendering RGBA frames from MatAnyone pair...")
                frame_paths, output_fps = self._save_matanyone_rgba_frames(
                    fg_video_path,
                    alpha_video_path,
                    work_dir,
                    target_fps=fps,
                    output_size=output_size,
                )

                print("\n[Step 2/2] Encoding transparent WebM...")
                self._encode_png_sequence_to_webm(
                    work_dir,
                    output_path,
                    fps=fps or output_fps,
                )
                print(f"\nDone! Output saved to: {output_path}")
            finally:
                if not keep_frames and work_dir and os.path.exists(work_dir):
                    print("Cleaning up temporary frames...")
                    shutil.rmtree(work_dir)
            return

        if output_suffix != ".mp4":
            raise ValueError(
                "MatAnyone regular video export currently supports only .webm or .mp4 output."
            )

        self._write_matanyone_mp4(
            fg_video_path=fg_video_path,
            alpha_video_path=alpha_video_path,
            output_path=output_path,
            fps=fps,
            bg_color=bg_color,
            bg_image_path=bg_image_path,
            output_size=output_size,
        )
        print(f"\nDone! Output saved to: {output_path}")

    def process_video(
        self,
        input_path: str,
        output_path: str,
        fps: int = None,
        bg_color: tuple = None,
        bg_image_path: str = None,
        keep_frames: bool = False,
        work_dir: str = None,
        output_size: tuple[int, int] | None = None,
    ):
        """Full pipeline: video -> frames -> remove bg -> video.

        Args:
            input_path: Input video path
            output_path: Output video path
            fps: Output FPS (default: same as input)
            bg_color: Background color as RGB tuple
            bg_image_path: Path to background image
            keep_frames: Keep intermediate frames
            work_dir: Working directory for frames
        """
        # Setup working directory
        if work_dir is None:
            work_dir = os.path.join(os.path.dirname(output_path), "frames_temp")

        input_frames_dir = os.path.join(work_dir, "input")
        output_frames_dir = os.path.join(work_dir, "output")

        try:
            # Get video FPS
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                raise ValueError(f"Cannot open video: {input_path}")
            video_fps = int(cap.get(cv2.CAP_PROP_FPS))
            cap.release()

            if fps is None:
                fps = video_fps

            # Step 1: Extract frames
            print("\n[Step 1/3] Extracting frames from video...")
            frame_paths = self.extract_frames(input_path, input_frames_dir)
            if output_size is not None:
                print(
                    "Resizing extracted frames "
                    f"to {output_size[0]}x{output_size[1]}..."
                )
                for frame_path in tqdm(frame_paths, desc="Resizing frames"):
                    frame = cv2.imread(frame_path, cv2.IMREAD_UNCHANGED)
                    resized = self._resize_frame(frame, output_size=output_size)
                    cv2.imwrite(frame_path, resized)

            # Step 2: Process frames
            print("\n[Step 2/3] Removing background from frames...")
            self.process_frames_batch(
                input_frames_dir,
                output_frames_dir,
                bg_color=bg_color,
                bg_image_path=bg_image_path,
            )

            # Step 3: Reconstruct video
            print("\n[Step 3/3] Reconstructing video...")
            self.frames_to_video(output_frames_dir, output_path, fps=fps)

            print(f"\nDone! Output saved to: {output_path}")

        finally:
            # Cleanup
            if not keep_frames and os.path.exists(work_dir):
                print("Cleaning up temporary frames...")
                shutil.rmtree(work_dir)

    def extract_frames_interval(
        self,
        video_path: str,
        output_dir: str,
        interval_sec: float = 1.0,
        format: str = "webp",
        output_size: tuple[int, int] | None = None,
        remove_background: bool = True,
        corner_radius: int = 0,
    ) -> list:
        """Extract frames at specified interval and remove background.

        Args:
            video_path: Path to input video
            output_dir: Directory to save processed frames
            interval_sec: Interval in seconds (default: 1.0)
            format: Output format (webp, png)

        Returns:
            List of output frame paths
        """
        self._normalize_corner_radius(corner_radius)
        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        # Calculate frame interval
        frame_interval = int(fps * interval_sec)

        print(f"Video: {total_frames} frames, {fps:.2f} fps, {duration:.2f}s")
        print(f"Extracting every {interval_sec}s (every {frame_interval} frames)")

        output_paths = []
        frame_count = 0
        saved_count = 0

        with tqdm(total=total_frames, desc="Processing") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Process only at intervals
                if frame_count % frame_interval == 0:
                    timestamp = frame_count / fps
                    result = self._to_rgba_image(
                        frame,
                        output_size=output_size,
                        remove_background=remove_background,
                        corner_radius=corner_radius,
                    )

                    # Save as webp (supports transparency)
                    output_path = os.path.join(
                        output_dir, f"frame_{saved_count:04d}_t{timestamp:.1f}s.{format}"
                    )

                    # Convert RGBA to PIL and save
                    result.save(output_path, format=format.upper())

                    output_paths.append(output_path)
                    saved_count += 1

                frame_count += 1
                pbar.update(1)

        cap.release()
        print(f"\nSaved {saved_count} frames to {output_dir}")

        return output_paths

    def _apply_background_color(
        self, frame: np.ndarray, color: tuple
    ) -> np.ndarray:
        """Apply solid background color."""
        alpha = frame[:, :, 3:4] / 255.0
        bg = np.array(color, dtype=np.uint8)

        result = frame[:, :, :3] * alpha + bg * (1 - alpha)
        return cv2.cvtColor(result.astype(np.uint8), cv2.COLOR_RGB2BGR)

    def _apply_background_image(
        self, frame: np.ndarray, bg: np.ndarray
    ) -> np.ndarray:
        """Apply background image."""
        alpha = frame[:, :, 3:4] / 255.0
        bg_rgb = cv2.cvtColor(bg, cv2.COLOR_BGR2RGB)

        result = frame[:, :, :3] * alpha + bg_rgb * (1 - alpha)
        return cv2.cvtColor(result.astype(np.uint8), cv2.COLOR_RGB2BGR)
