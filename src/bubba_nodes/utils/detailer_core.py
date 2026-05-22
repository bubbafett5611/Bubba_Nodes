from __future__ import annotations

import torch
import torch.nn.functional as F

from .detailer_types import DetailerCrop


def crop_image(image: torch.Tensor, crop: DetailerCrop) -> torch.Tensor:
    return image[:, crop.y1 : crop.y2, crop.x1 : crop.x2, :]


def crop_conditioning(conditioning, crop: DetailerCrop):
    if isinstance(conditioning, str):
        return conditioning

    cropped = []
    for item in conditioning:
        if not isinstance(item, (list, tuple)) or len(item) != 2 or not isinstance(item[1], dict):
            cropped.append(item)
            continue

        condition, details = item
        next_details = {}
        for key, value in details.items():
            if key == "mask" and isinstance(value, torch.Tensor):
                next_details[key] = crop_mask_tensor(value, crop)
            else:
                next_details[key] = value
        cropped.append([condition, next_details])
    return cropped


def crop_mask_tensor(mask: torch.Tensor, crop: DetailerCrop) -> torch.Tensor:
    if mask.ndim == 2:
        return mask[crop.y1 : crop.y2, crop.x1 : crop.x2]
    if mask.ndim == 3:
        return mask[:, crop.y1 : crop.y2, crop.x1 : crop.x2]
    if mask.ndim == 4:
        return mask[:, :, crop.y1 : crop.y2, crop.x1 : crop.x2]
    return mask


def composite_crop(base_image: torch.Tensor, refined_crop: torch.Tensor, crop: DetailerCrop) -> torch.Tensor:
    target = base_image.clone()
    crop_h, crop_w = crop.height, crop.width
    refined = refined_crop
    if refined.shape[1] != crop_h or refined.shape[2] != crop_w:
        refined = F.interpolate(refined.movedim(-1, 1), size=(crop_h, crop_w), mode="bilinear", align_corners=False).movedim(1, -1)

    mask = crop.mask.to(device=target.device, dtype=target.dtype).clamp(0.0, 1.0)
    if mask.ndim == 2:
        mask = mask.unsqueeze(0).unsqueeze(-1)
    elif mask.ndim == 3:
        mask = mask.unsqueeze(-1)

    existing = target[:, crop.y1 : crop.y2, crop.x1 : crop.x2, :]
    target[:, crop.y1 : crop.y2, crop.x1 : crop.x2, :] = (
        existing * (1.0 - mask) + refined.to(device=target.device, dtype=target.dtype) * mask
    )
    return target
