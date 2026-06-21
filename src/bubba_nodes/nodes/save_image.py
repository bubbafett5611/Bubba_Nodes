import json
from pathlib import Path
from typing import Any, Mapping, cast

from comfy_api.latest import UI
from PIL import Image
from PIL.PngImagePlugin import PngInfo

try:
    import folder_paths
except Exception:  # pragma: no cover - only used inside Comfy runtime
    folder_paths = None

from ..models import BubbaMetadata, BubbaPipe
from ..models.pipe import resolve_pipe_value
from ..utils.checkpointing import checkpoint_display_name, checkpoint_short_hash
from ..utils.paths import sanitize_relative_save_prefix

# TODO(new-feature): Add sidecar JSON export option for non-PNG outputs to preserve metadata portability.
# TODO(new-node): Add a save manifest node that records every saved file path plus metadata digest for later audit/reload.


_DEFAULT_METADATA_DICT = BubbaMetadata().to_dict()
_METADATA_FIELDS_IGNORED_FOR_EMPTY_WARNING = {"save_prefix"}


class BubbaSaveImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "save_prefix": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Relative save prefix, usually Character/Scene. Leave blank to use metadata.save_prefix when metadata is connected.",
                    },
                ),
                "preview_only": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Enable to save as temp preview images instead of writing to output.",
                    },
                ),
                "save_workflow_metadata": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Enable to embed ComfyUI prompt/workflow metadata into saved PNGs, matching the default Save Image node behavior.",
                    },
                ),
                "save_a1111_metadata": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Enable to embed an A1111/Civitai-compatible PNG 'parameters' text block alongside Bubba metadata.",
                    },
                ),
            },
            "optional": {
                "pipe": ("BUBBA_PIPE", {"tooltip": "Optional incoming pipe containing the image and metadata to save."}),
                "images": ("IMAGE", {"tooltip": "Optional image override. Overrides pipe.image when connected."}),
                "metadata": (
                    "BUBBA_METADATA",
                    {"tooltip": "Optional metadata override. Overrides pipe.metadata when connected."},
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ("BUBBA_PIPE", "BUBBA_METADATA")
    RETURN_NAMES = ("pipe", "metadata")
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "Bubba Nodes/Image/Save"
    DESCRIPTION = "Saves images using save_prefix or metadata.save_prefix, with optional preview-only temp mode, optional ComfyUI workflow metadata embedding, optional A1111/Civitai-compatible parameters metadata, and embedded Bubba metadata for PNG files."

    @staticmethod
    def _is_default_metadata(metadata: BubbaMetadata) -> bool:
        return metadata.to_dict() == _DEFAULT_METADATA_DICT

    @staticmethod
    def _has_generation_metadata(metadata: BubbaMetadata) -> bool:
        metadata_dict = metadata.to_dict()
        return any(
            metadata_dict.get(key) != default_value
            for key, default_value in _DEFAULT_METADATA_DICT.items()
            if key not in _METADATA_FIELDS_IGNORED_FOR_EMPTY_WARNING
        )

    @classmethod
    def _metadata_input_warnings(cls, metadata_was_connected: bool, metadata: BubbaMetadata) -> list[str]:
        if not metadata_was_connected or cls._has_generation_metadata(metadata):
            return []
        return ["Bubba metadata input is connected but contains no model, prompt, sampler, seed, or LoRA data."]

    @staticmethod
    def _resolve_base_dir(image_type: str) -> Path:
        if folder_paths is not None:
            if image_type == "temp" and hasattr(folder_paths, "get_temp_directory"):
                return Path(folder_paths.get_temp_directory())
            if hasattr(folder_paths, "get_output_directory"):
                return Path(folder_paths.get_output_directory())
        return Path.cwd()

    @classmethod
    def _resolve_saved_image_path(cls, item: dict) -> Path | None:
        filename = str(item.get("filename", "")).strip()
        if not filename:
            return None
        subfolder = str(item.get("subfolder", "")).strip()
        image_type = str(item.get("type", "output")).strip() or "output"
        base_dir = cls._resolve_base_dir(image_type)
        return (base_dir / subfolder / filename).resolve()

    @staticmethod
    def _serialize_png_text_value(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value)
        except Exception:
            return None

    @classmethod
    def _build_png_text_entries(
        cls,
        metadata_json: str | None,
        save_workflow_metadata: bool,
        save_a1111_metadata: bool,
        metadata: BubbaMetadata,
        prompt: Any,
        extra_pnginfo: Mapping[str, Any] | None,
    ) -> dict[str, str]:
        entries: dict[str, str] = {}
        if save_workflow_metadata:
            prompt_text = cls._serialize_png_text_value(prompt)
            if prompt_text is not None:
                entries["prompt"] = prompt_text
            if isinstance(extra_pnginfo, Mapping):
                for key, value in extra_pnginfo.items():
                    text_value = cls._serialize_png_text_value(value)
                    if text_value is not None:
                        entries[str(key)] = text_value
        if metadata_json:
            entries["bubba_metadata"] = metadata_json
        if save_a1111_metadata:
            parameters_text = cls._build_a1111_parameters(metadata, prompt)
            if parameters_text:
                entries["parameters"] = parameters_text
        return entries

    @staticmethod
    def _format_a1111_sampler(metadata: BubbaMetadata) -> str:
        sampler = metadata.sampler_name.strip()
        scheduler = metadata.scheduler.strip()
        if not sampler:
            return ""
        if scheduler and scheduler.lower() not in {"normal", "simple"}:
            return f"{sampler}_{scheduler}"
        return sampler

    @classmethod
    def _find_checkpoint_name_in_prompt(cls, prompt: Any) -> str:
        if not isinstance(prompt, Mapping):
            return ""
        for node in prompt.values():
            if not isinstance(node, Mapping):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, Mapping):
                continue
            ckpt_name = str(inputs.get("ckpt_name", "") or "").strip()
            if ckpt_name:
                return ckpt_name
        return ""

    @classmethod
    def _resolve_a1111_model_fields(cls, metadata: BubbaMetadata, prompt: Any) -> tuple[str, str]:
        checkpoint_name = cls._find_checkpoint_name_in_prompt(prompt)
        model_name = metadata.model_name or checkpoint_display_name(checkpoint_name)
        model_hash = ""
        if checkpoint_name and folder_paths is not None and hasattr(folder_paths, "get_full_path_or_raise"):
            try:
                checkpoint_path = folder_paths.get_full_path_or_raise("checkpoints", checkpoint_name)
                model_hash = checkpoint_short_hash(checkpoint_path)
            except Exception:
                model_hash = ""
        return model_name, model_hash

    @classmethod
    def _build_a1111_parameters(cls, metadata: BubbaMetadata, prompt: Any) -> str:
        if not cls._has_generation_metadata(metadata):
            return ""

        lines = [metadata.positive_prompt]
        if metadata.negative_prompt:
            lines.append(f"Negative prompt: {metadata.negative_prompt}")

        fields: list[str] = []
        if metadata.steps > 0:
            fields.append(f"Steps: {metadata.steps}")
        sampler = cls._format_a1111_sampler(metadata)
        if sampler:
            fields.append(f"Sampler: {sampler}")
        if metadata.cfg > 0:
            fields.append(f"CFG scale: {metadata.cfg:g}")
        if metadata.seed > 0:
            fields.append(f"Seed: {metadata.seed}")
        model_name, model_hash = cls._resolve_a1111_model_fields(metadata, prompt)
        if model_hash:
            fields.append(f"Model hash: {model_hash}")
        if model_name:
            fields.append(f"Model: {model_name}")
        if metadata.clip_skip > 0:
            fields.append(f"Clip skip: {metadata.clip_skip}")

        if fields:
            lines.append(", ".join(fields))
        return "\n".join(lines).strip()

    @staticmethod
    def _png_text_entry_matches(existing_value: str | None, expected_value: str) -> bool:
        if existing_value == expected_value:
            return True
        if existing_value is None:
            return False
        try:
            return json.loads(existing_value) == json.loads(expected_value)
        except Exception:
            return False

    @staticmethod
    def _embed_metadata_in_png(image_path: Path, text_entries: Mapping[str, str]) -> None:
        if image_path.suffix.lower() != ".png" or not image_path.exists() or not text_entries:
            return

        with Image.open(image_path) as source:
            existing_text = {str(key): value for key, value in source.info.items() if isinstance(value, str)}
            if all(BubbaSaveImage._png_text_entry_matches(existing_text.get(str(key)), value) for key, value in text_entries.items()):
                return

            png_info = PngInfo()
            for key, value in existing_text.items():
                png_info.add_text(key, value)
            for key, value in text_entries.items():
                png_info.add_text(key, value)
            source.save(image_path, pnginfo=png_info)

    @classmethod
    def _try_embed_metadata_in_saved_images(cls, save_result: dict, text_entries: Mapping[str, str]) -> list[str]:
        # TODO(optimize): Parallelize metadata embedding when multiple images are saved in one batch.
        failed_paths: list[str] = []
        if not text_entries:
            return failed_paths
        for item in save_result.get("images", []):
            if not isinstance(item, dict):
                continue
            path = cls._resolve_saved_image_path(item)
            if path is None:
                continue
            try:
                cls._embed_metadata_in_png(path, text_entries)
            except Exception:
                failed_paths.append(str(path))
        return failed_paths

    def save_images(
        self,
        save_prefix="",
        preview_only=False,
        save_workflow_metadata=True,
        save_a1111_metadata=False,
        pipe=None,
        images=None,
        metadata=None,
        prompt=None,
        extra_pnginfo=None,
    ):
        source_pipe = BubbaPipe.coerce(pipe)
        resolved_images = resolve_pipe_value(images, source_pipe.image, "image")
        input_metadata = BubbaMetadata.coerce(metadata if metadata is not None else source_pipe.metadata)
        metadata_warnings = self._metadata_input_warnings(metadata is not None, input_metadata)
        normalized_metadata = input_metadata
        raw_save_prefix = (save_prefix or "").strip() or normalized_metadata.save_prefix or "Character/Scene"
        resolved_save_prefix = sanitize_relative_save_prefix(raw_save_prefix)
        normalized_metadata = normalized_metadata.updated(save_prefix=resolved_save_prefix)
        updated_pipe = source_pipe.updated(image=resolved_images, metadata=normalized_metadata)
        has_metadata = not self._is_default_metadata(normalized_metadata)
        metadata_json_compact = normalized_metadata.to_json(pretty=False) if has_metadata else None
        metadata_json_pretty = normalized_metadata.to_json(pretty=True) if has_metadata else None

        if preview_only:
            result = UI.PreviewImage(resolved_images, cls=cast(Any, None)).as_dict()
            if metadata_warnings:
                result["metadata_warnings"] = metadata_warnings
            if metadata_json_pretty is not None:
                result["metadata_text"] = metadata_json_pretty
            return {"ui": result, "result": (updated_pipe, normalized_metadata)}

        result = UI.ImageSaveHelper.get_save_images_ui(
            images=resolved_images,
            filename_prefix=resolved_save_prefix,
            cls=cast(Any, None),
        ).as_dict()
        png_text_entries = self._build_png_text_entries(
            metadata_json_compact,
            save_workflow_metadata,
            save_a1111_metadata,
            normalized_metadata,
            prompt,
            extra_pnginfo,
        )
        if png_text_entries:
            failed_metadata_paths = self._try_embed_metadata_in_saved_images(result, png_text_entries)
            if failed_metadata_paths:
                metadata_warnings.extend(f"Failed to embed PNG metadata in {path}" for path in failed_metadata_paths)
        if metadata_warnings:
            result["metadata_warnings"] = metadata_warnings
        if metadata_json_pretty is not None:
            result["metadata_text"] = metadata_json_pretty
        return {"ui": result, "result": (updated_pipe, normalized_metadata)}
