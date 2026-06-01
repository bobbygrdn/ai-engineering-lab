"""Aggregate experiment results and produce plots.

Produces:
- aggregated_results.csv : one row per combo with pooled latency percentiles and mean recall
- per_combo_slow_queries.csv : worst queries per combo by median latency
- plots/recall_vs_avg_latency.png
- plots/recall_vs_p99_latency.png

Run:
    python analyze_results.py

Requires: pandas, numpy, matplotlib, seaborn
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

sns.set(style="whitegrid")

ROOT = Path('.')
PER_QUERY = ROOT / 'pinecone_per_query.csv'
RESULTS = ROOT / 'pinecone_results.csv'
OUT_DIR = ROOT / 'analysis_output'
OUT_DIR.mkdir(exist_ok=True)

if not PER_QUERY.exists() or not RESULTS.exists():
    raise SystemExit('Missing pinecone_per_query.csv or pinecone_results.csv in current directory')

pq = pd.read_csv(PER_QUERY)
res = pd.read_csv(RESULTS)

# Ensure expected columns exist
expected_combo_cols = ['M', 'ef_construction', 'ef_search']
for c in expected_combo_cols:
    if c not in pq.columns and c not in res.columns:
        raise SystemExit(f"Expected combo column '{c}' missing from CSVs")

# Normalize types
for c in expected_combo_cols:
    if c in pq.columns:
        pq[c] = pd.to_numeric(pq[c], errors='coerce')
    if c in res.columns:
        res[c] = pd.to_numeric(res[c], errors='coerce')

# Aggregate pooled per-combo latencies from per-query CSV
combo_group = pq.groupby(['M', 'ef_construction', 'ef_search'])['latency_ms']
combo_stats = combo_group.agg(['mean', 'median', lambda x: np.percentile(x,95), lambda x: np.percentile(x,99)])
combo_stats = combo_stats.rename(columns={'mean':'avg_latency_ms','median':'median_latency_ms','<lambda_0>':'p95_latency_ms','<lambda_1>':'p99_latency_ms'})
combo_stats = combo_stats.reset_index()

# Aggregate recall across trials from results CSV
recall_group = res.groupby(['M','ef_construction','ef_search'])['average_recall_at_k']
recall_stats = recall_group.agg(['mean','std','count']).reset_index().rename(columns={'mean':'mean_recall_at_k','std':'std_recall','count':'n_trials'})

# Per-query recall: median recall per query across trials, then per-combo summary across queries
if 'recall_at_k' in pq.columns:
    pq['recall_at_k'] = pd.to_numeric(pq['recall_at_k'], errors='coerce')
    per_query_recall = pq.groupby(['M','ef_construction','ef_search','query_id'])['recall_at_k'].median().reset_index()
    # per-combo summary across queries
    combo_recall_stats = per_query_recall.groupby(['M','ef_construction','ef_search'])['recall_at_k'].agg([
        ('mean_query_recall','mean'),
        ('median_query_recall','median'),
        ( 'p10_query_recall', lambda x: np.percentile(x,10)),
        ( 'p90_query_recall', lambda x: np.percentile(x,90))
    ]).reset_index()
else:
    combo_recall_stats = pd.DataFrame()

# Merge latency stats with recall stats
agg = combo_stats.merge(recall_stats, on=['M','ef_construction','ef_search'], how='left')
if not combo_recall_stats.empty:
    agg = agg.merge(combo_recall_stats, on=['M','ef_construction','ef_search'], how='left')

# Save aggregated results
agg_file = OUT_DIR / 'aggregated_results.csv'
agg.to_csv(agg_file, index=False)
print('Wrote', agg_file)

# Per-combo: compute per-query median latency across trials and save worst queries
pq_q = pq.groupby(['M','ef_construction','ef_search','query_id'])['latency_ms'].median().reset_index()
# For each combo, pick top 20 slowest queries
slow_rows = []
for (M, efc, ef), grp in pq_q.groupby(['M','ef_construction','ef_search']):
    top = grp.sort_values('latency_ms', ascending=False).head(20)
    top['M'] = M
    top['ef_construction'] = efc
    top['ef_search'] = ef
    slow_rows.append(top)
if slow_rows:
    slow_df = pd.concat(slow_rows, ignore_index=True)
    slow_file = OUT_DIR / 'per_combo_slow_queries.csv'
    slow_df.to_csv(slow_file, index=False)
    print('Wrote', slow_file)

# Plot: recall vs avg latency
plt.figure(figsize=(8,6))
recall_col = 'mean_query_recall' if 'mean_query_recall' in agg.columns else 'mean_recall_at_k'
ax = plt.gca()
# color mapping by M
Ms_unique = sorted(agg['M'].dropna().unique())
palette = dict(zip(Ms_unique, sns.color_palette('tab10', n_colors=max(1, len(Ms_unique)))))

# marker sizes: prefer index_vector_count, else fallback to n_trials
if 'index_vector_count' in agg.columns and agg['index_vector_count'].notna().any():
    iv = pd.to_numeric(agg['index_vector_count'], errors='coerce').fillna(0.0).astype(float)
    min_s, max_s = 50, 300
    sizes = ((iv - iv.min()) / (iv.max() - iv.min() + 1e-9)) * (max_s - min_s) + min_s
    agg['marker_size'] = sizes
elif 'n_trials' in agg.columns and agg['n_trials'].notna().any():
    nt = agg['n_trials'].fillna(1).astype(float)
    min_s, max_s = 50, 300
    sizes = ((nt - nt.min()) / (nt.max() - nt.min() + 1e-9)) * (max_s - min_s) + min_s
    agg['marker_size'] = sizes
else:
    agg['marker_size'] = 120

for _, row in agg.iterrows():
    x = row['avg_latency_ms']
    y = row.get(recall_col, np.nan)
    mval = row['M']
    color = palette.get(mval, 'gray')
    # compute error bars
    ms = row.get('marker_size', 120)
    if recall_col == 'mean_query_recall' and 'p10_query_recall' in row and 'p90_query_recall' in row:
        lower = 0.0 if pd.isna(row['p10_query_recall']) else max(0.0, y - row['p10_query_recall'])
        upper = 0.0 if pd.isna(row['p90_query_recall']) else max(0.0, row['p90_query_recall'] - y)
        ax.errorbar(x, y, yerr=[[lower],[upper]], fmt='o', color=color, ecolor=color, capsize=3, ms=ms/10)
    else:
        # use std_recall when available
        yerr = row.get('std_recall', 0.0)
        if pd.isna(yerr):
            yerr = 0.0
        ax.errorbar(x, y, yerr=yerr, fmt='o', color=color, ecolor=color, capsize=3, ms=ms/10)
    label = f"M{int(row.M)}_efc{int(row.ef_construction)}_ef{int(row.ef_search)}"
    ax.text(x*1.01, y, label, fontsize=8)
ax.set_xlabel('Average latency (ms)')
ax.set_ylabel(f'{recall_col}')
ax.set_title('Recall vs Average Latency (pooled)')
# adjust x limits and ticks (step 5)
if 'avg_latency_ms' in agg.columns:
    xmin = float(agg['avg_latency_ms'].min())
    xmax = float(agg['avg_latency_ms'].max())
    pad = max(1.0, (xmax - xmin) * 0.05)
    ax.set_xlim(max(0.0, xmin - pad), xmax + pad)
    start = int(np.floor(max(0.0, xmin - pad)))
    end = int(np.ceil(xmax + pad))
    ax.set_xticks(np.arange(start, end + 1, 5))
plt.tight_layout()
out1 = OUT_DIR / 'recall_vs_avg_latency.png'
plt.savefig(out1, dpi=200)
print('Wrote', out1)
plt.close()

plt.figure(figsize=(8,6))
recall_col = 'mean_query_recall' if 'mean_query_recall' in agg.columns else 'mean_recall_at_k'
ax = plt.gca()
Ms_unique = sorted(agg['M'].dropna().unique())
palette = dict(zip(Ms_unique, sns.color_palette('tab10', n_colors=max(1, len(Ms_unique)))))
for _, row in agg.iterrows():
    x = row['p99_latency_ms']
    y = row.get(recall_col, np.nan)
    mval = row['M']
    color = palette.get(mval, 'gray')
    if recall_col == 'mean_query_recall' and 'p10_query_recall' in row and 'p90_query_recall' in row:
        lower = 0.0 if pd.isna(row['p10_query_recall']) else max(0.0, y - row['p10_query_recall'])
        upper = 0.0 if pd.isna(row['p90_query_recall']) else max(0.0, row['p90_query_recall'] - y)
        ms = row.get('marker_size', 120)
        ax.errorbar(x, y, yerr=[[lower],[upper]], fmt='o', color=color, ecolor=color, capsize=3, ms=ms/10)
    else:
        yerr = row.get('std_recall', 0.0)
        if pd.isna(yerr):
            yerr = 0.0
        ms = row.get('marker_size', 120)
        ax.errorbar(x, y, yerr=yerr, fmt='o', color=color, ecolor=color, capsize=3, ms=ms/10)
    label = f"M{int(row.M)}_efc{int(row.ef_construction)}_ef{int(row.ef_search)}"
    ax.text(x*1.01, y, label, fontsize=8)
ax.set_xlabel('P99 latency (ms)')
ax.set_ylabel(f'{recall_col}')
ax.set_title('Recall vs P99 Latency (pooled)')
plt.tight_layout()
out2 = OUT_DIR / 'recall_vs_p99_latency.png'
plt.savefig(out2, dpi=200)
print('Wrote', out2)
plt.close()

# Combined plot: side-by-side comparison of trial-mean recall vs per-query median recall
plt.figure(figsize=(14,6))

# left: trial-mean recall (from results CSV)
ax1 = plt.subplot(1,2,1)
Ms_unique = sorted(agg['M'].dropna().unique())
palette = dict(zip(Ms_unique, sns.color_palette('tab10', n_colors=max(1, len(Ms_unique)))))
if 'mean_recall_at_k' in agg.columns:
    for _, row in agg.iterrows():
        x = row['avg_latency_ms']
        y = row.get('mean_recall_at_k', np.nan)
        yerr = row.get('std_recall', 0.0)
        if pd.isna(yerr):
            yerr = 0.0
        color = palette.get(row['M'], 'gray')
        ax1.errorbar(x, y, yerr=yerr, fmt='o', color=color, ecolor=color, capsize=3)
        ax1.text(x*1.01, y, f"M{int(row.M)}_efc{int(row.ef_construction)}_ef{int(row.ef_search)}", fontsize=8)
    ax1.set_title('Trial-mean recall@k vs Avg Latency')
    ax1.set_xlabel('Average latency (ms)')
    ax1.set_ylabel('Trial-mean recall@k')
else:
    ax1.text(0.5, 0.5, 'mean_recall_at_k not available', ha='center')

# right: per-query median recall (across trials)
ax2 = plt.subplot(1,2,2)
if 'mean_query_recall' in agg.columns:
    for _, row in agg.iterrows():
        x = row['avg_latency_ms']
        y = row.get('mean_query_recall', np.nan)
        lower = 0.0 if pd.isna(row.get('p10_query_recall')) else max(0.0, y - row['p10_query_recall'])
        upper = 0.0 if pd.isna(row.get('p90_query_recall')) else max(0.0, row['p90_query_recall'] - y)
        color = palette.get(row['M'], 'gray')
        ax2.errorbar(x, y, yerr=[[lower],[upper]], fmt='o', color=color, ecolor=color, capsize=3)
        ax2.text(x*1.01, y, f"M{int(row.M)}_efc{int(row.ef_construction)}_ef{int(row.ef_search)}", fontsize=8)
    ax2.set_title('Per-query median recall (across trials) vs Avg Latency')
    ax2.set_xlabel('Average latency (ms)')
    ax2.set_ylabel('Median per-query recall@k')
else:
    ax2.text(0.5, 0.5, 'mean_query_recall not available', ha='center')

plt.tight_layout()
out3 = OUT_DIR / 'combined_recall_vs_avg_latency.png'
plt.savefig(out3, dpi=200)
plt.close()
print('Wrote', out3)

print('Analysis complete. Outputs in', OUT_DIR)