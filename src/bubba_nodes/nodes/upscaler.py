import folder_paths
from comfy_extras.nodes_upscale_model import UpscaleModelLoader, ImageUpscaleWithModel
import comfy.utils

from ..models import BubbaMetadata


_UPSCALE_METHODS = ["lanczos", "bicubic", "bilinear", "nearest-exact", "area"]


class BubbaUpscaler:
    """Upscales an image using an ESRGAN/spandrel model, with an optional resize step
    to scale back down to a target size after upscaling.

    Typical hi-res workflow: 4x ESRGAN model → scale_by 0.5 → 2× the original resolution."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Image to upscale."}),
                "upscale_model_name": (
                    folder_paths.get_filename_list("upscale_models"),
                    {"tooltip": "ESRGAN or other spandrel-compatible upscale model."},
                ),
                "scale_by": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.1,
                        "max": 16.0,
                        "step": 0.05,
                        "tooltip": (
                            "Scale applied to the ESRGAN output. "
                            "1.0 = keep ESRGAN output as-is. "
                            "0.5 on a 4x model → 2× original resolution."
                        ),
                    },
                ),
                "resize_method": (
                    _UPSCALE_METHODS,
                    {"tooltip": "Interpolation method used for the post-ESRGAN resize step (ignored when scale_by is 1.0)."},
                ),
            },
            "optional": {
                "metadata": (
                    "BUBBA_METADATA",
                    {"tooltip": "Optional metadata to pass through unchanged."},
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "BUBBA_METADATA")
    RETURN_NAMES = ("image", "metadata")
    FUNCTION = "upscale"
    CATEGORY = "Bubba Nodes/Image"
    DESCRIPTION = (
        "Upscales an image using an ESRGAN/spandrel model. "
        "Use scale_by to resize the result after upscaling — e.g. 0.5 on a 4x model "
        "gives you 2× the original resolution at high quality. "
        "Metadata is passed through unchanged."
    )

    def upscale(self, image, upscale_model_name, scale_by, resize_method, metadata=None):
        # Load the upscale model
        upscale_model = UpscaleModelLoader.execute(upscale_model_name)[0]

        # Apply ESRGAN upscale
        upscaled = ImageUpscaleWithModel.execute(upscale_model, image)[0]

        # Optional post-upscale resize
        if abs(scale_by - 1.0) > 1e-4:
            h, w = upscaled.shape[1], upscaled.shape[2]
            target_w = max(1, round(w * scale_by))
            target_h = max(1, round(h * scale_by))
            # common_upscale expects (B, C, H, W) tensors
            resized = comfy.utils.common_upscale(
                upscaled.movedim(-1, -3),
                target_w,
                target_h,
                resize_method,
                "disabled",
            )
            upscaled = resized.movedim(-3, -1)

        return (upscaled, BubbaMetadata.coerce(metadata))
