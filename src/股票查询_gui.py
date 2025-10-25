# 本程序由空游开发
# Copyright (c) 2025 空游
# SPDX-License-Identifier: MIT
import threading
from typing import Dict, Any
import tkinter as tk
from tkinter import ttk, messagebox

# 复用已实现的查询逻辑
from 股票查询 import validateStockCode, fetchQuoteByAkshare

try:
    from multi_source_fetcher import fetchQuoteMultiSource
except Exception:
    fetchQuoteMultiSource = None


def formatQuoteToText(quoteData: Dict[str, Any], stockCode: str) -> str:
    """将行情数据格式化为文本，便于在 GUI 中展示。"""
    lines = [
        "================= 当日基础行情 =================",
        f"股票代码: {stockCode}",
        f"股票名称: {quoteData['stockName']}",
        f"开盘价: {quoteData['openPrice']}",
        f"收盘价(参考): {quoteData['closePrice']}",
        f"最高价: {quoteData['highPrice']}",
        f"最低价: {quoteData['lowPrice']}",
        f"成交量: {quoteData['volume']}",
        "说明: 交易时段内‘收盘价’为最新价，收盘后等同当日收盘价。",
        "==============================================",
    ]
    # 来源标注
    if 'dataSource' in quoteData and 'fetchedAt' in quoteData:
        lines.append(f"数据来源: {quoteData['dataSource']} | 获取时间: {quoteData['fetchedAt']}")
    return "\n".join(lines)


class StockQueryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("股票行情查询工具 · 多源稳健版")
        try:
            self.root.geometry("680x420")
        except Exception:
            pass
        # 提升界面美观度：使用 ttk 风格与合理间距
        import tkinter.ttk as ttk
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.configure("TLabel", padding=6)
        self.style.configure("TButton", padding=6)
        self.style.configure("TEntry", padding=4)
        self.stockCodeVar = tk.StringVar()
        self.statusVar = tk.StringVar(value="请输入 6 位 A 股代码后点击查询")

        self.buildUi()

    def buildUi(self) -> None:
        padding = {"padx": 10, "pady": 10}

        inputFrame = ttk.Frame(self.root)
        inputFrame.pack(fill=tk.X, **padding)

        codeLabel = ttk.Label(inputFrame, text="股票代码：")
        codeLabel.pack(side=tk.LEFT)

        codeEntry = ttk.Entry(inputFrame, textvariable=self.stockCodeVar, width=20)
        codeEntry.pack(side=tk.LEFT, padx=6)
        codeEntry.bind("<Return>", lambda e: self.onQueryClick())

        queryButton = ttk.Button(inputFrame, text="查询", command=self.onQueryClick)
        queryButton.pack(side=tk.LEFT)

        statusLabel = ttk.Label(self.root, textvariable=self.statusVar, foreground="#666")
        statusLabel.pack(fill=tk.X, padx=10, pady=(0, 6))

        self.copyrightLabel = ttk.Label(self.root,
                                        text="© 2025 空游 · 本程序由空游开发 · 许可证：MIT License",
                                        anchor="w")
        self.copyrightLabel.pack(fill=tk.X, padx=10, pady=(0, 10))

        textFrame = ttk.Frame(self.root)
        textFrame.pack(fill=tk.BOTH, expand=True, **padding)

        self.resultText = tk.Text(textFrame, wrap=tk.NONE, height=16)
        self.resultText.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        yScrollbar = ttk.Scrollbar(textFrame, orient=tk.VERTICAL, command=self.resultText.yview)
        yScrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.resultText.configure(yscrollcommand=yScrollbar.set)

    def setStatus(self, text: str) -> None:
        self.statusVar.set(text)
        self.root.update_idletasks()

    def onQueryClick(self) -> None:
        stockCodeInput = self.stockCodeVar.get().strip()

        try:
            stockCode = validateStockCode(stockCodeInput)
        except Exception as e:
            messagebox.showerror("输入错误", str(e))
            return

        self.setStatus("正在查询，请稍候…")
        self.resultText.delete("1.0", tk.END)

        # 使用线程避免阻塞 UI
        threading.Thread(target=self.queryWorker, args=(stockCode,), daemon=True).start()

    def queryWorker(self, stockCode: str) -> None:
        try:
            if fetchQuoteMultiSource is not None:
                quoteData = fetchQuoteMultiSource(stockCode)
            else:
                quoteData = fetchQuoteByAkshare(stockCode)
            resultText = formatQuoteToText(quoteData, stockCode)
            self.resultText.insert(tk.END, resultText)
            self.setStatus("查询完成")
        except Exception as e:
            self.setStatus("查询失败")
            messagebox.showerror("查询失败", str(e))


def main() -> None:
    root = tk.Tk()
    app = StockQueryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()


def formatQuoteToText_legacy(quote: dict) -> str:
    lines = []
    lines.append(f"股票名称: {quote.get('stockName')}")
    lines.append(f"开盘价: {quote.get('openPrice')}")
    lines.append(f"收盘价: {quote.get('closePrice')}")
    lines.append(f"最高价: {quote.get('highPrice')}")
    lines.append(f"最低价: {quote.get('lowPrice')}")
    lines.append(f"成交量: {quote.get('volume')}")
    if 'dataSource' in quote and 'fetchedAt' in quote:
        lines.append(f"数据来源: {quote['dataSource']} | 获取时间: {quote['fetchedAt']}")
    return "\n".join(lines)