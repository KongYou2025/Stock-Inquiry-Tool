# 本程序由空游开发
# Copyright (c) 2025 空游
# SPDX-License-Identifier: MIT
import time
import threading
import concurrent.futures
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse
import urllib.robotparser as robotparser
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except Exception:
    Retry = None


class SessionFactory:
    def __init__(self, totalRetries: int = 3, backoffFactor: float = 0.3) -> None:
        self.totalRetries = totalRetries
        self.backoffFactor = backoffFactor

    def build(self, headers: Optional[Dict[str, str]] = None) -> requests.Session:
        s = requests.Session()
        if headers:
            s.headers.update(headers)
        if Retry is not None:
            retry = Retry(total=self.totalRetries,
                          connect=self.totalRetries,
                          read=self.totalRetries,
                          status=self.totalRetries,
                          backoff_factor=self.backoffFactor,
                          status_forcelist=[429, 500, 502, 503, 504],
                          allowed_methods=["GET", "HEAD"],
                          respect_retry_after_header=True)
            adapter = HTTPAdapter(max_retries=retry)
            s.mount("http://", adapter)
            s.mount("https://", adapter)
        return s


class RobotsChecker:
    def __init__(self, userAgent: str = "StockQueryBot") -> None:
        self.userAgent = userAgent
        self.cache: Dict[str, robotparser.RobotFileParser] = {}
        self.lock = threading.Lock()

    def _getParser(self, url: str) -> Optional[robotparser.RobotFileParser]:
        parsed = urlparse(url)
        robotsUrl = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        with self.lock:
            rp = self.cache.get(robotsUrl)
            if rp is None:
                rp = robotparser.RobotFileParser()
                try:
                    rp.set_url(robotsUrl)
                    rp.read()
                except Exception:
                    rp = None
                self.cache[robotsUrl] = rp
            return rp

    def canFetch(self, url: str) -> bool:
        rp = self._getParser(url)
        if rp is None:
            return True
        return rp.can_fetch(self.userAgent, url)

    def crawlDelayMs(self, url: str, defaultMs: int = 10) -> int:
        rp = self._getParser(url)
        if rp is None:
            return defaultMs
        try:
            delay = rp.crawl_delay(self.userAgent) or rp.crawl_delay("*")
        except Exception:
            delay = None
        if delay is None:
            return defaultMs
        return max(defaultMs, int(delay * 1000))


class RateLimiter:
    def __init__(self, robotsChecker: RobotsChecker, defaultMinIntervalMs: int = 10) -> None:
        self.defaultMinIntervalMs = defaultMinIntervalMs
        self.robotsChecker = robotsChecker
        self.lastTimes: Dict[str, float] = {}
        self.lock = threading.Lock()

    def sleepIfNeeded(self, url: str) -> None:
        domain = urlparse(url).netloc
        intervalMs = self.robotsChecker.crawlDelayMs(url, defaultMs=self.defaultMinIntervalMs)
        with self.lock:
            now = time.time()
            last = self.lastTimes.get(domain, 0.0)
            elapsedMs = (now - last) * 1000.0
            if elapsedMs < intervalMs:
                time.sleep((intervalMs - elapsedMs) / 1000.0)
            self.lastTimes[domain] = time.time()


class CircuitBreaker:
    def __init__(self, failThreshold: int = 3, windowSec: int = 60, cooldownSec: int = 120) -> None:
        self.failThreshold = failThreshold
        self.windowSec = windowSec
        self.cooldownSec = cooldownSec
        self.failures: List[float] = []
        self.openedAt: Optional[float] = None

    def _prune(self) -> None:
        cutoff = time.time() - self.windowSec
        self.failures = [t for t in self.failures if t >= cutoff]

    def isOpen(self) -> bool:
        if self.openedAt is None:
            return False
        if time.time() - self.openedAt >= self.cooldownSec:
            # 过了冷却期，关闭熔断器
            self.openedAt = None
            self.failures.clear()
            return False
        return True

    def onSuccess(self) -> None:
        self.failures.clear()
        self.openedAt = None

    def onFailure(self) -> None:
        self._prune()
        self.failures.append(time.time())
        self._prune()
        if len(self.failures) >= self.failThreshold:
            self.openedAt = time.time()


