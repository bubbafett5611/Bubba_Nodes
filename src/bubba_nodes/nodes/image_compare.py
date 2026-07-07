import base64
import io

from comfy_api.latest import IO

from ..models import BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.image_ops import tensor_sample_to_pil


def _pil_to_base64_chunks(pil_image, chunk_size: int = 65536) -> list[str]:
    """Encode a PIL image as base64 chunks to keep UI payload strings manageable."""
    with io.BytesIO() as buffer:
        pil_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return [encoded[i : i + chunk_size] for i in range(0, len(encoded), chunk_size)]


class BubbaImageCompare(IO.ComfyNode):
    """Interactive A/B image compare node with a draggable split bar rendered in the frontend."""

    @classmethod
    def define_schema(cls):
        pipe = IO.Custom("BUBBA_PIPE")
        return IO.Schema(
            node_id="BubbaImageCompare",
            display_name="Bubba Image Compare",
            category="Bubba Nodes/Image",
            description="Interactive A/B compare with a draggable split bar directly in the node UI. Uses the first frame from each batch.",
            inputs=[
                pipe.Input("pipe_a", optional=True, tooltip="Optional pipe containing the first image (A-side)."),
                pipe.Input("pipe_b", optional=True, tooltip="Optional pipe containing the second image (B-side)."),
                IO.Image.Input("image_a", optional=True, tooltip="Optional A-side image override. Overrides pipe_a.image."),
                IO.Image.Input("image_b", optional=True, tooltip="Optional B-side image override. Overrides pipe_b.image."),
            ],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, pipe_a=None, pipe_b=None, image_a=None, image_b=None):
        # No stock UI output represents an interactive split slider; image_compare_node.js owns this payload contract.
        source_pipe_a = BubbaPipe.coerce(pipe_a)
        source_pipe_b = BubbaPipe.coerce(pipe_b)
        image_a = resolve_pipe_value(image_a, source_pipe_a.image, "image_a")
        image_b = resolve_pipe_value(image_b, source_pipe_b.image, "image_b")
        if image_a is None or image_b is None or len(image_a) == 0 or len(image_b) == 0:
            return IO.NodeOutput(ui={"b64_a": [], "b64_b": []})

        pil_a = tensor_sample_to_pil(image_a[0])
        pil_b = tensor_sample_to_pil(image_b[0])

        b64_a = _pil_to_base64_chunks(pil_a)
        b64_b = _pil_to_base64_chunks(pil_b)

        return IO.NodeOutput(ui={"b64_a": b64_a, "b64_b": b64_b})
