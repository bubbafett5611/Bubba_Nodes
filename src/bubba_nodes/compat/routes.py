from __future__ import annotations


def prompt_server_instance():
    try:
        from server import PromptServer  # type: ignore
    except Exception:
        return None
    return getattr(PromptServer, "instance", None)


def route_table():
    instance = prompt_server_instance()
    return getattr(instance, "routes", None) if instance is not None else None
