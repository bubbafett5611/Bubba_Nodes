from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class DetailerDetection:
    label: str
    confidence: float
    bbox_xyxy: tuple[int, int, int, int]
    mask: torch.Tensor
    area: int


@dataclass(frozen=True)
class DetailerCrop:
    x1: int
    y1: int
    x2: int
    y2: int
    mask: torch.Tensor

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1
