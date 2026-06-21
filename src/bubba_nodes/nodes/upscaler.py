import folder_paths
from comfy_extras.nodes_upscale_model import UpscaleModelLoader, ImageUpscaleWithModel
import comfy.utils

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value


_UPSCALE_METHODS = ["lanczos", "bicubic", "bilinear", "nearest-exact", "area"]


def _load_upscale_model(upscale_model_name):
    if hasattr(UpscaleModelLoader, "execute"):
        return UpscaleModelLoader.execute(upscale_model_name)[0]
    loader = UpscaleModelLoader()
    if hasattr(loader, "load_model"):
        return loader.load_model(upscale_model_name)[0]
    if hasattr(loader, "execute"):
        return loader.execute(upscale_model_name)[0]
    raise AttributeError("UpscaleModelLoader does not expose execute or load_model")


def _upscale_with_model(upscale_model, image):
    if hasattr(ImageUpscaleWithModel, "execute"):
        return ImageUpscaleWithModel.execute(upscale_model, image)[0]
    node = ImageUpscaleWithModel()
    if hasattr(node, "upscale"):
        return node.upscale(upscale_model, image)[0]
    if hasattr(node, "execute"):
        return node.execute(upscale_model, image)[0]
    raise AttributeError("ImageUpscaleWithModel does not expose execute or upscale")


class BubbaUpscaler:
    """Upscales an image using an ESRGAN/spandrel model, with an optional resize step
    to scale back down to a target size after upscaling.

    Typical hi-res workflow: 4x ESRGAN model -> scale_by 0.5 -> 2x the original resolution."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
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
                            "0.5 on a 4x model -> 2x original resolution."
                        ),
                    },
                ),
                "resize_method": (
                    _UPSCALE_METHODS,
                    {"tooltip": "Interpolation method used for the post-ESRGAN resize step (ignored when scale_by is 1.0)."},
                ),
            },
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe containing the image to upscale."}),
                "image": ("IMAGE", {"tooltip": "Optional image override. Overrides pipe.image when connected."}),
                "metadata": (
                    "BUBBA_METADATA",
                    {"tooltip": "Optional metadata override. Overrides pipe.metadata when connected."},
                ),
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "IMAGE", "BUBBA_METADATA")
    RETURN_NAMES = ("pipe", "image", "metadata")
    FUNCTION = "upscale"
    CATEGORY = "Bubba Nodes/Image"
    DESCRIPTION = (
        "Upscales an image using an ESRGAN/spandrel model. "
        "Use scale_by to resize the result after upscaling. For example, 0.5 on a 4x model "
        "gives you 2x the original resolution at high quality. "
        "Metadata is passed through unchanged."
    )

    def upscale(self, upscale_model_name, scale_by, resize_method, pipe=None, image=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_image = resolve_pipe_value(image, source_pipe.image, "image")
        # Load the upscale model
        upscale_model = _load_upscale_model(upscale_model_name)

        # Apply ESRGAN upscale
        upscaled = _upscale_with_model(upscale_model, resolved_image)

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

        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        updated_pipe = source_pipe.updated(image=upscaled, metadata=updated_metadata)
        return (updated_pipe, upscaled, updated_metadata)
