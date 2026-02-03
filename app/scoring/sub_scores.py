# app/scoring/sub_scores.py

from .utils import clamp, safe_get


def score_feasibility(idea: dict) -> float:
    team_fit = safe_get(idea, ["signals", "team_fit"], 0)
    tech = safe_get(idea, ["signals", "tech_readiness"], 0)
    data_dep = safe_get(idea, ["signals", "data_dependency"], 0)

    score = 0.45 * team_fit + 0.45 * tech + 0.10 * (100 - data_dep)
    return clamp(score)


def score_market(idea: dict) -> float:
    market = safe_get(idea, ["signals", "market_size"], 0)
    comp = safe_get(idea, ["signals", "competitor_count"], 0)

    comp_penalty = clamp((comp / 20) * 100)
    score = 0.75 * market + 0.25 * (100 - comp_penalty)
    return clamp(score)


def score_trend(idea: dict) -> float:
    mentions = safe_get(idea, ["signals", "news_mentions"], 0)
    search = safe_get(idea, ["signals", "search_trend"], 0)

    mentions_score = clamp((mentions / 30) * 100)
    score = 0.55 * search + 0.45 * mentions_score
    return clamp(score)