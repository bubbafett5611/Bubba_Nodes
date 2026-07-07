from src.bubba_nodes.nodes.sampler_controls import BubbaSamplerControls


def test_sampler_controls_pass_values_through_with_native_types():
    result = BubbaSamplerControls.execute(30, 6.5, "euler_ancestral", "karras", 0.75)

    assert result.result == (30, 6.5, "euler_ancestral", "karras", 0.75)
    assert isinstance(result.result[0], int)
    assert isinstance(result.result[1], float)
    assert isinstance(result.result[4], float)


def test_sampler_controls_schema_matches_ksampler_controls():
    schema = BubbaSamplerControls.GET_SCHEMA()

    assert [item.id for item in schema.inputs] == ["steps", "cfg", "sampler_name", "scheduler", "denoise"]
    assert [item.io_type for item in schema.inputs] == ["INT", "FLOAT", "COMBO", "COMBO", "FLOAT"]
    assert [item.id for item in schema.outputs] == ["steps", "cfg", "sampler_name", "scheduler", "denoise"]
    assert [item.io_type for item in schema.outputs] == ["INT", "FLOAT", "COMBO", "COMBO", "FLOAT"]
