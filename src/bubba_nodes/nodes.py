import re
import time
from functools import lru_cache
from comfy_api.latest import IO, UI
import comfy.samplers
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch
from nodes import common_ksampler


INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*]')

class BubbaFilename:
    """
    Builds a file path string in the format: <character_name>/<scene_name>
    Spaces are replaced with underscores and characters invalid in file paths are removed.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "character_name": ("STRING", {
                    "multiline": False,
                    "default": "Character",
                    "tooltip": "Used as the folder name in the output path.",
                }),
                "scene_name": ("STRING", {
                    "multiline": False,
                    "default": "Scene",
                    "tooltip": "Used as the image/file name in the output path.",
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filepath",)
    FUNCTION = "build_path"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Combines a character name (folder) and scene name (filename) into a relative file path."

    def build_path(self, character_name, scene_name):
        def sanitize(name):
            name = name.strip()
            name = name.replace(" ", "_")
            name = INVALID_PATH_CHARS.sub('', name)
            return name

        folder = sanitize(character_name)
        filename = sanitize(scene_name)
        filepath = f"{folder}/{filename}"
        return (filepath,)


class BubbaKSampler:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": (
                    "MODEL",
                    {"tooltip": "The model used for denoising the input latent."},
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                        "tooltip": "The random seed used for creating the noise.",
                    },
                ),
                "steps": (
                    "INT",
                    {
                        "default": 20,
                        "min": 1,
                        "max": 10000,
                        "tooltip": "The number of steps used in the denoising process.",
                    },
                ),
                "cfg": (
                    "FLOAT",
                    {
                        "default": 8.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "round": 0.01,
                        "tooltip": "The Classifier-Free Guidance scale used during sampling.",
                    },
                ),
                "sampler_name": (
                    comfy.samplers.KSampler.SAMPLERS,
                    {
                        "tooltip": "The sampling algorithm used to generate the image.",
                    },
                ),
                "scheduler": (
                    comfy.samplers.KSampler.SCHEDULERS,
                    {
                        "tooltip": "The scheduler controls how noise is removed across steps.",
                    },
                ),
                "positive": (
                    "CONDITIONING",
                    {
                        "tooltip": "The conditioning describing the attributes you want to include in the image.",
                    },
                ),
                "negative": (
                    "CONDITIONING",
                    {
                        "tooltip": "The conditioning describing the attributes you want to exclude from the image.",
                    },
                ),
                "latent_image": (
                    "LATENT",
                    {"tooltip": "The latent image to denoise."},
                ),
                "denoise": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "The amount of denoising applied.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("LATENT", "STRING")
    RETURN_NAMES = ("LATENT", "INFO")
    FUNCTION = "sample"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Runs KSampler and outputs a formatted generation info string for overlays or save metadata."

    @staticmethod
    def _format_info(elapsed_seconds, seed, steps, cfg, sampler_name, scheduler, denoise):
        return (f"Time: {elapsed_seconds:.3f}s  Seed: {seed}  Steps: {steps}  CFG: {cfg}"
                f"  Sampler: {sampler_name}  Scheduler: {scheduler}  Denoise: {denoise}")

    def sample(
        self,
        model,
        seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        positive,
        negative,
        latent_image,
        denoise=1.0,
    ):
        start_time = time.perf_counter()
        latent = common_ksampler(
            model,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            positive,
            negative,
            latent_image,
            denoise=denoise,
        )[0]
        elapsed_seconds = time.perf_counter() - start_time
        info = self._format_info(
            elapsed_seconds,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            denoise,
        )
        return (latent, info)


class BubbaSaveImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "filepath": (
                    "STRING",
                    {
                        "default": "Character/Scene",
                        "tooltip": "Relative output path prefix, e.g. Character/Scene.",
                    },
                ),
                "preview_only": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Enable to save as temp preview images instead of writing to output.",
                    },
                ),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Saves images using the given filepath prefix, with optional preview-only temp mode."

    def save_images(self, images, filepath, preview_only):
        if preview_only:
            return {"ui": UI.PreviewImage(images, cls=None).as_dict()}

        return {
            "ui": UI.ImageSaveHelper.get_save_images_ui(
                images=images,
                filename_prefix=filepath,
                cls=None,
            ).as_dict()
        }


class BubbaAddOverlay:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "model_text": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional model label text.",
                        "multiline": False,
                    },
                ),
                "info_text": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional generation info text.",
                        "multiline": False,
                    },
                ),
                "positive_text": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional positive prompt text.",
                        "multiline": True,
                    },
                ),
                "negative_text": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Optional negative prompt text.",
                        "multiline": True,
                    },
                ),
                "show_model": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "model_position": (
                    ["top", "bottom"],
                    {
                        "default": "top",
                    },
                ),
                "show_info": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "info_position": (
                    ["top", "bottom"],
                    {
                        "default": "top",
                    },
                ),
                "show_positive": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "positive_position": (
                    ["top", "bottom"],
                    {
                        "default": "bottom",
                    },
                ),
                "show_negative": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "negative_position": (
                    ["top", "bottom"],
                    {
                        "default": "bottom",
                    },
                ),
                "background_color": (
                    "STRING",
                    {
                        "default": "#000000AA",
                        "multiline": False,
                    },
                ),
                "font_size": (
                    "INT",
                    {
                        "default": 40,
                        "min": 10,
                        "max": 1000,
                    },
                ),
                "overlay_mode": (
                    "BOOLEAN",
                    {
                        "default": True,
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "add_text_overlay"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Adds an iTools-style text bar in overlay or underlay mode from individually toggled metadata fields."

    @staticmethod
    def _compose_text(
        model_text,
        info_text,
        positive_text,
        negative_text,
        show_model,
        show_info,
        show_positive,
        show_negative,
        model_position,
        info_position,
        positive_position,
        negative_position,
    ):
        top_parts, bottom_parts = [], []
        if show_model and model_text.strip():
            (top_parts if model_position == "top" else bottom_parts).append(f"Model: {model_text.strip()}")
        if show_info and info_text.strip():
            (top_parts if info_position == "top" else bottom_parts).append(f"{info_text.strip()}")
        if show_positive and positive_text.strip():
            (top_parts if positive_position == "top" else bottom_parts).append(f"Positive:\n{positive_text.strip()}")
        if show_negative and negative_text.strip():
            (top_parts if negative_position == "top" else bottom_parts).append(f"Negative:\n{negative_text.strip()}")
        return "\n".join(top_parts), "\n".join(bottom_parts)

    @staticmethod
    def _parse_rgba(color: str) -> tuple[int, int, int, int]:
        value = color.strip().lstrip("#")
        if len(value) == 6:
            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)
            return (r, g, b, 255)
        if len(value) == 8:
            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)
            a = int(value[6:8], 16)
            return (r, g, b, a)
        return (0, 0, 0, 170)

    @staticmethod
    def _wrap_text_to_width(text: str, font, max_width: int) -> str:
        """Word-wrap each line so it fits within max_width pixels."""
        probe_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        result_lines = []
        for paragraph in text.split("\n"):
            if not paragraph:
                result_lines.append("")
                continue
            words = paragraph.split(" ")
            current = ""
            for word in words:
                test = (current + " " + word).strip()
                w = probe_draw.textlength(test, font=font)
                if w <= max_width or not current:
                    current = test
                else:
                    result_lines.append(current)
                    current = word
            if current:
                result_lines.append(current)
        return "\n".join(result_lines)

    @staticmethod
    @lru_cache(maxsize=16)
    def _get_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        try:
            return ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            return ImageFont.load_default()

    def add_text_overlay(
        self,
        image,
        model_text,
        info_text,
        positive_text,
        negative_text,
        show_model,
        show_info,
        show_positive,
        show_negative,
        model_position,
        info_position,
        positive_position,
        negative_position,
        background_color,
        font_size,
        overlay_mode,
    ):
        top_text, bottom_text = self._compose_text(
            model_text, info_text, positive_text, negative_text,
            show_model, show_info, show_positive, show_negative,
            model_position, info_position, positive_position, negative_position,
        )
        if not top_text.strip() and not bottom_text.strip():
            return (image,)

        rgba = self._parse_rgba(background_color)
        font = self._get_font(font_size)
        pad_x = max(8, int(font_size * 0.30))
        pad_y = max(6, int(font_size * 0.25))
        img_w = image[0].shape[1]
        max_text_w = max(1, img_w - 2 * pad_x)

        def prepare_bar(text):
            if not text.strip():
                return None, 0, 0
            wrapped = self._wrap_text_to_width(text, font, max_text_w)
            probe_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            probe_draw = ImageDraw.Draw(probe_img)
            _, t, _, b = probe_draw.multiline_textbbox((0, 0), wrapped, font=font)
            text_h = max(1, b - t)
            bar_h = text_h + pad_y * 2
            text_y = max(0, (bar_h - text_h) // 2)
            return wrapped, bar_h, text_y

        top_wrapped, top_bar_h, top_text_y = prepare_bar(top_text)
        bottom_wrapped, bottom_bar_h, bottom_text_y = prepare_bar(bottom_text)
        output = []

        for sample in image:
            src = np.clip(255.0 * sample.cpu().numpy(), 0, 255).astype(np.uint8)
            src_pil = Image.fromarray(src)
            src_rgba = src_pil.convert("RGBA")
            W, H = src_rgba.size

            if overlay_mode:
                overlay = Image.new("RGBA", src_rgba.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                if top_wrapped:
                    draw.rectangle((0, 0, W, top_bar_h), fill=rgba)
                    draw.multiline_text((pad_x, top_text_y), top_wrapped, font=font, fill=(255, 255, 255, 255))
                if bottom_wrapped:
                    y0 = max(0, H - bottom_bar_h)
                    draw.rectangle((0, y0, W, H), fill=rgba)
                    draw.multiline_text((pad_x, y0 + bottom_text_y), bottom_wrapped, font=font, fill=(255, 255, 255, 255))
                composed = Image.alpha_composite(src_rgba, overlay)
            else:
                new_h = H + top_bar_h + bottom_bar_h
                composed = Image.new("RGBA", (W, new_h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(composed)
                if top_wrapped:
                    draw.rectangle((0, 0, W, top_bar_h), fill=rgba)
                    draw.multiline_text((pad_x, top_text_y), top_wrapped, font=font, fill=(255, 255, 255, 255))
                composed.paste(src_rgba, (0, top_bar_h))
                if bottom_wrapped:
                    y0 = top_bar_h + H
                    draw.rectangle((0, y0, W, new_h), fill=rgba)
                    draw.multiline_text((pad_x, y0 + bottom_text_y), bottom_wrapped, font=font, fill=(255, 255, 255, 255))

            if sample.shape[-1] == 4:
                out_arr = np.asarray(composed).astype(np.float32) / 255.0
            else:
                out_arr = np.asarray(composed.convert("RGB")).astype(np.float32) / 255.0

            output.append(torch.from_numpy(out_arr))

        return (torch.stack(output, dim=0).to(image.device, dtype=image.dtype),)


# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    #"Bubba Nodes": BubbaExample,
    "BubbaFilename": BubbaFilename,
    "BubbaKSampler": BubbaKSampler,
    "BubbaSaveImage": BubbaSaveImage,
    "BubbaAddOverlay": BubbaAddOverlay,
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    #"Bubba Nodes": "Bubba Example Node",
    "BubbaFilename": "Bubba Filename Builder",
    "BubbaKSampler": "Bubba KSampler",
    "BubbaSaveImage": "Bubba Save Image",
    "BubbaAddOverlay": "Bubba Add Text Overlay",
}
