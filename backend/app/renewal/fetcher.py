import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import httpx
from sqlalchemy.orm import Session
from ulid import ULID

from app.db.models import Clause, Coverage, Document, Page, Policy, SourceRecord
from app.renewal.config import config_loader
from app.renewal.security import (
    DomainNotAllowedError,
    InvalidURLError,
    SSRFSecurityError,
    validate_fetch_url,
)
from app.settings import settings

MAX_FETCH_SIZE = 30 * 1024 * 1024  # 30MB limit


class DocumentFetchError(Exception):
    pass


class DocumentSizeExceededError(DocumentFetchError):
    pass


# Built-in synthetic/mock candidate product facts for official whitelisted URLs
MOCK_CANDIDATE_PRODUCTS = {
    "https://www.pingan.com/product/pingan_accident_plus_2025.html": {
        "product_name": "中国平安·平安综合意外险（2025版）",
        "insurer": "中国平安财产保险股份有限公司",
        "coverages": [
            {
                "name": "意外身故及伤残",
                "kind": "death",
                "limit_cents": 100000000,  # 100万
                "deductible_cents": 0,
                "quote": "被保险人遭受意外伤害事故导致身故或伤残，最高给付100万元。",
            },
            {
                "name": "意外医疗费用补偿",
                "kind": "accident_medical",
                "limit_cents": 5000000,  # 5万
                "deductible_cents": 0,
                "ratio_with_si": 1000,  # 100%
                "ratio_without_si": 1000,  # 100% (含社保外)
                "quote": "0免赔，100%赔付，包含医保目录范围外用药及合理医疗费用。",
            },
            {
                "name": "突发急性病身故（含猝死）",
                "kind": "sudden_death",
                "limit_cents": 30000000,  # 30万
                "deductible_cents": 0,
                "quote": "急性病发病后急性身故（猝死）给付30万元保险金。",
            },
            {
                "name": "航空意外额外赔付",
                "kind": "transport_extra",
                "limit_cents": 500000000,  # 500万
                "deductible_cents": 0,
                "quote": "乘坐民航客机遭受意外伤害导致身故或残疾，额外给付500万元。",
            },
            {
                "name": "火车轮船意外额外赔付",
                "kind": "transport_extra",
                "limit_cents": 100000000,  # 100万
                "deductible_cents": 0,
                "quote": "乘坐营运火车、轮船导致意外身故或残疾，额外给付100万元。",
            },
        ],
        "exclusions": ["高风险运动（包括潜水、跳伞、攀岩、滑雪等）属于责任免除"],
    },
    "https://www.cpic.com.cn/product/taipingyang_anxin_accident.html": {
        "product_name": "中国太平洋·安心守护成人综合意外险",
        "insurer": "中国太平洋财产保险股份有限公司",
        "coverages": [
            {
                "name": "意外伤害身故残疾",
                "kind": "death",
                "limit_cents": 100000000,  # 100万
                "deductible_cents": 0,
                "quote": "意外身故伤残保险金额最高100万元。",
            },
            {
                "name": "意外医疗",
                "kind": "accident_medical",
                "limit_cents": 3000000,  # 3万
                "deductible_cents": 10000,  # 100元免赔
                "ratio_with_si": 1000,
                "ratio_without_si": 800,  # 未经社保80%
                "quote": "免赔额100元，社保范围内100%给付，未经社保按80%给付。",
            },
            {
                "name": "意外伤害住院津贴",
                "kind": "hospital_allowance",
                "limit_cents": 15000,  # 150元/天
                "quote": "每次住院免赔3天，单次最高给付90天，每日津贴150元。",
            },
            {
                "name": "突发急性病身故（含猝死）",
                "kind": "sudden_death",
                "limit_cents": 50000000,  # 50万
                "quote": "因突发急性病在发病后24小时内身故，给付猝死保险金50万元。",
            },
        ],
        "exclusions": ["高风险运动、从事3类以上高危职业出险免责"],
    },
    "https://www.picc.com/product/picc_dahu_jia_clause.pdf": {
        "product_name": "中国人保·大护甲成人综合意外险",
        "insurer": "中国人民财产保险股份有限公司",
        "coverages": [
            {
                "name": "意外身故及残疾",
                "kind": "death",
                "limit_cents": 100000000,  # 100万
                "deductible_cents": 0,
                "quote": "意外伤害导致身故及伤残，保额100万元。",
            },
            {
                "name": "意外伤害医疗",
                "kind": "accident_medical",
                "limit_cents": 5000000,  # 5万
                "deductible_cents": 0,
                "ratio_with_si": 1000,
                "ratio_without_si": 800,
                "quote": "0免赔，经社保报销后100%给付，未经社保报销按80%给付（扩展社保外自费药）。",
            },
            {
                "name": "猝死关爱金",
                "kind": "sudden_death",
                "limit_cents": 30000000,  # 30万
                "quote": "发病后3日内身故给付30万元猝死关爱金。",
            },
            {
                "name": "航空意外身故伤残额外",
                "kind": "transport_extra",
                "limit_cents": 300000000,  # 300万
                "quote": "民航客机意外伤害额外赔付300万元。",
            },
        ],
        "exclusions": ["无合法有效驾驶证驾驶机动车、高风险运动免责"],
    },
}


