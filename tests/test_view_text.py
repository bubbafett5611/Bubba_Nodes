from src.bubba_nodes.nodes import BubbaViewText


def test_view_text_preserves_multiline_text_and_returns_ui_payload():
    text = "First line\nSecond line\n\nFourth line"

    result = BubbaViewText().execute(text)

    assert result.result == (text,)
    assert tuple(result.ui.as_dict()["text"]) == (text,)


def test_view_text_coerces_none_to_empty_string():
    result = BubbaViewText().execute(None)

    assert result.result == ("",)
    assert tuple(result.ui.as_dict()["text"]) == ("",)


def test_view_text_node_contract_and_registration():
    schema = BubbaViewText.GET_SCHEMA()
    text_input = schema.inputs[0]
    assert text_input.io_type == "STRING"
    assert text_input.multiline is True
    assert text_input.force_input is True
    assert [output.id for output in schema.outputs] == ["text"]
    assert schema.category == "Bubba Nodes/Utilities"
    assert schema.is_output_node is True
