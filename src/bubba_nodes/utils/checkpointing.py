def checkpoint_display_name(ckpt_name: str) -> str:
    raw = str(ckpt_name or "").strip()
    if not raw:
        return ""

    leaf = raw.replace("\\", "/").rsplit("/", 1)[-1]
    if "." in leaf:
        leaf = leaf.rsplit(".", 1)[0]
    return leaf
