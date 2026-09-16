from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import SourceRecord
from app.renewal.config import config_loader
from app.renewal.security import is_domain_allowed


class SearchResult(BaseModel):
    url: str
    domain: str
    title: str
    snippet: str = ""


class SearchProviderError(Exception):
    """Base exception for search provider errors."""
    pass


class SearchTimeoutError(SearchProviderError):
    """Raised when search times out."""
    pass


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[SearchResult]:
        pass


class MockSearchProvider(SearchProvider):
    """
    Mock search provider with realistic accident insurance products
    on official insurance websites (whitelisted domains) for offline testing,
    evals, and demos.
    """
    def __init__(self, predefined_results: list[SearchResult] | None = None):
        if predefined_results is not None:
            self._results = predefined_results
        else:
            self._results = [
                SearchResult(
                    url="https://www.pingan.com/product/pingan_accident_plus_2025.html",
                    domain="pingan.com",
                    title="中国平安·平安综合意外险（2025版）产品条款与保障说明",
                    snippet="覆盖意外身故伤残100万、意外医疗5万（0免赔100%报销含社保外用药）、猝死责任30万、航空与高铁额外给付。",
                ),
                SearchResult(
                    url="https://www.cpic.com.cn/product/taipingyang_anxin_accident.html",
                    domain="cpic.com.cn",
                    title="中国太平洋财产保险·安心守护成人综合意外伤害保险条款",
                    snippet="提供意外伤害身故残疾最高100万、意外住院津贴150元/天、突发急性病身故（含猝死）50万、高风险运动免责条款明确。",
                ),
                SearchResult(
                    url="https://www.picc.com/product/picc_dahu_jia_clause.pdf",
                    domain="picc.com",
                    title="中国人保·人保大护甲成人综合意外伤害保险条款与费率表",
                    snippet="年度经典综合意外险，身故伤残保额100万，意外医疗社保内100%报销社保外80%报销，猝死保障30万，交通工具额外保障。",
                ),
                # A non-whitelisted domain result to verify filtering
                SearchResult(
                    url="https://thirdparty-review.cn/article/top-accidents-2025.html",
                    domain="thirdparty-review.cn",
                    title="第三方测评：2025十大热门意外险全方位深度评测",
                    snippet="网络个人博主评测文章，非官方产品条款来源。",
                ),
            ]

    async def search(self, query: str) -> list[SearchResult]:
        # Return results that roughly match or all standard results
        return list(self._results)


class FaultInjectionSearchProvider(SearchProvider):
    """
    Wraps any SearchProvider and injects faults on call N (timeout, exception, empty)
    to test agent fault disclosure and degradation mechanisms without touching agent code.
    """
    def __init__(
        self,
        base_provider: SearchProvider,
        fault_type: Literal["timeout", "error", "empty"] = "timeout",
        on_call: int = 1,
    ):
        self.base_provider = base_provider
        self.fault_type = fault_type
        self.on_call = on_call
        self.call_count = 0

    async def search(self, query: str) -> list[SearchResult]:
        self.call_count += 1
        if self.call_count == self.on_call:
            if self.fault_type == "timeout":
                raise SearchTimeoutError("模拟联网搜索超时 (timeout after 5000ms)")
            elif self.fault_type == "error":
                raise SearchProviderError("模拟搜索引擎服务不可用 (HTTP 503 Service Unavailable)")
            elif self.fault_type == "empty":
                return []
        return await self.base_provider.search(query)


async def execute_search_and_record(
    provider: SearchProvider,
    query: str,
    session_id: str,
    db: Session,
    allowed_domains: list[str] | None = None,
) -> list[SearchResult]:
    """
    Executes search, strictly filters results by allowed_domains,
    and writes every compliant result into source_record table.
    """
    if allowed_domains is None:
        allowed_domains = config_loader.get_allowed_domains()

    raw_results = await provider.search(query)
    filtered_results: list[SearchResult] = []

    for item in raw_results:
        parsed = urlparse(item.url)
        hostname = parsed.hostname or item.domain
        if is_domain_allowed(hostname, allowed_domains):
            filtered_results.append(item)
            # Record in source_record
            record = SourceRecord(
                session_id=session_id,
                url=item.url,
                domain=hostname,
                title=item.title,
                via="search",
                retrieved_at=datetime.now(timezone.utc),
            )
            db.add(record)

    db.commit()
    return filtered_results
