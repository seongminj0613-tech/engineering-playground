def calc_confidence(row: dict) -> float:
    score = row.get("total_score", 0)
    signals = row.get("signals", {})
    evidence_cnt = len(row.get("evidence", []))

    base = score / 100

    stability = (
        signals.get("feasibility", 0)
        + signals.get("market_pull", 0)
    ) / 20

    ev_boost = min(evidence_cnt * 0.05, 0.25)

    conf = base * 0.5 + stability * 0.3 + ev_boost
    return round(min(conf, 0.99), 2)