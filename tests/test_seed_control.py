from src.bubba_nodes.nodes.seed_control import BubbaSeedControl


def test_seed_control_outputs_seed():
    seed, info = BubbaSeedControl.execute(987654321).result

    assert seed == 987654321
    assert info == "Seed: 987654321"


def test_seed_control_schema_has_native_after_generate_control():
    schema = BubbaSeedControl.GET_SCHEMA()
    seed_input = next(item for item in schema.inputs if item.id == "seed")

    assert [item.id for item in schema.inputs] == ["seed"]
    assert [item.id for item in schema.outputs] == ["seed", "info"]
    assert seed_input.control_after_generate is True
    assert seed_input.min == 0
    assert seed_input.max == 0xFFFFFFFFFFFFFFFF
