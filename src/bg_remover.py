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
import cv2
import numpy as np
from PIL import Image
from rembg import remove, new_session
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
        self.session = new_session(model_name)

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
        output = remove(pil_image, session=self.session)

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
    ):
        """Convert video to animated WebP (like GIF but better quality).

        Args:
            video_path: Input video path
            output_path: Output WebP path
            fps: Output FPS (lower = smaller file, default: 10)
            max_frames: Maximum number of frames (optional)
        """
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

        with tqdm(total=total_frames, desc="Processing") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % frame_skip == 0:
                    # Remove background
                    result = self.remove_background_from_frame(frame)
                    result_pil = Image.fromarray(result)
                    frames.append(result_pil)

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

    def to_animated(
        self,
        video_path: str,
        output_path: str,
        fps: int = 10,
        max_frames: int = None,
        format: str = "webp",
    ):
        """Convert video to animated WebP or GIF.

        Args:
            video_path: Input video path
            output_path: Output path
            fps: Output FPS (lower = smaller file, default: 10)
            max_frames: Maximum number of frames (optional)
            format: Output format - "webp" or "gif"
        """
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

        with tqdm(total=total_frames, desc="Processing") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_count % frame_skip == 0:
                    # Remove background
                    result = self.remove_background_from_frame(frame)
                    result_pil = Image.fromarray(result)

                    # For GIF, properly handle transparency
                    if format == "gif":
                        # Keep RGBA for now, will convert when saving
                        pass

                    frames.append(result_pil)

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

        save_kwargs = {
            "save_all": True,
            "append_images": frames[1:],
            "duration": duration_ms,
            "loop": 0,  # 0 = infinite loop
        }

        if format == "webp":
            save_kwargs["lossless"] = False
            save_kwargs["quality"] = 85
        elif format == "gif":
            # For GIF, convert RGBA frames to P with proper transparency
            gif_frames = []
            for frame in frames:
                # Convert RGBA to P with transparency
                alpha = frame.split()[-1]  # Get alpha channel
                frame_p = frame.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
                # Set transparency based on alpha
                frame_p.info["transparency"] = 0
                gif_frames.append(frame_p)
            frames = gif_frames
            save_kwargs["append_images"] = frames[1:]
            save_kwargs["optimize"] = True
            save_kwargs["disposal"] = 1  # Do Not Dispose - prevents black trails!

        frames[0].save(output_path, format=format_upper, **save_kwargs)

        print(f"Animated {format_upper} saved to {output_path}")

    def process_video(
        self,
        input_path: str,
        output_path: str,
        fps: int = None,
        bg_color: tuple = None,
        bg_image_path: str = None,
        keep_frames: bool = False,
        work_dir: str = None,
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
        import shutil

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
            self.extract_frames(input_path, input_frames_dir)

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

                    # Remove background
                    result = self.remove_background_from_frame(frame)

                    # Save as webp (supports transparency)
                    output_path = os.path.join(
                        output_dir, f"frame_{saved_count:04d}_t{timestamp:.1f}s.{format}"
                    )

                    # Convert RGBA to PIL and save
                    result_pil = Image.fromarray(result)
                    result_pil.save(output_path, format=format.upper())

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
