from __future__ import annotations
from typing import Dict, List, Tuple

def index_by_id(rows: List[dict], id_key: str = "idea_id") -> Dict[str, dict]:
    m: Dict[str, dict] = {}
    for r in rows:
        iid = str(r.get(id_key) or "")
        if not iid:
            continue
        m[iid] = r
    return m

def apply_rank_and_delta(today_rows: List[dict], prev_rows: List[dict]) -> List[dict]:
    """
    today_rows: 이미 total_score 기준으로 정렬돼 있다고 가정 (rank_scores 결과)
    prev_rows: 전날 snapshot rows (정렬 여부 상관없음)
    """
    prev = index_by_id(prev_rows, "idea_id")

    out: List[dict] = []
    for rank, r in enumerate(today_rows, start=1):
        iid = str(r.get("idea_id") or "")
        pr = prev.get(iid)

        score_today = float(r.get("total_score", 0) or 0)
        score_prev = float(pr.get("total_score", 0) or 0) if pr else 0.0

        rank_prev = int(pr.get("rank", 0) or 0) if pr else 0

        rr = dict(r)
        rr["rank"] = rank
        rr["rank_prev"] = rank_prev
        rr["rank_delta"] = (rank_prev - rank) if rank_prev else 0  # +면 상승
        rr["score_prev"] = round(score_prev, 2)
        rr["score_delta"] = round(score_today - score_prev, 2)

        out.append(rr)
    return out

def top_movers(rows: List[dict], k: int = 5) -> Tuple[List[dict], List[dict]]:
    up = sorted(rows, key=lambda x: (x.get("rank_delta", 0), x.get("score_delta", 0)), reverse=True)[:k]
    down = sorted(rows, key=lambda x: (x.get("rank_delta", 0), x.get("score_delta", 0)))[:k]
    return up, down