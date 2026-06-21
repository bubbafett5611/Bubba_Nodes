class BubbaViewText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "forceInput": True,
                        "tooltip": "Text to display on the node. Supports connected and multiline strings.",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "view_text"
    CATEGORY = "Bubba Nodes/Utilities"
    OUTPUT_NODE = True
    DESCRIPTION = "Displays connected or entered multiline text directly on the node and passes it through unchanged."

    def view_text(self, text=""):
        value = str(text or "")
        return {"ui": {"text": [value]}, "result": (value,)}
