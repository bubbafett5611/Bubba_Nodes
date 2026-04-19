import hashlib
import os
import numpy as np
from PIL import Image, ImageOps, ImageSequence
import torch

# TODO(new-node): Add a batch directory loader node that emits image, mask, and metadata streams with deterministic ordering.
# TODO(optimize): Move per-frame numpy->torch conversion to a shared helper that can reuse buffers for same-sized frames.

try:
    import folder_paths
except Exception:  # pragma: no cover - only used inside Comfy runtime
    folder_paths = None

try:
    import node_helpers
except Exception:  # pragma: no cover - only used inside Comfy runtime
    node_helpers = None

try:
    import comfy.model_management
except Exception:  # pragma: no cover - only used inside Comfy runtime
    comfy = None

from ..models import BubbaMetadata


class BubbaLoadImageWithMetadata:
    @classmethod
    def INPUT_TYPES(s):
        if folder_paths is not None and hasattr(folder_paths, "get_input_directory"):
            input_dir = folder_paths.get_input_directory()
            files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
            files = folder_paths.filter_files_content_types(files, ["image"])
            return {
                "required": {
                    "image": (
                        sorted(files),
                        {
                            "image_upload": True,
                            "tooltip": "Input image filename (ComfyUI input folder).",
                        },
                    ),
                },
            }

        return {
            "required": {
                "image": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "Absolute path to an image file (fallback mode outside ComfyUI runtime).",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "BUBBA_METADATA", "STRING")
    RETURN_NAMES = ("image", "mask", "metadata", "metadata_text")
    FUNCTION = "load_image"
    CATEGORY = "Bubba Nodes/Image/Load"
    DESCRIPTION = "Loads an image using ComfyUI LoadImage behavior and returns mask plus embedded Bubba metadata (PNG text key 'bubba_metadata')."

    @staticmethod
    def _call_pillow(func, *args):
        if node_helpers is not None and hasattr(node_helpers, "pillow"):
            return node_helpers.pillow(func, *args)
        return func(*args)

    @staticmethod
    def _intermediate_dtype():
        if comfy is not None and hasattr(comfy, "model_management") and hasattr(comfy.model_management, "intermediate_dtype"):
            return comfy.model_management.intermediate_dtype()
        return torch.float32

    @classmethod
    def _resolve_image_path(cls, image: str) -> str:
        raw = str(image or "").strip()
        if not raw:
            raise ValueError("image is required.")

        if folder_paths is not None and hasattr(folder_paths, "get_annotated_filepath"):
            return folder_paths.get_annotated_filepath(raw)

        return raw

    @staticmethod
    def _extract_bubba_metadata(image_info: dict) -> tuple[BubbaMetadata, str]:
        raw_json = str(image_info.get("bubba_metadata", "") or "").strip()
        metadata = BubbaMetadata.from_json(raw_json)
        return (metadata, metadata.to_json(pretty=True))

    def load_image(self, image):
        image_path = self._resolve_image_path(image)
        img = self._call_pillow(Image.open, image_path)
        metadata, metadata_text = self._extract_bubba_metadata(getattr(img, "info", {}))

        output_images = []
        output_masks = []
        width = None
        height = None
        dtype = self._intermediate_dtype()

        # TODO(optimize): Add optional max_frames input and early termination for very large animated inputs.
        for frame in ImageSequence.Iterator(img):
            frame = self._call_pillow(ImageOps.exif_transpose, frame)

            if frame.mode == "I":
                frame = frame.point(lambda i: i * (1 / 255))

            rgb = frame.convert("RGB")
            if len(output_images) == 0:
                width, height = rgb.size

            if rgb.size[0] != width or rgb.size[1] != height:
                continue

            image_np = np.asarray(rgb).astype(np.float32) / 255.0
            image_tensor = torch.from_numpy(image_np)[None,].to(dtype=dtype)

            if "A" in frame.getbands():
                mask = np.asarray(frame.getchannel("A")).astype(np.float32) / 255.0
                mask = 1.0 - torch.from_numpy(mask)
            elif frame.mode == "P" and "transparency" in frame.info:
                mask = np.asarray(frame.convert("RGBA").getchannel("A")).astype(np.float32) / 255.0
                mask = 1.0 - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")

            output_images.append(image_tensor)
            output_masks.append(mask.unsqueeze(0).to(dtype=dtype))

            if img.format == "MPO":
                break

        if len(output_images) > 1:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

        return (output_image, output_mask, metadata, metadata_text)

    @classmethod
    def IS_CHANGED(cls, image):
        image_path = cls._resolve_image_path(image)
        digest = hashlib.sha256()
        with open(image_path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, image):
        raw = str(image or "").strip()
        if not raw:
            return "Invalid image file: empty path"

        if folder_paths is not None and hasattr(folder_paths, "exists_annotated_filepath"):
            if not folder_paths.exists_annotated_filepath(raw):
                return f"Invalid image file: {raw}"
            return True

        try:
            path = cls._resolve_image_path(raw)
            with open(path, "rb"):
                pass
        except Exception:
            return f"Invalid image file: {raw}"
        return True
