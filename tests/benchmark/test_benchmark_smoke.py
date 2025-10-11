from benchmarks.throughput import run_benchmark


def test_benchmark_smoke():
    stats = run_benchmark(n=50, repeat=1)
    assert stats["tasks"] == 50
    assert stats["avg_s"] >= 0.0
