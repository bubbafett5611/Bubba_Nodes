from nodes import CheckpointLoaderSimple


class BubbaCheckpointLoader:
    @classmethod
    def INPUT_TYPES(s):
        return CheckpointLoaderSimple.INPUT_TYPES()

    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "checkpoint_name")
    FUNCTION = "load_checkpoint_with_name"
    CATEGORY = "Bubba Nodes"
    DESCRIPTION = "Loads a checkpoint and also outputs the selected checkpoint name as text."

    def load_checkpoint_with_name(self, ckpt_name):
        model, clip, vae = CheckpointLoaderSimple().load_checkpoint(ckpt_name)
        return (model, clip, vae, str(ckpt_name))
