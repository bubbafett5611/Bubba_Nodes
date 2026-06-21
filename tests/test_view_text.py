from src.bubba_nodes.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS, BubbaViewText


def test_view_text_preserves_multiline_text_and_returns_ui_payload():
    text = "First line\nSecond line\n\nFourth line"

    result = BubbaViewText().view_text(text)

    assert result["result"] == (text,)
    assert result["ui"]["text"] == [text]


def test_view_text_coerces_none_to_empty_string():
    result = BubbaViewText().view_text(None)

    assert result["result"] == ("",)
    assert result["ui"]["text"] == [""]


def test_view_text_node_contract_and_registration():
    text_input = BubbaViewText.INPUT_TYPES()["required"]["text"]

    assert text_input[0] == "STRING"
    assert text_input[1]["multiline"] is True
    assert text_input[1]["forceInput"] is True
    assert BubbaViewText.RETURN_TYPES == ("STRING",)
    assert BubbaViewText.RETURN_NAMES == ("text",)
    assert BubbaViewText.FUNCTION == "view_text"
    assert BubbaViewText.CATEGORY == "Bubba Nodes/Utilities"
    assert BubbaViewText.OUTPUT_NODE is True
    assert NODE_CLASS_MAPPINGS["BubbaViewText"] is BubbaViewText
    assert NODE_DISPLAY_NAME_MAPPINGS["BubbaViewText"] == "Bubba View Text"
