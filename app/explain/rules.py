from __future__ import annotations

SIGNAL_LABELS = {
    "clarity": "명확성",
    "feasibility": "실행가능성",
    "market_pull": "시장당김",
    "evidence": "근거성",
    "specificity": "구체성",
    "novelty": "참신성",
    "freshness": "신선도",
    "trend_boost": "트렌드부스트",
}

# 0~1 스케일 가정
THRESH = {
    "strong": 0.70,
    "ok": 0.55,
    "weak": 0.40,
}

NEXT_STEP_RECIPES = {
    "clarity": [
        "한 문장 문제정의(Who/Problem/Outcome)로 다시 정리하기",
        "입력/출력/성공지표(KPI) 3개를 명시하기",
        "범위(out of scope) 3개를 못 박기",
    ],
    "evidence": [
        "검증 가능한 근거 3개 확보(기사/리서치/유저인터뷰/내부로그)",
        "가정 목록을 '측정 가능한 문장'으로 바꾼 뒤 우선순위 매기기",
        "최소 실험(1~2일) 설계: 측정지표/성공조건/중단조건 정의",
    ],
    "feasibility": [
        "MVP 스코프를 1/3로 축소(핵심 플로우만 남기기)",
        "필수 의존성(데이터/권한/API/모델) 체크리스트 작성",
        "리스크 3개에 대한 대응(대안/우회/롤백) 시나리오 만들기",
    ],
    "market_pull": [
        "타겟 페르소나 1개 고정 + '지금 돈/시간을 쓰는 이유' 적기",
        "대체재(기존 방식/경쟁) 3개 비교표 만들기",
        "인터뷰 질문 5개로 3명만 빠르게 검증하기",
    ],
}

RISK_RECIPES = {
    "clarity": "요구사항/범위가 흔들리면 구현은 빨라도 제품화가 어려움",
    "evidence": "근거가 약하면 우선순위/투자/설득 단계에서 밀릴 가능성",
    "feasibility": "의존성(데이터/권한/운영) 이슈로 일정이 폭발할 가능성",
    "market_pull": "사용자 페인이 약하면 '있으면 좋음'에서 끝날 가능성",
}