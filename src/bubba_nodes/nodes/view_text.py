from comfy_api.latest import IO, UI


class BubbaViewText(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="BubbaViewText",
            display_name="Bubba View Text",
            category="Bubba Nodes/Utilities",
            description="Displays connected or entered multiline text directly on the node and passes it through unchanged.",
            inputs=[
                IO.String.Input(
                    "text",
                    default="",
                    multiline=True,
                    force_input=True,
                    tooltip="Text to display on the node. Supports connected and multiline strings.",
                )
            ],
            outputs=[IO.String.Output("text")],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, text=""):
        value = str(text or "")
        return IO.NodeOutput(value, ui=UI.PreviewText(value))
