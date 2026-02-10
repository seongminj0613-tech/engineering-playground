from app.main import ensure_list, _to_float

def test_to_float_basic():
    assert _to_float(None) == 0.0
    assert _to_float("1.5") == 1.5
    assert _to_float(" 2 ") == 2.0
    assert _to_float("bad", 7) == 7.0
    assert _to_float(3) == 3.0

def test_ensure_list():
    assert ensure_list(None) == []
    assert ensure_list(["a"]) == ["a"]
    assert ensure_list("a") == ["a"]
    assert ensure_list("a,b") == ["a", "b"]
    assert ensure_list(123) == ["123"]