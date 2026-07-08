import json
import pathlib
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

CSV_PATH = pathlib.Path("evaluation_results.csv")
OUT_IMG  = pathlib.Path("evaluation_metrics.png")


def load_data(csv_path: pathlib.Path) -> pd.DataFrame:
    """Load the CSV and keep only the rows that contain numeric scores."""
    df = pd.read_csv(csv_path)

    numeric_df = df[pd.to_numeric(df["sample_id"], errors="coerce").notnull()].copy()
    numeric_df["sample_id"] = numeric_df["sample_id"].astype(int)

    for col in ["faithfulness", "answer_relevancy", "context_precision"]:
        numeric_df[col] = pd.to_numeric(numeric_df[col], errors="coerce")
    return numeric_df


def compute_summary(df: pd.DataFrame) -> dict:
    """Return mean and std‑dev for each metric."""
    summary = {}
    for metric in ["faithfulness", "answer_relevancy", "context_precision"]:
        summary[metric] = {
            "mean": df[metric].mean(),
            "std":  df[metric].std(),
        }
    return summary


def plot_metrics(summary: dict, out_path: pathlib.Path) -> None:
    """Create a bar‑chart with error bars (±1 σ) and save as PNG."""
    metrics = list(summary.keys())
    means   = [summary[m]["mean"] for m in metrics]
    stds    = [summary[m]["std"]  for m in metrics]

    sns.set_style("whitegrid")
    plt.figure(figsize=(6, 4))

    ax = plt.gca()
    bars = ax.bar(metrics, means, yerr=stds, capsize=5,
                  color=["#4c72b0", "#55a868", "#c44e52"])

    for bar, mean in zip(bars, means):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2,
                height + 0.02,
                f"{mean:.3f}",
                ha="center", va="bottom", fontsize=10)

    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("RAG Evaluation – Average Metrics")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()


def main(argv: list[str] | None = None) -> int:
    """Entry point – prints a short summary and writes the PNG."""
    csv_path = CSV_PATH
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    df = load_data(csv_path)
    if df.empty:
        print("CSV contains no numeric rows – nothing to plot.", file=sys.stderr)
        return 1

    summary = compute_summary(df)

    plot_metrics(summary, OUT_IMG)
    print(f"\n✅  Chart saved to {OUT_IMG.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())