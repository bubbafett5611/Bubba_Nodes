from __future__ import annotations

import time
from collections import Counter
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from comfy_api.latest import IO

from ..compat.core_nodes import common_ksampler, encode_inpaint_conditioning
from ..compat.sampling import sampler_names, scheduler_names
from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.detailer_core import composite_crop, crop_conditioning, crop_image
from ..utils.detailer_masks import (
    bbox_to_mask,
    label_allowed,
    parse_label_filter,
    plan_crop,
    postprocess_mask,
    sorted_detections,
)
from ..utils.detailer_models import detector_dropdown_values, load_detector
from ..utils.detailer_types import DetailerDetection
from ..utils.prompting import encode_conditioning
from ..utils.progress import ProgressReporter


class BubbaDetailer(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        i, f = IO.Int.Input, IO.Float.Input
        pipe, metadata = IO.Custom("BUBBA_PIPE"), IO.Custom("BUBBA_METADATA")
        inputs = [
            IO.Combo.Input("detector_model_name", options=detector_dropdown_values()),
            f("confidence", default=0.3, min=0.01, max=1, step=0.01),
            i("mask_dilation", default=4, min=-64, max=128),
            i("mask_blur", default=4, min=0, max=64),
            i("inpaint_padding", default=32, min=0, max=256),
            IO.Boolean.Input("force_square_crop", default=False),
            i("guide_size", default=512, min=64, max=4096, step=8),
            IO.Boolean.Input("guide_size_for", default=True, label_on="bbox", label_off="crop"),
            i("max_size", default=1024, min=64, max=4096, step=8),
            i("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF, control_after_generate=True),
            i("steps", default=20, min=1, max=10000),
            f("cfg", default=7, min=0, max=100, step=0.1, round=0.01),
            IO.Combo.Input("sampler_name", options=sampler_names()),
            IO.Combo.Input("scheduler", options=scheduler_names()),
            f("denoise", default=0.45, min=0, max=1, step=0.01),
            i("max_detections", default=5, min=1, max=50),
            pipe.Input("pipe", optional=True),
            IO.Image.Input("image", optional=True),
            metadata.Input("metadata", optional=True),
            IO.Model.Input("model", optional=True),
            IO.Clip.Input("clip", optional=True),
            IO.Vae.Input("vae", optional=True),
            IO.Conditioning.Input("positive", optional=True),
            IO.Conditioning.Input("negative", optional=True),
            IO.String.Input("detail_positive", default="", multiline=True, optional=True, extra_dict={"bubba.autocomplete": {}}),
            IO.String.Input(
                "detail_negative", default="", multiline=True, optional=True, extra_dict={"bubba.autocomplete": {"group": "negative"}}
            ),
            IO.String.Input("include_labels", default="", optional=True),
            IO.String.Input("exclude_labels", default="", optional=True),
            IO.Boolean.Input("inpaint_model", default=False, optional=True),
        ]
        return IO.Schema(
            node_id="BubbaDetailer",
            display_name="Bubba Detailer",
            category="Bubba Nodes/Generation",
            description="Detects regions with Ultralytics and performs localized inpaint refinement.",
            inputs=inputs,
            outputs=[
                pipe.Output("pipe"),
                IO.Image.Output("image"),
                IO.Mask.Output("mask"),
                metadata.Output("metadata"),
                IO.String.Output("info"),
            ],
        )

    @classmethod
    def execute(
        cls,
        detector_model_name,
        confidence,
        mask_dilation,
        mask_blur,
        inpaint_padding,
        force_square_crop,
        guide_size,
        guide_size_for,
        max_size,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        max_detections,
        pipe=None,
        image=None,
        metadata=None,
        model=None,
        clip=None,
        vae=None,
        positive=None,
        negative=None,
        detail_positive="",
        detail_negative="",
        include_labels="",
        exclude_labels="",
        inpaint_model=False,
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_image = resolve_pipe_value(image, source_pipe.image, "image")
        resolved_model = resolve_pipe_value(model, source_pipe.model, "model")
        resolved_vae = resolve_pipe_value(vae, source_pipe.vae, "vae")
        resolved_clip = clip if clip is not None else source_pipe.clip
        start_time = time.perf_counter()
        mode, detector_path, detector = load_detector(detector_model_name)
        resolved_positive, resolved_negative = cls._resolve_conditioning(
            positive if positive is not None else source_pipe.positive,
            negative if negative is not None else source_pipe.negative,
            resolved_clip,
            detail_positive,
            detail_negative,
        )

        output_images = []
        output_masks = []
        total_processed = 0
        total_matched = 0
        fallback_count = 0
        label_counter: Counter[str] = Counter()
        progress = ProgressReporter(int(resolved_image.shape[0]) * int(max_detections))

        for batch_index, sample in enumerate(resolved_image):
            working = sample.unsqueeze(0).clone()
            detections, fallbacks = cls._detect_sample(detector, working, mode, confidence, include_labels, exclude_labels)
            fallback_count += fallbacks
            detections = sorted_detections(detections)
            total_matched += len(detections)
            processed_for_sample = 0
            union_mask = torch.zeros((working.shape[1], working.shape[2]), dtype=working.dtype, device=working.device)

            for detection_index, detection in enumerate(detections[: int(max_detections)]):
                processed = cls._process_detection(
                    working,
                    detection,
                    resolved_model,
                    resolved_vae,
                    resolved_positive,
                    resolved_negative,
                    int(seed) + batch_index + detection_index,
                    int(steps),
                    float(cfg),
                    sampler_name,
                    scheduler,
                    float(denoise),
                    int(mask_dilation),
                    int(mask_blur),
                    int(inpaint_padding),
                    bool(force_square_crop),
                    int(guide_size),
                    bool(guide_size_for),
                    int(max_size),
                    bool(inpaint_model),
                )
                if processed is None:
                    progress.update()
                    continue

                working, processed_mask = processed
                union_mask = torch.maximum(union_mask, processed_mask.to(device=union_mask.device, dtype=union_mask.dtype))
                processed_for_sample += 1
                label_counter[detection.label] += 1
                progress.update()

            total_processed += processed_for_sample
            output_images.append(working)
            output_masks.append(union_mask.unsqueeze(0))

        result_image = torch.cat(output_images, dim=0)
        result_mask = torch.cat(output_masks, dim=0)
        elapsed = time.perf_counter() - start_time
        updated_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        info = cls._format_info(detector_model_name, mode, total_matched, total_processed, elapsed, label_counter, fallback_count)
        updated_pipe = source_pipe.updated(
            image=result_image,
            mask=result_mask,
            model=resolved_model,
            clip=resolved_clip,
            vae=resolved_vae,
            positive=resolved_positive,
            negative=resolved_negative,
            metadata=updated_metadata,
        )
        return IO.NodeOutput(updated_pipe, result_image, result_mask, updated_metadata, info)

    @staticmethod
    def _resolve_conditioning(positive, negative, clip, detail_positive: str, detail_negative: str):
        has_positive_override = bool(str(detail_positive or "").strip())
        has_negative_override = bool(str(detail_negative or "").strip())
        if not has_positive_override and not has_negative_override:
            if positive is None or negative is None:
                raise ValueError(
                    "BubbaDetailer needs conditioning inputs, or connect clip and provide detail_positive/detail_negative prompt text."
                )
            return positive, negative
        if clip is None:
            raise ValueError("BubbaDetailer detail_positive/detail_negative overrides require the optional clip input.")
        return (
            encode_conditioning(clip, detail_positive) if has_positive_override or positive is None else positive,
            encode_conditioning(clip, detail_negative) if has_negative_override or negative is None else negative,
        )

    @classmethod
    def _detect_sample(cls, detector, image: torch.Tensor, mode: str, confidence: float, include_labels: str, exclude_labels: str):
        height, width = image.shape[1], image.shape[2]
        image_np = np.clip(image[0].detach().cpu().numpy() * 255.0, 0, 255).astype(np.uint8)
        results = detector(image_np, conf=float(confidence), verbose=False)
        result = results[0] if isinstance(results, (list, tuple)) else results
        include = parse_label_filter(include_labels)
        exclude = parse_label_filter(exclude_labels)
        detections: list[DetailerDetection] = []
        fallbacks = 0

        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return detections, fallbacks

        xyxy_values = cls._tensor_to_list(getattr(boxes, "xyxy", []))
        conf_values = cls._tensor_to_list(getattr(boxes, "conf", []))
        cls_values = cls._tensor_to_list(getattr(boxes, "cls", []))
        names = getattr(result, "names", {}) or getattr(detector, "names", {}) or {}

        for index, bbox_values in enumerate(xyxy_values):
            bbox = tuple(int(round(float(value))) for value in bbox_values[:4])
            bbox = (bbox[0], bbox[1], bbox[2], bbox[3])
            confidence_value = float(conf_values[index]) if index < len(conf_values) else 0.0
            class_index = int(cls_values[index]) if index < len(cls_values) else index
            label = str(names.get(class_index, class_index))
            if not label_allowed(label, include, exclude):
                continue

            mask = cls._segmentation_mask_for_result(result, index, height, width)
            if mask is None:
                mask = bbox_to_mask(bbox, height, width)
                if mode == "segm":
                    fallbacks += 1

            area = int((mask > 0.001).sum().item())
            if area <= 0:
                continue
            detections.append(DetailerDetection(label=label, confidence=confidence_value, bbox_xyxy=bbox, mask=mask, area=area))

        return detections, fallbacks

    @staticmethod
    def _tensor_to_list(value: Any) -> list:
        if isinstance(value, torch.Tensor):
            return value.detach().cpu().tolist()
        if hasattr(value, "cpu") and hasattr(value, "tolist"):
            return value.cpu().tolist()
        if hasattr(value, "tolist"):
            return value.tolist()
        return list(value or [])

    @classmethod
    def _segmentation_mask_for_result(cls, result, index: int, height: int, width: int) -> torch.Tensor | None:
        masks = getattr(result, "masks", None)
        if masks is None:
            return None

        data = getattr(masks, "data", None)
        if data is not None:
            mask_list = cls._tensor_to_list(data)
            if index < len(mask_list):
                mask = torch.as_tensor(mask_list[index], dtype=torch.float32)
                if tuple(mask.shape[-2:]) != (height, width):
                    mask = F.interpolate(
                        mask.unsqueeze(0).unsqueeze(0), size=(height, width), mode="bilinear", align_corners=False
                    ).squeeze()
                return mask.clamp(0.0, 1.0)

        polygons = getattr(masks, "xy", None)
        if polygons is not None and index < len(polygons):
            from ..utils.detailer_masks import polygon_to_mask

            points = [(float(x), float(y)) for x, y in polygons[index]]
            return polygon_to_mask(points, height, width)
        return None

    @classmethod
    def _process_detection(
        cls,
        working,
        detection,
        model,
        vae,
        positive,
        negative,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        mask_dilation,
        mask_blur,
        inpaint_padding,
        force_square_crop,
        guide_size,
        guide_size_for_bbox,
        max_size,
        inpaint_model,
    ):
        processed_mask = postprocess_mask(detection.mask, mask_dilation, mask_blur).to(device=working.device, dtype=working.dtype)
        crop = plan_crop(processed_mask.detach().cpu(), inpaint_padding, force_square_crop)
        if crop is None:
            return None

        crop = type(crop)(
            x1=crop.x1,
            y1=crop.y1,
            x2=crop.x2,
            y2=crop.y2,
            mask=crop.mask.to(device=working.device, dtype=working.dtype),
        )
        cropped_image = crop_image(working, crop)
        cropped_mask = crop.mask.unsqueeze(0)
        crop_bbox = (
            max(0, detection.bbox_xyxy[0] - crop.x1),
            max(0, detection.bbox_xyxy[1] - crop.y1),
            min(crop.width, detection.bbox_xyxy[2] - crop.x1),
            min(crop.height, detection.bbox_xyxy[3] - crop.y1),
        )
        cropped_positive = crop_conditioning(positive, crop)
        cropped_negative = crop_conditioning(negative, crop)
        refined = cls._inpaint_crop(
            cropped_image,
            cropped_mask,
            crop_bbox,
            model,
            vae,
            cropped_positive,
            cropped_negative,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            denoise,
            guide_size,
            guide_size_for_bbox,
            max_size,
            inpaint_model,
        )
        return composite_crop(working, refined, crop), processed_mask

    @staticmethod
    def _inpaint_crop(
        cropped_image,
        cropped_mask,
        crop_bbox,
        model,
        vae,
        positive,
        negative,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
        guide_size,
        guide_size_for_bbox,
        max_size,
        inpaint_model,
    ):
        upscaled_image, upscaled_mask = BubbaDetailer._prepare_guided_crop(
            cropped_image,
            cropped_mask,
            crop_bbox,
            guide_size,
            guide_size_for_bbox,
            max_size,
        )

        if inpaint_model:
            sample_positive, sample_negative, latent = encode_inpaint_conditioning(
                positive,
                negative,
                upscaled_image,
                vae,
                upscaled_mask,
                True,
            )
        else:
            latent = {
                "samples": vae.encode(upscaled_image),
                "noise_mask": upscaled_mask.reshape((-1, 1, upscaled_mask.shape[-2], upscaled_mask.shape[-1])),
            }
            sample_positive = positive
            sample_negative = negative

        sampled = common_ksampler(
            model, seed, steps, cfg, sampler_name, scheduler, sample_positive, sample_negative, latent, denoise=denoise
        )[0]
        samples = sampled["samples"]
        if getattr(samples, "is_nested", False):
            samples = samples.unbind()[0]
        decoded = vae.decode(samples)
        if len(decoded.shape) == 5:
            decoded = decoded.reshape(-1, decoded.shape[-3], decoded.shape[-2], decoded.shape[-1])
        return decoded

    @staticmethod
    def _prepare_guided_crop(cropped_image, cropped_mask, crop_bbox, guide_size, guide_size_for_bbox, max_size):
        crop_h = int(cropped_image.shape[1])
        crop_w = int(cropped_image.shape[2])
        bbox_w = max(1, int(crop_bbox[2] - crop_bbox[0]))
        bbox_h = max(1, int(crop_bbox[3] - crop_bbox[1]))
        target_basis = min(bbox_w, bbox_h) if guide_size_for_bbox else min(crop_w, crop_h)
        scale = max(1.0, float(guide_size) / max(1, target_basis))
        new_w = max(8, int(round(crop_w * scale)))
        new_h = max(8, int(round(crop_h * scale)))
        if max(new_w, new_h) > max_size:
            scale *= float(max_size) / float(max(new_w, new_h))
            new_w = max(8, int(round(crop_w * scale)))
            new_h = max(8, int(round(crop_h * scale)))

        new_w = max(8, (new_w // 8) * 8)
        new_h = max(8, (new_h // 8) * 8)
        if new_w == crop_w and new_h == crop_h:
            return cropped_image, cropped_mask

        image = F.interpolate(cropped_image.movedim(-1, 1), size=(new_h, new_w), mode="bicubic", align_corners=False).movedim(1, -1)
        mask = F.interpolate(cropped_mask.unsqueeze(1), size=(new_h, new_w), mode="bilinear", align_corners=False).squeeze(1)
        return image.clamp(0.0, 1.0), mask.clamp(0.0, 1.0)

    @staticmethod
    def _format_info(detector_model_name, mode, matched, processed, elapsed, label_counter, fallback_count):
        labels = ", ".join(f"{label}:{count}" for label, count in sorted(label_counter.items())) or "none"
        return (
            f"Detector: {detector_model_name}  Mode: {mode}  Matched: {matched}  "
            f"Processed: {processed}  Time: {elapsed:.3f}s\n"
            f"Labels: {labels}\n"
            f"Fallbacks: segm_to_bbox:{fallback_count}  Skipped: {max(0, matched - processed)}"
        )
