from .utils import clamp, safe_get
from .weights import MAX_RISK_PENALTY


def risk_penalty(idea: dict) -> float:
    reg = safe_get(idea, ["signals", "regulatory_risk"], 0)
    data_dep = safe_get(idea, ["signals", "data_dependency"], 0)

    raw = 0.7 * reg + 0.3 * data_dep
    penalty = (raw / 100) * MAX_RISK_PENALTY
    return clamp(penalty, 0, MAX_RISK_PENALTY)