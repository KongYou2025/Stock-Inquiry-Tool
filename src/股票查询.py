# 本程序由空游开发
# Copyright (c) 2025 空游
# SPDX-License-Identifier: MIT
import argparse
from typing import Dict, Any
from datetime import datetime



def validateStockCode(stockCode: str) -> str:
    """校验并标准化股票代码为 6 位数字字符串。"""
    normalizedCode = stockCode.strip()
    if not normalizedCode.isdigit():
        raise ValueError("股票代码应为纯数字。")
    if len(normalizedCode) != 6:
        # 一些输入可能不是 6 位，采用左侧补零的方式标准化
        normalizedCode = normalizedCode.zfill(6)
    return normalizedCode




def fetchQuoteByAkshare(stockCode: str):
    # 优先使用多源实现，保持旧函数名以兼容 CLI/GUI 现有调用
    try:
        from multi_source_fetcher import fetchQuoteMultiSource
        return fetchQuoteMultiSource(stockCode)
    except Exception:
        pass
    # 回退到原 Akshare 单源实现
    from akshare import stock_zh_a_spot_em
    df = stock_zh_a_spot_em()
    df["代码"] = df["代码"].astype(str).str.zfill(6)
    row = df[df["代码"] == stockCode].iloc[0].to_dict()
    return {
        "stockName": row.get("名称") or "未知名称",
        "openPrice": float(row.get("今开") or 0),
        "closePrice": float((row.get("最新价") or row.get("收盘") or 0) or 0),
        "highPrice": float(row.get("最高") or 0),
        "lowPrice": float(row.get("最低") or 0),
        "volume": int(float(row.get("成交量") or row.get("成交量(手)") or 0)),
        "dataSource": "akshare",
        "fetchedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def printBasicQuote(quote: dict):
    print(f"股票名称: {quote.get('stockName')}")
    print(f"开盘价: {quote.get('openPrice')}")
    print(f"收盘价: {quote.get('closePrice')}")
    print(f"最高价: {quote.get('highPrice')}")
    print(f"最低价: {quote.get('lowPrice')}")
    print(f"成交量: {quote.get('volume')}")
    if 'dataSource' in quote and 'fetchedAt' in quote:
        print(f"数据来源: {quote['dataSource']} | 获取时间: {quote['fetchedAt']}")
    print("版权声明：本程序由空游开发 · 许可证：MIT License")


def main():
    parser = argparse.ArgumentParser(description="股票查询CLI · 多源稳健版")
    parser.add_argument("--code", required=True, help="股票代码，例如 600519")
    args = parser.parse_args()
    from multi_source_fetcher import fetchQuoteMultiSource
    quote = fetchQuoteMultiSource(args.code)
    printBasicQuote(quote)


if __name__ == "__main__":
    main()

