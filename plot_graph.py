import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import os
from datetime import datetime

PATH = "graph_edges_snapshot.csv"

def node_type(name: str) -> str:
    s = name.lower().strip()
    
# 케이스 노드 규칙 (case_1, case_10 등)
    if s.startswith("case_"):
        return "case"

    # 패턴 노드 규칙 (너 데이터에서 이미 이 형태)
    if "generator" in s or "hybrid/rag" in s or "agent" == s:
        return "pattern"

    # 리스크 규칙 (지금은 hallucination만 있지만 확장 가능)
    risk_keywords = {"hallucination", "privacy", "security", "compliance", "latency", "cost"}
    if s in risk_keywords:
        return "risk"

    # 그 외는 기능(feature)로 간주
    return "feature"

def hop_neighbors(graph, start, depth: int):
    """depth=1이면 1-hop, depth=2이면 2-hop까지 포함"""
    visited = {start}
    frontier = {start}
    for _ in range(depth):
        nxt = set()
        for u in frontier:
            nxt.update(graph.neighbors(u))
        nxt -= visited
        visited |= nxt
        frontier = nxt
    visited.discard(start)
    return visited


def main():
    df = pd.read_csv(PATH)

    # 컬럼명 자동 탐지
    cols = [c.lower() for c in df.columns]
    if "source" in cols and "target" in cols:
        source_col = df.columns[cols.index("source")]
        target_col = df.columns[cols.index("target")]
    elif "from" in cols and "to" in cols:
        source_col = df.columns[cols.index("from")]
        target_col = df.columns[cols.index("to")]
    else:
        source_col, target_col = df.columns[0], df.columns[1]

    # 그래프 구성
    G = nx.DiGraph()
    for _, r in df.iterrows():
        s = str(r[source_col])
        t = str(r[target_col])
        G.add_edge(s, t)

    

    # ✅ 1단계 핵심: 연결 수(중요도) 기반 노드 크기
    deg = dict(G.degree())  # in+out degree
    UG = G.to_undirected()
    # B) Centrality (병목 / 중요 노드)
    bet = nx.betweenness_centrality(G)
    pr  = nx.pagerank(G)

    TOP_CENT_N = 10
    top_bet = sorted(bet.items(), key=lambda x: x[1], reverse=True)[:TOP_CENT_N]
    top_pr  = sorted(pr.items(),  key=lambda x: x[1], reverse=True)[:TOP_CENT_N]
    
    def safe_node_type(n: str) -> str:
        try:
            return node_type(n)
        except Exception:
            return "unknown"
    
    TOP_N = 5
    top_hubs = sorted(deg.items(), key=lambda x: x[1], reverse=True)[:TOP_N]
    
    
    # 2) Risk Nodes & Neighbors
    risk_nodes = [n for n in G.nodes() if safe_node_type(n) == "risk"]
    risk_links = {}
    for r in risk_nodes:
        neigh = list(UG.neighbors(r))
        neigh_sorted = sorted(neigh, key=lambda n: deg.get(n, 0), reverse=True)
        risk_links[r] = neigh_sorted
        
        risk_edge_1hop = set()
        risk_edge_2hop = set()

        for r in risk_nodes:
            hop1 = set(hop_neighbors(UG, r, depth=1))
            hop2 = set(hop_neighbors(UG, r, depth=2))

            zone1 = hop1 | {r}
            zone2 = hop2 | {r}

            # 1-hop zone 내부 edge들
            for u, v in G.edges():
                if u in zone1 and v in zone1:
                    risk_edge_1hop.add((u, v))

            # 2-hop zone 내부 edge들 (1-hop은 제외)
            for u, v in G.edges():
                if (u in zone2 and v in zone2) and ((u, v) not in risk_edge_1hop):
                    risk_edge_2hop.add((u, v))

        risk_edge_1hop = list(risk_edge_1hop)
        risk_edge_2hop = list(risk_edge_2hop)

    # 3) Feature → Connected Cases
    feature_nodes = [n for n in G.nodes() if safe_node_type(n) == "feature"]
    feature_case_map = {}
    for f in feature_nodes:
        cases = [n for n in UG.neighbors(f) if safe_node_type(n) == "case"]

        def case_index(name):
            try:
                return int(name.split("_")[1])
            except Exception:
                return 9999

        feature_case_map[f] = sorted(cases, key=case_index)
          # -------------------------
    # 4) Risk Impact Zone (1-hop / 2-hop)
    # -------------------------


    risk_impact = {}
    for r in risk_nodes:
        hop1 = hop_neighbors(UG, r, depth=1)
        hop2 = hop_neighbors(UG, r, depth=2)

        # 보기 좋게 degree 높은 순 정렬
        hop1_sorted = sorted(hop1, key=lambda n: deg.get(n, 0), reverse=True)
        hop2_sorted = sorted(hop2, key=lambda n: deg.get(n, 0), reverse=True)

        risk_impact[r] = {
            "hop1": hop1_sorted,
            "hop2": hop2_sorted,
            "hop1_count": len(hop1_sorted),
            "hop2_count": len(hop2_sorted),
        }
    impact_scores = {}  # node -> score

    for r, info in risk_impact.items():
        # 가중치: 1-hop=2점, 2-hop=1점
        for n in info["hop1"]:
            impact_scores[n] = impact_scores.get(n, 0) + 2
        for n in info["hop2"]:
            impact_scores[n] = impact_scores.get(n, 0) + 1

    # 상위 N개
    TOP_SCORE_N = 10
    impact_top = sorted(
        impact_scores.items(), 
        key=lambda x: x[1], 
        reverse=True
        )[:TOP_SCORE_N]
    
    impact_top_nodes = [n for (n, score) in impact_top]
    

    # 리포트 저장 (Markdown)
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("reports", exist_ok=True)

    md_path = os.path.join("reports", f"{today}_graph_insights.md")
    md_latest = os.path.join("reports", "latest_graph_insights.md")

    lines = []
    lines.append(f"# Graph Insights ({today})\n\n")

    lines.append("## 1) Top Hub Nodes (by Degree)\n")
    for i, (n, d) in enumerate(top_hubs, 1):
        lines.append(f"- {i}. **{n}** — degree={d}, type={safe_node_type(n)}\n")

    lines.append("\n## 2) Risk Nodes & Direct Neighbors\n")
    if not risk_nodes:
        lines.append("- (no risk nodes found)\n")
    else:
        for r, neigh in risk_links.items():
            text = ", ".join(neigh) if neigh else "(none)"
            lines.append(f"- **{r}** → {text}\n")

    lines.append("\n## 3) Feature → Connected Cases\n")
    if not feature_nodes:
        lines.append("- (no feature nodes found)\n")
    else:
        for f, cases in feature_case_map.items():
            text = ", ".join(cases) if cases else "(none)"
            lines.append(f"- **{f}** → cases({len(cases)}): {text}\n")
            
    lines.append("\n## 4) Risk Impact Zone (1-hop / 2-hop)\n")
    if not risk_nodes:
        lines.append("- (no risk nodes found)\n")
    else:
        for r, info in risk_impact.items():
            lines.append(f"- **{r}**\n")
            h1 = ", ".join(info["hop1"]) if info["hop1"] else "(none)"
            h2 = ", ".join(info["hop2"]) if info["hop2"] else "(none)"
            lines.append(f"  - 1-hop({info['hop1_count']}): {h1}\n")
            lines.append(f"  - 2-hop({info['hop2_count']}): {h2}\n")
            
    lines.append("\n## 5) Impact Score Top Nodes\n")

    if not impact_top:
        lines.append("- (no impact nodes found)\n")
    else:
        for i, (node, score) in enumerate(impact_top, 1):
            lines.append(
                f"- {i}. **{node}** — score={score}, degree={deg.get(node, 0)}, type={safe_node_type(node)}\n"
            )
    
    lines.append("\n## 6) Centrality (Betweenness / PageRank)\n")

    lines.append("### 6.1 Betweenness Centrality (Top 10)\n")
    for i, (n, v) in enumerate(top_bet, 1):
        lines.append(f"- {i}. **{n}** — betweenness={v:.4f}, degree={deg.get(n,0)}, type={safe_node_type(n)}\n")

    lines.append("\n### 6.2 PageRank (Top 10)\n")
    for i, (n, v) in enumerate(top_pr, 1):
        lines.append(f"- {i}. **{n}** — pagerank={v:.4f}, degree={deg.get(n,0)}, type={safe_node_type(n)}\n")

            
    content = "".join(lines)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    with open(md_latest, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[INSIGHTS] saved -> {md_path}")
    print(f"[INSIGHTS] saved -> {md_latest}")
    # =========================

    # 레이아웃
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, k=0.8, seed=42)
    
    # =========================
