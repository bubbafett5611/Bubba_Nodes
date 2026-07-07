import hashlib
from typing import Any

import numpy as np
from PIL import Image, ImageOps, ImageSequence
import torch
from comfy_api.latest import IO

# TODO(new-node): Add a batch directory loader node that emits image, mask, and metadata streams with deterministic ordering.
# TODO(optimize): Move per-frame numpy->torch conversion to a shared helper that can reuse buffers for same-sized frames.

from ..compat.paths import exists_annotated_filepath, get_annotated_filepath, get_input_directory, input_image_files
from ..compat.runtime import intermediate_device, intermediate_dtype, pillow_call

from ..models import BubbaMetadata, BubbaPipe


class BubbaLoadImageWithMetadata(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        files = input_image_files()
        if files:
            image_input = IO.Combo.Input("image", options=sorted(files), extra_dict={"image_upload": True})
        else:
            image_input = IO.String.Input("image", default="")
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaLoadImageWithMetadata",
            display_name="Bubba Load Image (With Metadata)",
            category="Bubba Nodes/Image/Load",
            description="Loads image, mask, and embedded Bubba PNG metadata.",
            inputs=[image_input],
            outputs=[
                pipe.Output("pipe"),
                IO.Image.Output("image"),
                IO.Mask.Output("mask"),
                metadata.Output("metadata"),
                IO.String.Output("metadata_text"),
            ],
        )

    @staticmethod
    def _call_pillow(func, *args) -> Any:
        return pillow_call(func, *args)

    @staticmethod
    def _intermediate_dtype():
        return intermediate_dtype()

    @staticmethod
    def _intermediate_device():
        return intermediate_device()

    @classmethod
    def _resolve_image_path(cls, image: str) -> str:
        raw = str(image or "").strip()
        if not raw:
            raise ValueError("image is required.")

        return get_annotated_filepath(raw)

    @staticmethod
    def _extract_bubba_metadata(image_info: dict) -> tuple[BubbaMetadata, str]:
        raw_json = str(image_info.get("bubba_metadata", "") or "").strip()
        metadata = BubbaMetadata.from_json(raw_json)
        return (metadata, metadata.to_json(pretty=True))

    @classmethod
    def _load_open_image(cls, img):
        metadata, metadata_text = cls._extract_bubba_metadata(getattr(img, "info", {}))

        output_images: list[torch.Tensor] = []
        output_masks: list[torch.Tensor] = []
        width = None
        height = None
        dtype = cls._intermediate_dtype()
        device = cls._intermediate_device()

        # TODO(optimize): Add optional max_frames input and early termination for very large animated inputs.
        for frame in ImageSequence.Iterator(img):
            frame = cls._call_pillow(ImageOps.exif_transpose, frame)

            if frame.mode == "I":
                frame = frame.point(lambda i: i * (1 / 255))

            rgb = frame.convert("RGB")
            if len(output_images) == 0:
                width, height = rgb.size

            if rgb.size[0] != width or rgb.size[1] != height:
                continue

            image_np = np.asarray(rgb).astype(np.float32) / 255.0
            image_tensor = torch.from_numpy(image_np)[None,].to(device=device, dtype=dtype)

            if "A" in frame.getbands():
                alpha_np = np.asarray(frame.getchannel("A")).astype(np.float32) / 255.0
                mask_tensor = 1.0 - torch.from_numpy(alpha_np)
            elif frame.mode == "P" and "transparency" in frame.info:
                alpha_np = np.asarray(frame.convert("RGBA").getchannel("A")).astype(np.float32) / 255.0
                mask_tensor = 1.0 - torch.from_numpy(alpha_np)
            else:
                mask_tensor = torch.zeros((rgb.size[1], rgb.size[0]), dtype=torch.float32, device="cpu")

            output_images.append(image_tensor)
            output_masks.append(mask_tensor.unsqueeze(0).to(device=device, dtype=dtype))

            if img.format == "MPO":
                break

        if not output_images:
            raise ValueError("Bubba Load Image could not read any compatible image frames.")

        if len(output_images) > 1:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

        pipe = BubbaPipe(image=output_image, mask=output_mask, metadata=metadata)
        return IO.NodeOutput(pipe, output_image, output_mask, metadata, metadata_text)

    @classmethod
    def execute(cls, image):
        image_path = cls._resolve_image_path(image)
        try:
            with cls._call_pillow(Image.open, image_path) as img:
                return cls._load_open_image(img)
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(f"Bubba Load Image could not read image '{image}': {error}") from error

    @classmethod
    def fingerprint_inputs(cls, image):
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
    def validate_inputs(cls, image):
        raw = str(image or "").strip()
        if not raw:
            return "Invalid image file: empty path"

        input_dir = get_input_directory()
        if input_dir.exists():
            if not exists_annotated_filepath(raw):
                return f"Invalid image file: {raw}"
            return True

        try:
            path = cls._resolve_image_path(raw)
            with open(path, "rb"):
                pass
        except Exception:
            return f"Invalid image file: {raw}"
        return True