class SourceBase:
    def __init__(self, robotsChecker: RobotsChecker, rateLimiter: RateLimiter, sessionFactory: SessionFactory) -> None:
        self.robotsChecker = robotsChecker
        self.rateLimiter = rateLimiter
        self.session = sessionFactory.build()

    def fetchQuote(self, stockCode: str) -> Dict[str, Any]:
        raise NotImplementedError


class AkshareSource(SourceBase):
    def __init__(self, robotsChecker: RobotsChecker, rateLimiter: RateLimiter, sessionFactory: SessionFactory) -> None:
        super().__init__(robotsChecker, rateLimiter, sessionFactory)
        try:
            import akshare as ak  # 延迟导入以避免打包问题
            self.ak = ak
        except Exception:
            self.ak = None
            raise RuntimeError("Akshare 不可用：模块未安装或导入失败")

    def fetchQuote(self, stockCode: str) -> Dict[str, Any]:
        spotDf = self.ak.stock_zh_a_spot_em()
        if spotDf is None or spotDf.empty:
            raise RuntimeError("Akshare 返回空数据")
        spotDf["代码"] = spotDf["代码"].astype(str).str.zfill(6)
        targetDf = spotDf[spotDf["代码"] == stockCode]
        if targetDf.empty:
            raise RuntimeError("Akshare 未找到目标代码")
        row = targetDf.iloc[0].to_dict()
        return {
            "stockName": row.get("名称") or "未知名称",
            "openPrice": float(row.get("今开") or 0),
            "closePrice": float((row.get("最新价") or row.get("收盘") or 0) or 0),
            "highPrice": float(row.get("最高") or 0),
            "lowPrice": float(row.get("最低") or 0),
            "volume": int(float(row.get("成交量") or row.get("成交量(手)") or 0)),
        }


class SinaSource(SourceBase):
    def __init__(self, robotsChecker: RobotsChecker, rateLimiter: RateLimiter, sessionFactory: SessionFactory) -> None:
        super().__init__(robotsChecker, rateLimiter, sessionFactory)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            "Referer": "http://finance.sina.com.cn/",
        })

    def mapCode(self, stockCode: str) -> str:
        return f"sh{stockCode}" if stockCode.startswith("6") else f"sz{stockCode}"

    def fetchQuote(self, stockCode: str) -> Dict[str, Any]:
        mapped = self.mapCode(stockCode)
        url = f"http://hq.sinajs.cn/list={mapped}"
        if not self.robotsChecker.canFetch(url):
            raise RuntimeError("Sina robots 不允许抓取该路径")
        self.rateLimiter.sleepIfNeeded(url)
        resp = self.session.get(url, timeout=(5, 10))
        resp.raise_for_status()
        text = resp.text
        if "hq_str_" not in text or "\"" not in text:
            raise RuntimeError("Sina 返回格式异常")
        payload = text.split("\"")[1]
        parts = payload.split(",")
        stockName = parts[0]
        openPrice = float(parts[1]) if parts[1] else 0.0
        prevClose = float(parts[2]) if parts[2] else 0.0
        currentPrice = float(parts[3]) if parts[3] else prevClose
        highPrice = float(parts[4]) if parts[4] else 0.0
        lowPrice = float(parts[5]) if parts[5] else 0.0
        volumeStr = parts[8] if len(parts) > 8 else "0"
        volume = int(float(volumeStr)) * 100
        return {
            "stockName": stockName,
            "openPrice": openPrice,
            "closePrice": currentPrice,
            "highPrice": highPrice,
            "lowPrice": lowPrice,
            "volume": volume,
        }


