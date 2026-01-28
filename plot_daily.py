import pandas as pd
import matplotlib.pyplot as plt

PATH = "daily_interest_metrics.csv"

def main():
    df = pd.read_csv(PATH)

    # date 정렬
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # interest_score 라인 차트
    plt.figure()
    plt.plot(df["date"], df["interest_score"], marker="o")
    plt.title("Daily Interest Score")
    plt.xlabel("date")
    plt.ylabel("interest_score")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    # 패턴 점유율 라인 차트 (generator/hybrid/agent)
    pattern_cols = [c for c in df.columns if c.startswith("share_")]
    if pattern_cols:
        plt.figure()
        for c in pattern_cols:
            plt.plot(df["date"], df[c], marker="o", label=c)
        plt.title("Architecture Share Over Time")
        plt.xlabel("date")
        plt.ylabel("share")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    main()