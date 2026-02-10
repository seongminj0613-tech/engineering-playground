from app.main import to_cards

def test_to_cards_smoke_empty():
    cards = to_cards([])
    assert isinstance(cards, list)
    assert len(cards) == 0

def test_to_cards_smoke_minimal_row():
    raw = [{"title": "t", "summary": "s", "feasibility": "0.7", "confidence": 0.3}]
    cards = to_cards(raw)
    assert len(cards) == 1
    assert cards[0].title == "t"