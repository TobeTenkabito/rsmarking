import os
import csv
import matplotlib.pyplot as plt
import numpy as np


class BenchmarkReporter:
    def __init__(self, output_dir="benchmark_results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.records = []
        # 设置全局绘图风格
        try:
            plt.style.use('seaborn-v0_8-muted')
        except:
            plt.style.use('ggplot')

    def add_record(self, test_type, tile_size, bands, latency_ms):
        self.records.append({
            "test_type": test_type,
            "tile_size": tile_size,
            "bands": bands,
            "latency_ms": latency_ms
        })

    def _setup_plot(self, title, xlabel, ylabel):
        plt.figure(figsize=(10, 6), dpi=120)
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.title(title, fontsize=14, fontweight='bold', pad=15)
        plt.xlabel(xlabel, fontsize=12)
        plt.ylabel(ylabel, fontsize=12)

    def save_csv(self):
        path = os.path.join(self.output_dir, "tile_render_report.csv")
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["test_type", "tile_size", "bands", "latency_ms"])
            writer.writeheader()
            writer.writerows(self.records)
        print(f"\n[System] Benchmark CSV saved: {path}")

    def plot_generic(self, test_type, x_key, title, filename):
        """通用绘图函数，处理过滤和排序逻辑"""
        data = [r for r in self.records if r["test_type"] == test_type]
        if not data: return

        # 排序确保折线图不会乱跳
        data.sort(key=lambda x: x[x_key])
        xs = [r[x_key] for r in data]
        ys = [r["latency_ms"] for r in data]

        self._setup_plot(title, x_key.replace('_', ' ').title(), "Latency (ms)")

        # 绘制主线与散点
        line, = plt.plot(xs, ys, marker='o', markersize=8, linewidth=2.5, color='#2c3e50', label='Mean Latency')
        # 添加阴影填充增强视觉效果
        plt.fill_between(xs, ys, color=line.get_color(), alpha=0.1)

        # 在点上标注数值
        for x, y in zip(xs, ys):
            plt.annotate(f'{y:.1f}', (x, y), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=9)

        plt.tight_layout()
        path = os.path.join(self.output_dir, filename)
        plt.savefig(path)
        plt.close()
        print(f"[Visual] {title} plot saved: {path}")

    def plot_tile_scaling(self):
        self.plot_generic("tile_scaling", "tile_size", "Tile Resolution Scaling Performance", "tile_scaling.png")

    def plot_band_scaling(self):
        self.plot_generic("band_scaling", "bands", "Spectral Band Scaling Performance", "band_scaling.png")

    def plot_stress(self):
        """针对计算压力测试的条形图"""
        data = [r for r in self.records if r["test_type"] == "stress"]
        if not data: return

        labels = [f"Bands:{r['bands']}" for r in data]
        ys = [r["latency_ms"] for r in data]

        self._setup_plot("Computational Stress Analysis (256px)", "Processing Scenario", "Latency (ms)")
        colors = plt.cm.viridis(np.linspace(0.3, 0.8, len(ys)))
        bars = plt.bar(labels, ys, color=colors, alpha=0.8, edgecolor='black', linewidth=1)

        plt.bar_label(bars, fmt='%.2f', padding=3)
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "stress_test.png"))
        plt.close()

    def plot_concurrency(self):
        self.plot_generic("concurrency", "bands", "Concurrency Saturation (Worker Scaling)", "concurrency_scaling.png")