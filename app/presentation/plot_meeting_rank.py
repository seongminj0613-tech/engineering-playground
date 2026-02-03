import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    df = pd.read_csv("daily_interest_metrics.csv")
    df = df.sort_values("interest_score", ascending=False).head(7)

    plt.figure()
    plt.barh(df["date"], df["interest_score"])
    plt.title("Agile Meeting Productivity Ranking")
    plt.xlabel("Interest Score")
    plt.tight_layout()

    out = Path("reports/charts")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "meeting_rank.png"

    plt.savefig(path)
    plt.close()
    print(f"📊 Chart saved to {path}")

if __name__ == "__main__":
    main()