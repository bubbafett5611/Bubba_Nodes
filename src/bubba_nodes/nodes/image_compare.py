import base64
import io

from ..utils.image_ops import tensor_sample_to_pil


def _pil_to_base64_chunks(pil_image, chunk_size: int = 65536) -> list[str]:
    """Encode a PIL image as base64 chunks to keep UI payload strings manageable."""
    with io.BytesIO() as buffer:
        pil_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return [encoded[i : i + chunk_size] for i in range(0, len(encoded), chunk_size)]


class BubbaImageCompare:
    """Interactive A/B image compare node with a draggable split bar rendered in the frontend."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_a": ("IMAGE", {"tooltip": "First image (A-side)."}),
                "image_b": ("IMAGE", {"tooltip": "Second image (B-side)."}),
            },
        }

    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "compare"
    CATEGORY = "Bubba Nodes/Image"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Interactive A/B compare with a draggable split bar directly in the node UI. "
        "No side-by-side/top-bottom composite output; this node is preview-focused. "
        "Uses the first frame from each input batch."
    )

    def compare(self, image_a, image_b):
        if image_a is None or image_b is None or len(image_a) == 0 or len(image_b) == 0:
            return {"ui": {"b64_a": [], "b64_b": []}}

        pil_a = tensor_sample_to_pil(image_a[0])
        pil_b = tensor_sample_to_pil(image_b[0])

        b64_a = _pil_to_base64_chunks(pil_a)
        b64_b = _pil_to_base64_chunks(pil_b)

        return {"ui": {"b64_a": b64_a, "b64_b": b64_b}}
