import matplotlib.pyplot as plt
from pathlib import Path

OUTPUT_DIR = Path("reports/charts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def plot_idea_rank(cards, top_n: int = 10):
    # priority 기준 상위 N개
    top_cards = sorted(
        cards,
        key=lambda c: c.scores.priority,
        reverse=True
    )[:top_n]

    labels = [c.title for c in top_cards]
    scores = [c.scores.priority for c in top_cards]

    plt.figure(figsize=(10, 6))
    plt.barh(labels[::-1], scores[::-1])
    plt.xlabel("Priority Score")
    plt.title("Top Ideas Ranking")

    out_path = OUTPUT_DIR / "idea_rank.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

    print(f"[OK] Saved idea rank chart -> {out_path}")