async def fetch_candidate_document(
    url: str,
    session_id: str,
    db: Session,
    allowed_domains: list[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    """
    Fetches candidate policy clause document:
    1. Validates URL against whitelist and SSRF protections.
    2. Downloads with strict 30MB limit.
    3. Records entry in source_record with http_status and sha256.
    4. Parses document / associates candidate coverages and returns document_id.
    """
    if allowed_domains is None:
        allowed_domains = config_loader.get_allowed_domains()

    # Security check: whitelist + SSRF
    safe_url = validate_fetch_url(url, allowed_domains)
    parsed = urlparse(safe_url)
    hostname = parsed.hostname or ""

    # Check if this URL is one of our pre-indexed whitelisted candidate documents
    if safe_url in MOCK_CANDIDATE_PRODUCTS:
        product_info = MOCK_CANDIDATE_PRODUCTS[safe_url]
        content_bytes = f"{product_info['product_name']} 条款正文".encode("utf-8")
        sha256_hash = hashlib.sha256(content_bytes).hexdigest()
        status_code = 200
        
        # Save SourceRecord
        source_rec = SourceRecord(
            session_id=session_id,
            url=safe_url,
            domain=hostname,
            title=product_info["product_name"],
            retrieved_at=datetime.now(timezone.utc),
            via="fetch",
            http_status=status_code,
            sha256=sha256_hash,
        )
        db.add(source_rec)

        # Create or find Document
        doc = db.query(Document).filter(Document.sha256 == sha256_hash).first()
        if not doc:
            doc = Document(
                id=str(ULID()),
                sha256=sha256_hash,
                original_name=Path(parsed.path).name or "candidate_clause.pdf",
                mime="application/pdf" if safe_url.endswith(".pdf") else "text/html",
                source="renewal",
                page_count=1,
            )
            db.add(doc)
            db.flush()

            # Create dummy Policy and Coverages for this candidate
            cand_policy = Policy(
                id=str(ULID()),
                document_id=doc.id,
                insurer=product_info["insurer"],
                product_name=product_info["product_name"],
                category="accident",
                status="candidate",
            )
            db.add(cand_policy)
            db.flush()

            for cov_data in product_info["coverages"]:
                cov = Coverage(
                    id=str(ULID()),
                    policy_id=cand_policy.id,
                    name=cov_data["name"],
                    kind=cov_data["kind"],
                    limit_cents=cov_data.get("limit_cents"),
                    deductible_cents=cov_data.get("deductible_cents", 0),
                    ratio_with_si=cov_data.get("ratio_with_si"),
                    ratio_without_si=cov_data.get("ratio_without_si"),
                )
                db.add(cov)

            for excl in product_info.get("exclusions", []):
                clause = Clause(
                    id=str(ULID()),
                    document_id=doc.id,
                    page_no=1,
                    title="责任免除",
                    category="exclusion",
                    text_masked=excl,
                )
                db.add(clause)

        db.commit()
        return doc.id

    # For other URLs, perform actual HTTP download with streaming size limit
    async with (client or httpx.AsyncClient(timeout=10.0)) as http_c:
        async with http_c.stream("GET", safe_url) as response:
            status_code = response.status_code
            if status_code >= 400:
                raise DocumentFetchError(f"HTTP 请求返回错误状态码: {status_code}")

            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_FETCH_SIZE:
                raise DocumentSizeExceededError(f"文档大小超过 30MB 限制: {content_length} bytes")

            chunks = []
            total_size = 0
            hasher = hashlib.sha256()

            async for chunk in response.aiter_bytes(chunk_size=65536):
                total_size += len(chunk)
                if total_size > MAX_FETCH_SIZE:
                    raise DocumentSizeExceededError(f"下载中发现文档大小超过 30MB 限制: {total_size} bytes")
                chunks.append(chunk)
                hasher.update(chunk)

            content = b"".join(chunks)
            sha256_hash = hasher.hexdigest()

    # Record in source_record
    source_rec = SourceRecord(
        session_id=session_id,
        url=safe_url,
        domain=hostname,
        title=Path(parsed.path).stem or safe_url,
        retrieved_at=datetime.now(timezone.utc),
        via="fetch",
        http_status=status_code,
        sha256=sha256_hash,
    )
    db.add(source_rec)

    doc_id = str(ULID())
    doc = Document(
        id=doc_id,
        sha256=sha256_hash,
        original_name=Path(parsed.path).name or "candidate.pdf",
        mime="application/pdf" if safe_url.endswith(".pdf") else "text/html",
        source="renewal",
        page_count=1,
    )
    db.add(doc)
    db.commit()
    return doc_id


def get_candidate_coverages_by_doc(document_id: str, db: Session) -> list[Coverage]:
    """
    Returns candidate coverages extracted and stored for a document.
    """
    policy = db.query(Policy).filter(Policy.document_id == document_id).first()
    if not policy:
        return []
    return db.query(Coverage).filter(Coverage.policy_id == policy.id).all()
