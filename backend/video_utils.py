import os
import subprocess
import cv2
from PIL import Image
from loguru import logger
from scenedetect import detect, ContentDetector


def extract_audio(video_path: str, output_path: str) -> bool:
    """
    Extracts audio from video file using ffmpeg.
    """
    logger.info(f"Extracting audio from {video_path} to {output_path}")
    try:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "libmp3lame",
            "-q:a",
            "2",
            output_path,
        ]
        subprocess.run(
            command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg audio extraction failed: {e.stderr.decode()}")
        return False
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return False


def extract_keyframes_fixed_fps(
    video_path: str, output_dir: str, fps: float = 1.0
) -> list[str]:
    """
    Extracts frames from video at a fixed FPS.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Extracting frames from {video_path} at {fps} FPS")

    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")
    try:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vf",
            f"fps={fps}",
            output_pattern,
        ]
        subprocess.run(
            command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        frames = sorted(
            [
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f.startswith("frame_") and f.endswith(".jpg")
            ]
        )
        return frames
    except Exception as e:
        logger.error(f"FFmpeg frame extraction failed: {e}")
        return []


def extract_keyframes_scene_detection(
    video_path: str, output_dir: str, max_scenes: int = 20
) -> list[str]:
    """
    Extracts one keyframe per detected scene change.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Detecting scenes in {video_path} (limit={max_scenes})")

    try:
        scene_list = detect(video_path, ContentDetector())
        if not scene_list:
            logger.warning("No scenes detected, falling back to fixed FPS")
            return extract_keyframes_fixed_fps(video_path, output_dir, fps=0.5)

        logger.info(f"Detected {len(scene_list)} scenes")

        # If too many scenes, sample them
        if len(scene_list) > max_scenes:
            stride = len(scene_list) / max_scenes
            indices = [int(i * stride) for i in range(max_scenes)]
            scene_list = [scene_list[i] for i in indices]
            logger.info(f"Sampled down to {len(scene_list)} scenes")

        frames = []
        cap = cv2.VideoCapture(video_path)

        for i, scene in enumerate(scene_list):
            # Take the middle frame of the scene for better representation
            start_frame = scene[0].get_frames()
            end_frame = scene[1].get_frames()
            middle_frame = int((start_frame + end_frame) / 2)

            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            ret, frame = cap.read()
            if ret:
                frame_path = os.path.join(output_dir, f"scene_{i:04d}.jpg")
                cv2.imwrite(frame_path, frame)
                frames.append(frame_path)

        cap.release()
        return frames
    except Exception as e:
        logger.error(f"Scene detection failed: {e}")
        return extract_keyframes_fixed_fps(video_path, output_dir, fps=0.5)


def resize_image_smart(image_path: str, max_dim: int = 1024) -> str:
    """
    Resizes image preserving aspect ratio if it exceeds max_dim.
    Overwrites the original image or saves to a temp location?
    For now, let's overwrite for simplicity as it's a pre-processed copy.
    """
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            if w <= max_dim and h <= max_dim:
                return image_path

            if w > h:
                new_w = max_dim
                new_h = int(h * (max_dim / w))
            else:
                new_h = max_dim
                new_w = int(w * (max_dim / h))

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            img.save(image_path, quality=85)
            logger.info(f"Resized image {image_path} to {new_w}x{new_h}")
            return image_path
    except Exception as e:
        logger.error(f"Error resizing image {image_path}: {e}")
        return image_path
