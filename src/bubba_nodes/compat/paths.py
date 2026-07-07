from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _folder_paths():
    try:
        import folder_paths  # type: ignore

        return folder_paths
    except Exception:
        return None


def get_filename_list(folder_name: str) -> list[str]:
    folder_paths = _folder_paths()
    if folder_paths is None or not hasattr(folder_paths, "get_filename_list"):
        return []
    return list(folder_paths.get_filename_list(folder_name))


def get_input_directory() -> Path:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "get_input_directory"):
        return Path(folder_paths.get_input_directory())
    return Path.cwd()


def get_output_directory() -> Path:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "get_output_directory"):
        return Path(folder_paths.get_output_directory())
    return Path.cwd()


def get_temp_directory() -> Path:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "get_temp_directory"):
        return Path(folder_paths.get_temp_directory())
    return Path.cwd()


def get_user_directory() -> Path:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "get_user_directory"):
        return Path(folder_paths.get_user_directory())
    return Path.cwd() / "user"


def filter_files_content_types(files: Iterable[str], content_types: Iterable[str]) -> list[str]:
    folder_paths = _folder_paths()
    file_list = list(files)
    if folder_paths is not None and hasattr(folder_paths, "filter_files_content_types"):
        return list(folder_paths.filter_files_content_types(file_list, list(content_types)))
    return file_list


def input_image_files() -> list[str]:
    input_dir = get_input_directory()
    try:
        files = [name for name in os.listdir(input_dir) if os.path.isfile(input_dir / name)]
    except Exception:
        return []
    return sorted(filter_files_content_types(files, ["image"]))


def get_annotated_filepath(path: str) -> str:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "get_annotated_filepath"):
        return str(folder_paths.get_annotated_filepath(path))
    return path


def exists_annotated_filepath(path: str) -> bool:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "exists_annotated_filepath"):
        return bool(folder_paths.exists_annotated_filepath(path))
    return Path(path).exists()


def get_full_path_or_raise(folder_name: str, filename: str) -> str:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "get_full_path_or_raise"):
        return str(folder_paths.get_full_path_or_raise(folder_name, filename))
    path = Path(filename)
    if not path.exists():
        raise FileNotFoundError(filename)
    return str(path)


def get_full_path(folder_name: str, filename: str) -> Path | None:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "get_full_path"):
        resolved = folder_paths.get_full_path(folder_name, filename)
        if resolved:
            return Path(resolved)
    return None


def get_folder_paths(folder_name: str) -> list[Path]:
    folder_paths = _folder_paths()
    if folder_paths is not None and hasattr(folder_paths, "get_folder_paths"):
        try:
            return [Path(path) for path in folder_paths.get_folder_paths(folder_name)]
        except KeyError:
            # Optional model categories are not present in every ComfyUI setup.
            return []
    return []