# ✅ STEP 6) Risk propagation edge highlight (1-hop / 2-hop)
# =========================

    risk_edge_1hop = set()
    risk_edge_2hop = set()
    
    for r in risk_nodes:
        
        hop1 = set(hop_neighbors(UG, r, depth=1))
        hop2 = set(hop_neighbors(UG, r, depth=2))

        zone1 = hop1 | {r}
        zone2 = hop2 | {r}

    # 1-hop zone 내부 edge들
        for u, v in G.edges():
            if u in zone1 and v in zone1:
                risk_edge_1hop.add((u, v))

    # 2-hop zone 내부 edge들 (1-hop은 제외)
        for u, v in G.edges():
            if (u in zone2 and v in zone2) and ((u, v) not in risk_edge_1hop):
                risk_edge_2hop.add((u, v))

    risk_edge_1hop = list(risk_edge_1hop)
    risk_edge_2hop = list(risk_edge_2hop)

# 기본 edge (리스크 존 제외)
    base_edges = [
        e for e in G.edges()
        if e not in set(risk_edge_1hop) and e not in set(risk_edge_2hop)
]

    min_size = 450
    scale = 220
    node_sizes = [min_size + scale * deg.get(n, 0) for n in G.nodes()]

    color_map = {
        "pattern": "red",
        "case": "blue",
        "feature": "green",
        "risk": "orange",
    }

    # ✅ 안전하게 (예상 못한 타입이면 gray)
    node_colors = [color_map.get(node_type(n), "gray") for n in G.nodes()]

    # 그리기
    # 🎯 Impact Top 노드 강조용 스타일 분리
    normal_nodes = [n for n in G.nodes() if n not in impact_top_nodes]
    highlight_nodes = impact_top_nodes

    # 기존 노드 사이즈 / 컬러 매핑 재사용
    normal_sizes = [
        node_sizes[list(G.nodes()).index(n)] for n in normal_nodes
    ]
    normal_colors = [
        node_colors[list(G.nodes()).index(n)] for n in normal_nodes
    ]

    highlight_sizes = [
        node_sizes[list(G.nodes()).index(n)] * 1.4 for n in highlight_nodes
    ]
    highlight_colors = [
        node_colors[list(G.nodes()).index(n)] for n in highlight_nodes
    ]

    # 일반 노드
    nx.draw_networkx_nodes(
        G,
        pos,
        nodelist=normal_nodes,
        node_size=normal_sizes,
        node_color=normal_colors,
        alpha=0.85
    )

    # ⭐ Impact Top 노드 (강조)
    nx.draw_networkx_nodes(
        G,
        pos,
        nodelist=highlight_nodes,
        node_size=highlight_sizes,
        node_color=highlight_colors,
        edgecolors="black",
        linewidths=2.5
    )
    nx.draw_networkx_edges(
        G,
        pos,
        edgelist=base_edges,
        edge_color="#CCCCCC",
        alpha=0.2,
        width=1.0
    )

    # 2-hop 리스크 zone edge (주황색)
    nx.draw_networkx_edges(
        G,
        pos,
        edgelist=risk_edge_2hop,
        edge_color="orange",
        width=3.0,
        alpha=0.8
    )

    # 1-hop 리스크 zone edge (빨간색 강조)
    nx.draw_networkx_edges(
        G,
        pos,
        edgelist=risk_edge_1hop,
        width=5.0,
        alpha=0.95
    )
    nx.draw_networkx_labels(G, pos, font_size=9)

    from matplotlib.patches import Patch
    legend_items = [
        Patch(label="pattern", facecolor=color_map["pattern"]),
        Patch(label="case", facecolor=color_map["case"]),
        Patch(label="feature", facecolor=color_map["feature"]),
        Patch(label="risk", facecolor=color_map["risk"]),
    ]
    plt.legend(handles=legend_items, loc="lower left")

    plt.title("Reference Graph (Size=Degree, Color=Type)")
    plt.axis("off")
    plt.tight_layout()

    os.makedirs("snapshots", exist_ok=True)
    filename = f"snapshots/reference_graph_{today}.png"
    latest_png = "snapshots/reference_graph_latest.png"

    plt.savefig(filename, dpi=200)
    plt.savefig(latest_png, dpi=200)

    print(f"📸 Graph saved -> {filename}")
    print(f"📸 Graph saved -> {latest_png}")

    plt.show()


if __name__ == "__main__":
    main()