class TencentSource(SourceBase):
    def __init__(self, robotsChecker: RobotsChecker, rateLimiter: RateLimiter, sessionFactory: SessionFactory) -> None:
        super().__init__(robotsChecker, rateLimiter, sessionFactory)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            "Referer": "https://stockapp.finance.qq.com/",
        })

    def mapCode(self, stockCode: str) -> str:
        return f"sh{stockCode}" if stockCode.startswith("6") else f"sz{stockCode}"

    def fetchQuote(self, stockCode: str) -> Dict[str, Any]:
        mapped = self.mapCode(stockCode)
        url = f"http://qt.gtimg.cn/q={mapped}"
        if not self.robotsChecker.canFetch(url):
            raise RuntimeError("Tencent robots 不允许抓取该路径")
        self.rateLimiter.sleepIfNeeded(url)
        resp = self.session.get(url, timeout=(5, 10))
        resp.raise_for_status()
        text = resp.text
        if "=\"" not in text:
            raise RuntimeError("Tencent 返回格式异常")
        payload = text.split("=\"")[1].split("\";")[0]
        parts = payload.split("~")
        stockName = parts[1] if len(parts) > 1 else "未知名称"
        currentPrice = float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
        prevClose = float(parts[4]) if len(parts) > 4 and parts[4] else 0.0
        openPrice = float(parts[5]) if len(parts) > 5 and parts[5] else 0.0
        volumeHands = int(float(parts[6])) if len(parts) > 6 and parts[6] else 0
        volume = volumeHands * 100
        highPrice = max(currentPrice, openPrice, prevClose)
        lowPrice = min(currentPrice, openPrice, prevClose)
        return {
            "stockName": stockName,
            "openPrice": openPrice,
            "closePrice": currentPrice or prevClose,
            "highPrice": highPrice,
            "lowPrice": lowPrice,
            "volume": volume,
        }


class EastMoneySource(SourceBase):
    def __init__(self, robotsChecker: RobotsChecker, rateLimiter: RateLimiter, sessionFactory: SessionFactory) -> None:
        super().__init__(robotsChecker, rateLimiter, sessionFactory)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            "Referer": "https://quote.eastmoney.com/",
        })

    def _secid(self, code: str) -> str:
        return ("1." + code) if code.startswith("6") else ("0." + code)

    def fetchQuote(self, stockCode: str) -> Dict[str, Any]:
        secid = self._secid(stockCode)
        # 选取常用字段，提高高/低位准确性
        fields = "f58,f43,f46,f44,f45,f47"  # 名称、最新、开盘、高、低、成交量
        url = f"http://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields={fields}"
        if not self.robotsChecker.canFetch(url):
            raise RuntimeError("EastMoney robots 不允许抓取该路径")
        self.rateLimiter.sleepIfNeeded(url)
        resp = self.session.get(url, timeout=(5, 10))
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        if not data:
            raise RuntimeError("EastMoney 返回空数据")
        stockName = data.get("f58") or "未知名称"
        currentPrice = float(data.get("f43") or 0.0)
        openPrice = float(data.get("f46") or 0.0)
        highPrice = float(data.get("f44") or max(currentPrice, openPrice))
        lowPrice = float(data.get("f45") or min(currentPrice, openPrice))
        volume = int(float(data.get("f47") or 0))
        return {
            "stockName": stockName,
            "openPrice": openPrice,
            "closePrice": currentPrice,
            "highPrice": highPrice,
            "lowPrice": lowPrice,
            "volume": volume,
        }


