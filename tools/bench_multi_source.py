# 本程序由空游开发
# Copyright (c) 2025 空游
# SPDX-License-Identifier: MIT
import time
import statistics
from collections import Counter
import sys
import os

# 将项目根目录和src加入模块搜索路径
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, 'src')
for p in (ROOT_DIR, SRC_DIR):
    if p not in sys.path:
        sys.path.append(p)

CODES = [
    "600519",  # 贵州茅台
    "000001",  # 平安银行
    "601318",  # 中国平安
    "300750",  # 宁德时代
    "600036",  # 招商银行
]

ROUND_TRIPS = 3  # 每只股票查询次数


def resolve_fetch():
    """解析可用的多源获取函数，优先使用CLI同源实现。"""
    try:
        from 股票查询 import fetchQuoteMultiSource
        return fetchQuoteMultiSource
    except Exception:
        pass
    try:
        from multi_source_fetcher import fetchQuoteMultiSource
        return fetchQuoteMultiSource
    except Exception:
        pass
    try:
        from multi_source_fetcher import MultiSourceClient
        client = MultiSourceClient()
        for attr in ("fetch", "get", "get_quote", "query"):
            if hasattr(client, attr):
                method = getattr(client, attr)
                return lambda code: method(code)
        raise AttributeError("MultiSourceClient未找到兼容方法(fetch/get/get_quote/query)")
    except Exception as e:
        raise RuntimeError(f"无法解析多源获取函数: {e}")


def main():
    fetch = resolve_fetch()
    latencies = []
    sources = []
    errors = 0

    for code in CODES:
        for _ in range(ROUND_TRIPS):
            t0 = time.perf_counter()
            try:
                quote = fetch(code)
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000.0)
                src = quote.get("dataSource") or quote.get("source") or "unknown"
                sources.append(src)
            except Exception as e:
                errors += 1
                latencies.append(None)
                print(f"[ERROR] code={code}: {e}")
            time.sleep(0.2)

    valid_latencies = [x for x in latencies if x is not None]
    print("\n=== 多源查询基准评估 ===")
    print(f"样本数: {len(latencies)} | 失败数: {errors}")
    if valid_latencies:
        print(f"平均延迟(ms): {statistics.mean(valid_latencies):.2f}")
        print(f"中位延迟(ms): {statistics.median(valid_latencies):.2f}")
        try:
            p95 = statistics.quantiles(valid_latencies, n=20)[18]
        except Exception:
            p95 = sorted(valid_latencies)[int(len(valid_latencies)*0.95)-1]
        print(f"P95延迟(ms): {p95:.2f}")
    else:
        print("无有效延迟样本")
    cnt = Counter(sources)
    if cnt:
        print("数据源分布:")
        for src, n in cnt.items():
            print(f" - {src}: {n}")
    else:
        print("无数据源样本")


if __name__ == "__main__":
    main()

