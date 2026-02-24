def build_explain(signals: dict) -> list[str]:
    explain = []

    if signals.get("market_pull", 0) > 7:
        explain.append("시장 수요 근거가 존재함")

    if signals.get("feasibility", 0) > 7:
        explain.append("구현 난이도가 현실적임")

    if signals.get("novelty", 0) > 7:
        explain.append("아이디어 신선도가 높음")

    if signals.get("evidence", 0) > 5:
        explain.append("근거 문서 기반 검증됨")

    if signals.get("trend_boost", 0) > 5:
        explain.append("최근 트렌드와 방향 일치")

    if not explain:
        explain.append("기본 점수 기반 선정")

    return explain

def build_evidence(idea: dict) -> list[str]:
    ev = []

    for e in idea.get("evidence", []):
        text = e.get("text") or e.get("summary")
        if text:
            ev.append(text[:120])

    return ev[:3]