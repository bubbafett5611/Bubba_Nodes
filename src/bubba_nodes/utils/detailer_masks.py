from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFilter

from .detailer_types import DetailerCrop, DetailerDetection


def parse_label_filter(value: str | None) -> set[str]:
    return {part.strip().lower() for part in str(value or "").split(",") if part.strip()}


def label_allowed(label: str, include_labels: Iterable[str], exclude_labels: Iterable[str]) -> bool:
    normalized = str(label or "").strip().lower()
    include = set(include_labels)
    exclude = set(exclude_labels)
    if include and normalized not in include:
        return False
    return normalized not in exclude


def bbox_to_mask(bbox_xyxy: tuple[int, int, int, int], height: int, width: int) -> torch.Tensor:
    x1, y1, x2, y2 = clamp_bbox(bbox_xyxy, height, width)
    mask = torch.zeros((height, width), dtype=torch.float32)
    if x2 > x1 and y2 > y1:
        mask[y1:y2, x1:x2] = 1.0
    return mask


def polygon_to_mask(points: list[tuple[float, float]], height: int, width: int) -> torch.Tensor:
    image = Image.new("L", (width, height), 0)
    if points:
        ImageDraw.Draw(image).polygon(points, fill=255)
    return torch.from_numpy(np.asarray(image, dtype=np.float32) / 255.0)


def clamp_bbox(bbox_xyxy: tuple[int, int, int, int], height: int, width: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox_xyxy
    return (
        max(0, min(width, int(round(x1)))),
        max(0, min(height, int(round(y1)))),
        max(0, min(width, int(round(x2)))),
        max(0, min(height, int(round(y2)))),
    )


def postprocess_mask(mask: torch.Tensor, dilation: int, blur: int) -> torch.Tensor:
    mask = mask.detach().float().cpu().clamp(0.0, 1.0)
    if dilation != 0:
        radius = abs(int(dilation))
        kernel = radius * 2 + 1
        batched = mask.unsqueeze(0).unsqueeze(0)
        if dilation > 0:
            mask = F.max_pool2d(batched, kernel, stride=1, padding=radius).squeeze(0).squeeze(0)
        else:
            mask = 1.0 - F.max_pool2d(1.0 - batched, kernel, stride=1, padding=radius).squeeze(0).squeeze(0)

    if blur > 0:
        arr = np.clip(mask.numpy() * 255.0, 0, 255).astype(np.uint8)
        image = Image.fromarray(arr, mode="L").filter(ImageFilter.GaussianBlur(radius=int(blur)))
        mask = torch.from_numpy(np.asarray(image, dtype=np.float32) / 255.0)

    return mask.clamp(0.0, 1.0)


def mask_bounds(mask: torch.Tensor) -> tuple[int, int, int, int] | None:
    nonzero = torch.nonzero(mask > 0.001, as_tuple=False)
    if nonzero.numel() == 0:
        return None
    y1 = int(nonzero[:, 0].min().item())
    y2 = int(nonzero[:, 0].max().item()) + 1
    x1 = int(nonzero[:, 1].min().item())
    x2 = int(nonzero[:, 1].max().item()) + 1
    return x1, y1, x2, y2


def plan_crop(mask: torch.Tensor, padding: int, force_square: bool, multiple: int = 8) -> DetailerCrop | None:
    bounds = mask_bounds(mask)
    if bounds is None:
        return None

    height, width = mask.shape[-2], mask.shape[-1]
    x1, y1, x2, y2 = bounds
    x1 -= padding
    y1 -= padding
    x2 += padding
    y2 += padding

    if force_square:
        crop_w = x2 - x1
        crop_h = y2 - y1
        side = max(crop_w, crop_h)
        x_pad = side - crop_w
        y_pad = side - crop_h
        x1 -= x_pad // 2
        x2 += x_pad - x_pad // 2
        y1 -= y_pad // 2
        y2 += y_pad - y_pad // 2

    x1, y1, x2, y2 = expand_to_multiple((x1, y1, x2, y2), height, width, multiple)
    if x2 - x1 < multiple or y2 - y1 < multiple:
        return None
    return DetailerCrop(x1=x1, y1=y1, x2=x2, y2=y2, mask=mask[y1:y2, x1:x2])


def expand_to_multiple(bbox_xyxy: tuple[int, int, int, int], height: int, width: int, multiple: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox_xyxy
    x1 = max(0, min(width, x1))
    x2 = max(0, min(width, x2))
    y1 = max(0, min(height, y1))
    y2 = max(0, min(height, y2))

    x1, x2 = _expand_axis_to_multiple(x1, x2, width, multiple)
    y1, y2 = _expand_axis_to_multiple(y1, y2, height, multiple)
    return x1, y1, x2, y2


def _expand_axis_to_multiple(start: int, end: int, limit: int, multiple: int) -> tuple[int, int]:
    size = max(0, end - start)
    remainder = size % multiple
    if remainder == 0:
        return start, end

    needed = multiple - remainder
    before = needed // 2
    after = needed - before
    start = max(0, start - before)
    end = min(limit, end + after)

    size = end - start
    remainder = size % multiple
    if remainder == 0:
        return start, end

    needed = multiple - remainder
    if start > 0:
        start = max(0, start - needed)
    elif end < limit:
        end = min(limit, end + needed)
    return start, end


def sorted_detections(detections: Iterable[DetailerDetection]) -> list[DetailerDetection]:
    return sorted(detections, key=lambda detection: detection.area, reverse=True)
