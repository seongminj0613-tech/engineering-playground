import pandas as pd
from pathlib import Path

def main():
    df = pd.read_csv("daily_interest_metrics.csv")
    df = df.sort_values("interest_score", ascending=False)

    out = Path("reports/latest_meeting_rank.md")
    out.parent.mkdir(exist_ok=True)

    lines = []
    lines.append("# 🧠 Agile Meeting Idea Ranking\n")
    lines.append("회의 종료 시점 자동 생성 랭킹\n")

    for i, row in df.head(5).iterrows():
        lines.append(f"## {len(lines)-1}. {row['date']}")
        lines.append(f"- 🔥 Interest Score: **{row['interest_score']}**")
        lines.append(f"- 💬 Mentions: {row['mentions']}")
        lines.append(f"- 🧩 Top Feature: `{row['top_feature']}`")
        lines.append(f"- ⚠️ Top Risk: `{row['top_risk']}`\n")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Meeting ranking written to {out}")

if __name__ == "__main__":
    main()