class MultiSourceClient:
    def __init__(self, primaryTimeoutSec: int = 60, maxRetries: int = 3, defaultMinIntervalMs: int = 10) -> None:
        self.primaryTimeoutSec = primaryTimeoutSec
        self.maxRetries = maxRetries
        self.robotsChecker = RobotsChecker()
        self.rateLimiter = RateLimiter(robotsChecker=self.robotsChecker, defaultMinIntervalMs=defaultMinIntervalMs)
        self.sessionFactory = SessionFactory(totalRetries=3, backoffFactor=0.3)
        self.sources: List[Tuple[str, SourceBase]] = []
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._buildSources()

    def _addSource(self, tag: str, source: SourceBase) -> None:
        self.sources.append((tag, source))
        self.breakers[tag] = CircuitBreaker(failThreshold=3, windowSec=60, cooldownSec=120)

    def _buildSources(self) -> None:
        # 主数据源：Akshare
        try:
            self._addSource("akshare", AkshareSource(self.robotsChecker, self.rateLimiter, self.sessionFactory))
        except Exception:
            pass
        # 备用数据源：Sina -> Tencent -> EastMoney（作为第三备用源）
        self._addSource("sina", SinaSource(self.robotsChecker, self.rateLimiter, self.sessionFactory))
        self._addSource("tencent", TencentSource(self.robotsChecker, self.rateLimiter, self.sessionFactory))
        self._addSource("eastmoney", EastMoneySource(self.robotsChecker, self.rateLimiter, self.sessionFactory))

    def _trySource(self, tag: str, source: SourceBase, stockCode: str) -> Optional[Dict[str, Any]]:
        br = self.breakers.get(tag)
        if br and br.isOpen():
            return None
        for attemptIndex in range(self.maxRetries):
            try:
                result = source.fetchQuote(stockCode)
                if br:
                    br.onSuccess()
                return result
            except Exception:
                if br:
                    br.onFailure()
                time.sleep(0.2 * (attemptIndex + 1))
        return None

    def _sanitizeQuote(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # 统一校正高/低位，确保满足基本不变量
        openP = float(data.get("openPrice") or 0.0)
        closeP = float(data.get("closePrice") or 0.0)
        highP = float(data.get("highPrice") or 0.0)
        lowP = float(data.get("lowPrice") or 0.0)
        maxOC = max(openP, closeP)
        minOC = min(openP, closeP)
        # 修正不合理的高低位
        if highP < maxOC:
            highP = maxOC
        if lowP > minOC:
            lowP = minOC
        if highP < lowP:
            highP, lowP = lowP, highP
        data["highPrice"] = highP
        data["lowPrice"] = lowP
        return data

    def _annotate(self, data: Dict[str, Any], tag: str) -> Dict[str, Any]:
        sanitized = self._sanitizeQuote(dict(data))
        sanitized["dataSource"] = tag
        sanitized["fetchedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return sanitized

    def fetchQuote(self, stockCode: str) -> Dict[str, Any]:
        if not self.sources:
            raise RuntimeError("无可用数据源")
        # 如果首源是 Akshare，使用超时控制
        firstTag, firstSource = self.sources[0]
        if firstTag == "akshare":
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._trySource, firstTag, firstSource, stockCode)
                try:
                    result = future.result(timeout=self.primaryTimeoutSec)
                    if result:
                        return self._annotate(result, firstTag)
                except concurrent.futures.TimeoutError:
                    pass
        # 尝试备用源
        for tag, source in self.sources[1:]:
            result = self._trySource(tag, source, stockCode)
            if result:
                return self._annotate(result, tag)
        raise RuntimeError("所有数据源均不可用，请稍后重试")


def normalizeCode(stockCode: str) -> str:
    cleaned = stockCode.strip()
    if not cleaned.isdigit():
        raise ValueError("股票代码应为纯数字")
    if len(cleaned) != 6:
        cleaned = cleaned.zfill(6)
    return cleaned


def fetchQuoteMultiSource(stockCode: str) -> Dict[str, Any]:
    normalizedCode = normalizeCode(stockCode)
    client = MultiSourceClient(primaryTimeoutSec=60, maxRetries=3, defaultMinIntervalMs=10)
    return client.fetchQuote(normalizedCode)