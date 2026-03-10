import numpy as np
import time
import concurrent.futures
from tests.unit.services.tile_rendering.utils.tile_benchmark_utils import benchmark_render
from tests.unit.services.tile_rendering.utils.benchmark_reporter import BenchmarkReporter
reporter = BenchmarkReporter()


def test_render_binary_mask():
    data = np.random.choice([0, 1], size=(1, 256, 256)).astype(np.float32)
    t = benchmark_render(data)
    latency = t * 1000
    print(f"\nBinary mask render: {latency:.2f} ms")
    reporter.add_record("data_type", 256, 1, latency)


def test_render_multiband():
    data = np.random.rand(4, 256, 256).astype(np.float32) * 5000
    t = benchmark_render(data)
    latency = t * 1000
    print(f"\nMultiband render: {latency:.2f} ms")
    reporter.add_record("data_type", 256, 4, latency)


def test_render_high_dynamic_range():
    data = np.random.rand(3, 256, 256).astype(np.float32) * 10000
    t = benchmark_render(data)
    latency = t * 1000
    print(f"\nHigh dynamic range render: {latency:.2f} ms")
    reporter.add_record("data_type", 256, 3, latency)


def test_render_normalized():
    data = np.random.uniform(-1, 1, (3, 256, 256)).astype(np.float32)
    t = benchmark_render(data)
    latency = t * 1000
    print(f"\nNormalized data render: {latency:.2f} ms")
    reporter.add_record("data_type", 256, 3, latency)


def test_tile_size_scaling():
    sizes = [128, 256, 512]
    for s in sizes:
        data = np.random.rand(3, s, s).astype(np.float32) * 1000
        t = benchmark_render(data)
        latency = t * 1000
        pixels = s * s
        print(f"\nTile {s}x{s} ({pixels} px) render: {latency:.2f} ms")
        reporter.add_record("tile_scaling", s, 3, latency)


def test_band_scaling():
    bands = [1, 3, 4, 8]
    for b in bands:
        data = np.random.rand(b, 256, 256).astype(np.float32) * 1000
        t = benchmark_render(data)
        latency = t * 1000
        print(f"\nBands {b} render: {latency:.2f} ms")
        reporter.add_record("band_scaling", 256, b, latency)


def test_real_remote_sensing():
    """
    模拟真实遥感数据类型
    """
    tests = {
        "RGB": (3, 256),
        "RGB+NIR": (4, 256),
        "PlanetScope": (8, 256),
        "Sentinel2": (13, 256)
    }
    for name, (b, s) in tests.items():
        data = np.random.rand(b, s, s).astype(np.float32) * 10000
        t = benchmark_render(data)
        latency = t * 1000
        print(f"\n{name} render: {latency:.2f} ms")
        reporter.add_record("remote_sensing", s, b, latency)


def test_render_stress():
    """
    模拟服务器连续渲染大量 tile
    """
    data = np.random.rand(3, 256, 256).astype(np.float32) * 1000
    runs = 500
    t = benchmark_render(data, runs=runs)
    latency = t * 1000
    print(f"\nStress test ({runs} tiles): {latency:.2f} ms per tile")
    reporter.add_record("stress", 256, 3, latency)


def test_generate_report():
    reporter.save_csv()
    reporter.plot_tile_scaling()
    reporter.plot_band_scaling()
    print("\nBenchmark report generated.")


def test_render_extreme_resolutions():
    """测试从 1k 到 4k 的单瓦片渲染"""
    sizes = [1024, 2048, 4096]
    for s in sizes:
        try:
            data = np.random.rand(3, s, s).astype(np.float32)
            t = benchmark_render(data)
            latency = t * 1000
            print(f"Extreme Resolution {s}x{s}: {latency:.2f} ms")
            reporter.add_record("extreme_res", s, 3, latency)
        except MemoryError:
            print(f"Memory Error at resolution: {s}x{s}")
            break


def test_hyperspectral_scaling():
    """模拟高光谱遥感数据"""
    band_counts = [30, 64, 128, 242]
    for b in band_counts:
        data = np.random.rand(b, 256, 256).astype(np.float32)
        t = benchmark_render(data)
        latency = t * 1000
        print(f"Hyperspectral {b} bands: {latency:.2f} ms")
        reporter.add_record("hyperspectral", 256, b, latency)


def test_processing_chain_complexity():
    """模拟计算指数、NDVI、色彩映射等场景"""
    scenarios = {
        "Simple_Read": lambda d: d[:3],
        "NDVI_Logic": lambda d: ((d[3] - d[0]) / (d[3] + d[0] + 1e-5))[np.newaxis, :],
        "Full_Stretch": lambda d: np.clip((d[:3] - 500) / 2000 * 255, 0, 255).astype(np.uint8)
    }
    data = np.random.rand(4, 256, 256).astype(np.float32) * 5000
    for name, func in scenarios.items():
        try:
            runs = 10
            start = time.perf_counter()
            for _ in range(runs):
                processed = func(data)
                _ = benchmark_render(processed, runs=1)
            end = time.perf_counter()
            latency = ((end - start) / runs) * 1000
            print(f"Scenario {name}: {latency:.2f} ms")
            reporter.add_record("stress", 256, processed.shape[0], latency)
        except Exception as e:
            print(f"Scenario {name} failed: {str(e)}")


def test_concurrent_load_saturation():
    """模拟高并发请求，观察 CPU 调度损耗"""
    worker_counts = [2, 4, 8, 16]
    data = np.random.rand(3, 256, 256).astype(np.float32)

    def single_worker_task():
        return benchmark_render(data, runs=20)
    print("\nStarting Concurrency Saturation Tests...")
    for w in worker_counts:
        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=w) as executor:
            futures = [executor.submit(single_worker_task) for _ in range(w * 5)]
            concurrent.futures.wait(futures)

        total_time = (time.perf_counter() - start) * 1000
        avg_per_request = total_time / (w * 5)
        print(f"Concurrency {w} workers: Avg {avg_per_request:.2f}ms/tile")
        reporter.add_record("concurrency", 256, w, avg_per_request)


def test_generate_advanced_report():
    """
    保存并可视化性能边界
    """
    if not hasattr(reporter, 'records') or not reporter.records:
        print("No records to report.")
        return
    reporter.save_csv()
    plot_methods = [
        m for m in dir(reporter)
        if m.startswith('plot_') and m not in ['plot_generic']
    ]
    for method_name in plot_methods:
        method = getattr(reporter, method_name)
        try:
            method()
            print(f"Successfully executed {method_name}")
        except Exception as e:
            print(f"Failed to execute {method_name}: {e}")
    print("\nAdvanced Boundary Report Generated.")
