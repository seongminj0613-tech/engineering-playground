import re
from typing import List, Dict, Any

def _sentences(text: str) -> List[str]:
    # 아주 단순 문장 분리 (한글/영문 섞여도 대충 동작)
    if not text:
        return []
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[\.\?\!])\s+|(?<=다\.)\s+|(?<=요\.)\s+|(?<=함\.)\s+", text)
    parts = [p.strip() for p in parts if p and len(p.strip()) >= 12]
    return parts

def build_evidence_trace(meeting_text: str, idea: Dict[str, Any], max_items: int = 3) -> List[str]:
    """
    회의 원문에서 '아이디어 제목/태그' 기반으로 문장 1~3개 뽑기.
    """
    sents = _sentences(meeting_text)
    title = str(idea.get("title") or idea.get("name") or idea.get("idea") or "").strip()
    tags = idea.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]

    # 키워드 후보
    kws = []
    for t in [title] + list(tags):
        t = str(t).strip()
        if not t:
            continue
        # 너무 짧은 건 제외
        if len(t) < 2:
            continue
        kws.append(t)

    kws = list(dict.fromkeys(kws))[:8]  # 중복 제거 + 최대 8개

    scored = []
    for sent in sents:
        score = 0
        for kw in kws:
            if kw.lower() in sent.lower():
                score += 2
        # “해야/필요/문제/리스크/자동/개선/대응” 같은 의사결정 신호 가중치
        if re.search(r"(필요|문제|리스크|위험|자동|개선|대응|확인|검토|해야)", sent):
            score += 1
        if score > 0:
            scored.append((score, sent))

    scored.sort(key=lambda x: (-x[0], -len(x[1])))

    traces = []
    for _, sent in scored[:max_items]:
        traces.append(f'회의 인용: "{sent[:140]}"')

    if not traces:
        traces = ['회의 인용을 찾지 못함 → 업로드 문서에 해당 키워드가 있는지 확인 필요']

    return traces[:max_items]

def build_risk_analysis(idea_row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    A(문서 업로드)의 리스크: 근거 부족/메타 부족/신뢰도 낮음 같은 기본 리스크는 무조건 생성
    """
    risks = []
    evc = int(idea_row.get("evidence_count", 0) or 0)

    # 1) 근거 부족은 가장 중요
    if evc <= 0:
        risks.append({
            "type": "evidence_missing",
            "description": "회의 원문 근거 인용이 부족해 랭킹 신뢰도가 낮을 수 있음",
            "impact": "high",
            "mitigation": "회의 원문에서 핵심 문장 1~3개를 evidence_trace로 자동 추출/표시"
        })

    # 2) 메타데이터 부족
    unknown_fields = 0
    for k in ["market", "impact", "risk"]:
        v = idea_row.get(k)
        if v is None or str(v).strip().lower() in ["unknown", "none", ""]:
            unknown_fields += 1
    if unknown_fields >= 2:
        risks.append({
            "type": "metadata_missing",
            "description": "market/impact/risk 메타가 비어 있어 판단 근거가 약해질 수 있음",
            "impact": "medium",
            "mitigation": "idea 카드에 market/impact/risk 최소값(옵션/드롭다운) 입력 지원"
        })

    return risks or [{
        "type": "no_major_risk",
        "description": "현재 기준에서 큰 리스크 없음",
        "impact": "low",
        "mitigation": "근거/메타 유지"
    }]

def build_next_actions(idea_row: Dict[str, Any]) -> List[str]:
    actions = []
    evc = int(idea_row.get("evidence_count", 0) or 0)
    conf = str(idea_row.get("confidence", "") or "").lower()

    if evc <= 0:
        actions.append("[HIGH] 회의 원문 근거 1~3개 확보(인용 자동 추출/표시)")
    actions.append("[MED] 30분 PoC 스케치(입출력/데이터/성공조건 정의)")
    actions.append("[MED] 사용자(팀) 1명에게 필요성 확인 질문 3개 던지기")

    if conf == "low":
        actions.append("[LOW→MED] 외부 근거 1개(링크/기사/문서) 추가하여 신뢰도 개선")

    return actions[:4]

def build_confidence(idea_row: Dict[str, Any]) -> str:
    evc = int(idea_row.get("evidence_count", 0) or 0)
    sc = int(idea_row.get("signal_count", 0) or 0)
    ms = float(idea_row.get("market_signal", 0) or 0)

    # HIGH
    if evc >= 2 and sc >= 6 and ms > 0.2:
        return "high"
    # MEDIUM
    if evc >= 1 and sc >= 4:
        return "medium"
    # LOW
    if evc == 0:
        return "low"
    return "medium"