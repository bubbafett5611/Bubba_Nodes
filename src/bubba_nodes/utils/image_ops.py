import numpy as np
import torch
from PIL import Image


def tensor_sample_to_pil(sample: torch.Tensor) -> Image.Image:
    sample_np = np.clip(255.0 * sample.cpu().numpy(), 0, 255).astype(np.uint8)
    return Image.fromarray(sample_np)


def pil_to_tensor_like(image: Image.Image, reference_sample: torch.Tensor, *, device, dtype) -> torch.Tensor:
    if reference_sample.shape[-1] == 4:
        out_arr = np.asarray(image, dtype=np.float32) / 255.0
    else:
        out_arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(out_arr).to(device=device, dtype=dtype)
