from comfy_api.latest import IO

from ..compat.core_nodes import load_upscale_model, upscale_with_model
from ..compat.paths import get_filename_list
from ..compat.sampling import common_upscale
from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value


_UPSCALE_METHODS = ["lanczos", "bicubic", "bilinear", "nearest-exact", "area"]


def _resize_upscaled(image, scale_by, resize_method):
    if abs(scale_by - 1.0) <= 1e-4:
        return image

    height, width = image.shape[1:3]
    target_width = max(1, round(width * scale_by))
    target_height = max(1, round(height * scale_by))
    resized = common_upscale(
        image.movedim(-1, -3),
        target_width,
        target_height,
        resize_method,
        "disabled",
    )
    return resized.movedim(-3, -1)


class BubbaUpscaler(IO.ComfyNode):
    """Upscales an image using an ESRGAN/spandrel model, with an optional resize step
    to scale back down to a target size after upscaling.

    Typical hi-res workflow: 4x ESRGAN model -> scale_by 0.5 -> 2x the original resolution."""

    @classmethod
    def define_schema(cls):
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        return IO.Schema(
            node_id="BubbaUpscaler",
            display_name="Bubba Upscaler (ESRGAN)",
            category="Bubba Nodes/Image",
            description="Upscales an image with an ESRGAN/spandrel model and optional resize.",
            inputs=[
                IO.Combo.Input("upscale_model_name", options=get_filename_list("upscale_models")),
                IO.Float.Input("scale_by", default=1.0, min=0.1, max=16.0, step=0.05),
                IO.Combo.Input("resize_method", options=_UPSCALE_METHODS),
                pipe.Input("pipe", optional=True),
                IO.Image.Input("image", optional=True),
                metadata.Input("metadata", optional=True),
            ],
            outputs=[pipe.Output("pipe"), IO.Image.Output("image"), metadata.Output("metadata")],
        )

    @classmethod
    def execute(cls, upscale_model_name, scale_by, resize_method, pipe=None, image=None, metadata=None):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_image = resolve_pipe_value(image, source_pipe.image, "image")
        # Load the upscale model
        upscale_model = load_upscale_model(upscale_model_name)

        # Apply ESRGAN upscale
        upscaled = upscale_with_model(upscale_model, resolved_image)

        upscaled = _resize_upscaled(upscaled, scale_by, resize_method)

        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        updated_pipe = source_pipe.updated(image=upscaled, metadata=updated_metadata)
        return IO.NodeOutput(updated_pipe, upscaled, updated_metadata)
