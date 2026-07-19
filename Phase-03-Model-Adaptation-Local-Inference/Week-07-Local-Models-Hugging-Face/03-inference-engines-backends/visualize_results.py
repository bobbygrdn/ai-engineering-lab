#!/usr/bin/env python3
"""
Visualization script for llama.cpp benchmark results.
Generates charts showing performance metrics vs GPU layers.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import argparse

def load_and_process_data(csv_path):
    """Load and process the benchmark results CSV."""
    # Read the CSV, handling potential duplicate headers
    df = pd.read_csv(csv_path, comment='#')
    
    # Remove any rows that might be header duplicates
    df = df[df['run_date'] != 'run_date']
    
    # Convert numeric columns
    numeric_cols = ['n_gpu_layers', 'context_size', 'port', 'prompt_tokens', 
                   'generated_tokens', 'time_to_first_token', 'total_response_time', 
                   'tokens_per_sec', 'peak_vram']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Clean up text columns
    df['run_name'] = df['run_name'].astype(str).str.strip()
    df['result'] = df['result'].astype(str).str.strip()
    
    return df

def calculate_averages(df):
    """Calculate average metrics per GPU layer configuration."""
    # Group by run_name (which encodes GPU layers) and calculate means
    grouped = df.groupby('run_name').agg({
        'n_gpu_layers': 'first',  # Take first value as they're identical per group
        'time_to_first_token': 'mean',
        'total_response_time': 'mean', 
        'tokens_per_sec': 'mean',
        'peak_vram': 'mean',
        'prompt_tokens': 'mean',
        'generated_tokens': 'mean'
    }).reset_index()
    
    # Extract GPU layers from run_name for safety
    grouped['n_gpu_layers_extracted'] = grouped['run_name'].str.extract(r'(\d+)layers').astype(float)
    # Use extracted if available, otherwise use the column
    grouped['n_gpu_layers'] = grouped['n_gpu_layers_extracted'].fillna(grouped['n_gpu_layers'])
    grouped = grouped.drop('n_gpu_layers_extracted', axis=1)
    
    return grouped.sort_values('n_gpu_layers')

def create_visualizations(df_avg, output_dir):
    """Create and save visualization charts."""
    # Set style
    plt.style.use('seaborn-v0_8')
    sns.set_palette("husl")
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # 1. Time to First Token (Latency) vs GPU Layers
    plt.figure(figsize=(10, 6))
    plt.plot(df_avg['n_gpu_layers'], df_avg['time_to_first_token'], 'o-', linewidth=2, markersize=8)
    plt.xlabel('Number of GPU Layers', fontsize=12)
    plt.ylabel('Time to First Token (seconds)', fontsize=12)
    plt.title('Latency vs GPU Layers\nLower is Better', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'{output_dir}/latency_vs_gpu_layers.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Tokens per Second (Throughput) vs GPU Layers
    plt.figure(figsize=(10, 6))
    plt.plot(df_avg['n_gpu_layers'], df_avg['tokens_per_sec'], 's-', linewidth=2, markersize=8, color='green')
    plt.xlabel('Number of GPU Layers', fontsize=12)
    plt.ylabel('Tokens per Second', fontsize=12)
    plt.title('Throughput vs GPU Layers\nHigher is Better', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'{output_dir}/throughput_vs_gpu_layers.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Total Response Time vs GPU Layers
    plt.figure(figsize=(10, 6))
    plt.plot(df_avg['n_gpu_layers'], df_avg['total_response_time'], '^-', linewidth=2, markersize=8, color='red')
    plt.xlabel('Number of GPU Layers', fontsize=12)
    plt.ylabel('Total Response Time (seconds)', fontsize=12)
    plt.title('Total Response Time vs GPU Layers\nLower is Better', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'{output_dir}/response_time_vs_gpu_layers.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. Peak VRAM Usage vs GPU Layers (if data is meaningful)
    if df_avg['peak_vram'].notna().any() and (df_avg['peak_vram'] > 0).any():
        plt.figure(figsize=(10, 6))
        plt.plot(df_avg['n_gpu_layers'], df_avg['peak_vram'], 'd-', linewidth=2, markersize=8, color='orange')
        plt.xlabel('Number of GPU Layers', fontsize=12)
        plt.ylabel('Peak VRAM Usage (MB)', fontsize=12)
        plt.title('VRAM Usage vs GPU Layers\nImportant for 4GB GPU Limit', fontsize=14, fontweight='bold')
        plt.axhline(y=4096, color='r', linestyle='--', alpha=0.7, label='4GB Limit')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f'{output_dir}/vram_vs_gpu_layers.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # 5. Combined View: Latency and Throughput
    fig, ax1 = plt.subplots(figsize=(12, 8))
    
    color1 = 'blue'
    ax1.set_xlabel('Number of GPU Layers', fontsize=12)
    ax1.set_ylabel('Time to First Token (s)', color=color1, fontsize=12)
    line1 = ax1.plot(df_avg['n_gpu_layers'], df_avg['time_to_first_token'], 
                     color=color1, marker='o', linewidth=2, markersize=8, label='Latency')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True, alpha=0.3)
    
    ax2 = ax1.twinx()
    color2 = 'green'
    ax2.set_ylabel('Tokens per Second', color=color2, fontsize=12)
    line2 = ax2.plot(df_avg['n_gpu_layers'], df_avg['tokens_per_sec'], 
                     color=color2, marker='s', linewidth=2, markersize=8, label='Throughput')
    ax2.tick_params(axis='y', labelcolor=color2)
    
    # Add legend
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    
    plt.title('Latency and Throughput vs GPU Layers', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'{output_dir}/latency_throughput_combined.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 6. Bar chart showing all metrics normalized
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Normalize metrics for comparison (0-1 scale)
    df_norm = df_avg.copy()
    for col in ['time_to_first_token', 'total_response_time']:
        # Invert so higher is better for all metrics
        df_norm[f'{col}_inv'] = 1 / (df_norm[col] + 1e-8)  # Add small epsilon to avoid division by zero
    
    # Normalize each metric to 0-1 range
    metrics_to_plot = ['time_to_first_token_inv', 'total_response_time_inv', 'tokens_per_sec']
    if 'peak_vram' in df_norm.columns and df_norm['peak_vram'].notna().any():
        # For VRAM, lower is better, so we also invert it
        df_norm['vram_efficiency'] = 1 / (df_norm['peak_vram'] + 1e-8)
        metrics_to_plot.append('vram_efficiency')
    
    # Normalize each metric
    for metric in metrics_to_plot:
        if metric in df_norm.columns:
            min_val = df_norm[metric].min()
            max_val = df_norm[metric].max()
            if max_val > min_val:
                df_norm[f'{metric}_norm'] = (df_norm[metric] - min_val) / (max_val - min_val)
            else:
                df_norm[f'{metric}_norm'] = 0.5  # All same value
    
    # Prepare data for bar chart
    bar_width = 0.2
    x = np.arange(len(df_norm))
    
    # Plot each normalized metric
    colors = ['skyblue', 'lightgreen', 'salmon', 'gold']
    labels = ['Latency (inv)', 'Response Time (inv)', 'Throughput', 'VRAM Efficiency']
    
    for i, metric in enumerate(metrics_to_plot):
        norm_col = f'{metric}_norm'
        if norm_col in df_norm.columns:
            offset = (i - len(metrics_to_plot)/2) * bar_width + bar_width/2
            ax.bar(x + offset, df_norm[norm_col], bar_width, 
                   label=labels[i], color=colors[i % len(colors)], alpha=0.8)
    
    ax.set_xlabel('GPU Layers Configuration', fontsize=12)
    ax.set_ylabel('Normalized Performance (0-1, Higher is Better)', fontsize=12)
    ax.set_title('Normalized Performance Metrics vs GPU Layers', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([f'{int(layers)} Layers' for layers in df_norm['n_gpu_layers']])
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f'{output_dir}/normalized_metrics.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Print summary statistics
    print("\n=== SUMMARY STATISTICS ===")
    print(f"Configurations tested: {len(df_avg)}")
    print(f"GPU layers range: {df_avg['n_gpu_layers'].min()} - {df_avg['n_gpu_layers'].max()}")
    
    # Find best performing configurations
    best_latency = df_avg.loc[df_avg['time_to_first_token'].idxmin()]
    best_throughput = df_avg.loc[df_avg['tokens_per_sec'].idxmax()]
    best_response_time = df_avg.loc[df_avg['total_response_time'].idxmin()]
    
    print(f"\nBest Latency (lowest time to first token):")
    print(f"  {best_latency['n_gpu_layers']:.0f} GPU layers: {best_latency['time_to_first_token']:.4f}s")
    
    print(f"\nBest Throughput (highest tokens/sec):")
    print(f"  {best_throughput['n_gpu_layers']:.0f} GPU layers: {best_throughput['tokens_per_sec']:.2f} tokens/s")
    
    print(f"\nBest Response Time (lowest total time):")
    print(f"  {best_response_time['n_gpu_layers']:.0f} GPU layers: {best_response_time['total_response_time']:.4f}s")
    
    if 'peak_vram' in df_avg.columns and df_avg['peak_vram'].notna().any():
        lowest_vram = df_avg.loc[df_avg['peak_vram'].idxmin()]
        print(f"\nLowest VRAM Usage:")
        print(f"  {lowest_vram['n_gpu_layers']:.0f} GPU layers: {lowest_vram['peak_vram']:.0f} MB")

def main():
    parser = argparse.ArgumentParser(description='Visualize llama.cpp benchmark results')
    parser.add_argument('--input', '-i', type=str, default='combined_results.csv',
                        help='Path to input CSV file (default: combined_results.csv)')
    parser.add_argument('--output', '-o', type=str, default='visualizations',
                        help='Output directory for plots (default: visualizations)')
    
    args = parser.parse_args()
    
    print(f"Loading data from: {args.input}")
    df = load_and_process_data(args.input)
    
    print(f"Loaded {len(df)} benchmark results")
    print(f"Unique configurations: {df['run_name'].nunique()}")
    
    df_avg = calculate_averages(df)
    
    print(f"\nCreating visualizations in: {args.output}")
    create_visualizations(df_avg, args.output)
    
    print(f"\nVisualization complete! Charts saved to '{args.output}' directory.")
    print("Generated files:")
    print("  - latency_vs_gpu_layers.png")
    print("  - throughput_vs_gpu_layers.png") 
    print("  - response_time_vs_gpu_layers.png")
    if (df_avg['peak_vram'].notna().any() and (df_avg['peak_vram'] > 0).any()):
        print("  - vram_vs_gpu_layers.png")
    print("  - latency_throughput_combined.png")
    print("  - normalized_metrics.png")

if __name__ == "__main__":
    main()
