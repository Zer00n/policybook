from datetime import datetime, timezone
from ulid import ULID
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


def generate_ulid() -> str:
    return str(ULID())


def now_utc():
    return datetime.now(timezone.utc)


class Member(Base):
    __tablename__ = "member"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    display_name = Column(String(50), nullable=False)
    relation = Column(String(20), nullable=False)  # 本人 / 配偶 / 子女 / 父母 / 其他
    birth_year = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)  # 男 / 女 / 其他
    occupation = Column(String(100), nullable=True)
    city = Column(String(50), nullable=True)
    social_insurance = Column(String(20), nullable=True)  # 职工 / 居民 / 无 / 未知
    color = Column(String(20), default="#2A8F82")
    real_name_enc = Column(Text, nullable=True)  # 加密真实姓名，仅本地匹配脱敏
    placeholder = Column(String(20), nullable=False, unique=True)  # 如 〔成员A〕
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Document(Base):
    __tablename__ = "document"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    sha256 = Column(String(64), index=True, nullable=False)
    original_name = Column(String(255), nullable=False)
    mime = Column(String(50), nullable=False)
    page_count = Column(Integer, default=0)
    source = Column(String(20), default="upload")  # upload / renewal
    created_at = Column(DateTime(timezone=True), default=now_utc)

    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan", order_by="Page.page_no")
    pii_mappings = relationship("PiiMapping", back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "page"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    document_id = Column(String(26), ForeignKey("document.id", ondelete="CASCADE"), index=True, nullable=False)
    page_no = Column(Integer, nullable=False)  # 1-indexed
    image_path = Column(String(255), nullable=False)  # 原始 144 DPI 渲染图片
    masked_image_path = Column(String(255), nullable=True)  # 视觉打码后的图片
    text_raw_enc = Column(Text, nullable=True)  # 加密保存的原始提取文本
    text_masked = Column(Text, nullable=True)  # 脱敏后的文本（发送给模型）
    char_map_path = Column(String(255), nullable=True)  # 字符级坐标 JSON
    is_ocr = Column(Boolean, default=False)
    pii_status = Column(String(20), default="pending")  # pending / success / failed
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now_utc)

    document = relationship("Document", back_populates="pages")


class PiiMapping(Base):
    __tablename__ = "pii_mapping"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    document_id = Column(String(26), ForeignKey("document.id", ondelete="CASCADE"), index=True, nullable=False)
    placeholder = Column(String(50), nullable=False)  # 如 〔证件1〕, 〔电话1〕
    kind = Column(String(30), nullable=False)  # id_card / phone / bank_card / email / name / policy_no / address
    value_enc = Column(Text, nullable=False)  # Fernet 加密密文

    document = relationship("Document", back_populates="pii_mappings")


class Job(Base):
    __tablename__ = "job"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    kind = Column(String(50), nullable=False)  # import / renewal
    status = Column(String(20), default="queued", index=True)  # queued / running / review_ready / succeeded / failed
    step = Column(String(50), default="init")
    payload_json = Column(Text, nullable=True)
    progress = Column(Float, default=0.0)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Policy(Base):
    __tablename__ = "policy"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    document_id = Column(String(26), ForeignKey("document.id", ondelete="SET NULL"), index=True, nullable=True)
    insurer = Column(String(100), nullable=False)
    product_name = Column(String(150), nullable=False, index=True)
    policy_no_enc = Column(Text, nullable=True)  # Fernet 加密真实保单号
    category = Column(String(50), nullable=False, index=True)  # critical_illness / medical / accident / term_life / whole_life / annuity / endowment_whole_life / property / auto / other
    subcategory = Column(String(50), nullable=True)
    term_type = Column(String(20), default="long_term")  # long_term / short_term / one_year
    premium_cents = Column(Integer, nullable=True)  # 保费（分）
    pay_mode = Column(String(20), nullable=True)  # 年交 / 月交 / 趸交
    pay_years = Column(String(30), nullable=True)  # 20年 / 终身 / 1年
    sum_insured_cents = Column(Integer, nullable=True)  # 基本保额（分）
    apply_date = Column(String(20), nullable=True)  # YYYY-MM-DD
    effective_date = Column(String(20), nullable=True)  # YYYY-MM-DD
    expiry_date = Column(String(20), nullable=True)  # YYYY-MM-DD
    cooling_days = Column(Integer, nullable=True)  # 犹豫期天数
    waiting_days = Column(Integer, nullable=True)  # 等待期天数
    guaranteed_renewal = Column(Boolean, nullable=True)  # 是否保证续保
    renewal_years = Column(Integer, nullable=True)  # 保证续保年数
    status = Column(String(20), default="active", index=True)  # active / waiting / expiring_soon / lapsed
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    document = relationship("Document")
    parties = relationship("PolicyParty", back_populates="policy", cascade="all, delete-orphan")
    coverages = relationship("Coverage", back_populates="policy", cascade="all, delete-orphan")


class PolicyParty(Base):
    __tablename__ = "policy_party"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    policy_id = Column(String(26), ForeignKey("policy.id", ondelete="CASCADE"), index=True, nullable=False)
    member_id = Column(String(26), ForeignKey("member.id", ondelete="SET NULL"), index=True, nullable=True)
    role = Column(String(30), nullable=False)  # applicant / insured / beneficiary
    share = Column(Integer, nullable=True)  # 比例百分比 (0-100)

    policy = relationship("Policy", back_populates="parties")
    member = relationship("Member")


class Coverage(Base):
    __tablename__ = "coverage"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    policy_id = Column(String(26), ForeignKey("policy.id", ondelete="CASCADE"), index=True, nullable=False)
    parent_coverage_id = Column(String(26), ForeignKey("coverage.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(150), nullable=False)
    kind = Column(String(50), nullable=False)  # death / disability / critical_illness / medical / accident_medical / hospital_allowance / transport_extra / sudden_death / other
    limit_cents = Column(Integer, nullable=True)  # 保额/限额（分）
    deductible_cents = Column(Integer, nullable=True)  # 免赔额（分）
    deductible_scope = Column(String(30), default="none")  # annual / per_claim / none / unknown
    ratio_with_si = Column(Integer, nullable=True)  # 经社保赔付比例千分比 (1000 = 100%)
    ratio_without_si = Column(Integer, nullable=True)  # 未经社保赔付比例千分比
    waiting_days = Column(Integer, nullable=True)
    is_rider = Column(Boolean, default=False)

    policy = relationship("Policy", back_populates="coverages")
    parent = relationship("Coverage", remote_side=[id], backref="children")


class Clause(Base):
    __tablename__ = "clause"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    document_id = Column(String(26), ForeignKey("document.id", ondelete="CASCADE"), index=True, nullable=False)
    page_no = Column(Integer, nullable=False)
    clause_no = Column(String(50), nullable=True)
    title = Column(String(200), nullable=True)
    category = Column(String(30), default="liability")  # liability / exclusion / definition / waiting / renewal / other
    text_masked = Column(Text, nullable=False)

    document = relationship("Document")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    owner_type = Column(String(30), nullable=False)  # policy / coverage / exclusion / clause
    owner_id = Column(String(26), index=True, nullable=False)
    field = Column(String(50), nullable=False)
    page_id = Column(String(26), ForeignKey("page.id", ondelete="SET NULL"), nullable=True)
    page_no = Column(Integer, nullable=False)
    quote = Column(Text, nullable=False)
    start = Column(Integer, nullable=True)
    end = Column(Integer, nullable=True)
    rects_json = Column(Text, nullable=True)  # JSON 格式坐标列表 [{"x0", "y0", "x1", "y1"}] (PDF pt)
    status = Column(String(20), default="unverified")  # verified / unverified / not_found / conflict
    model_value = Column(Text, nullable=True)
    human_value = Column(Text, nullable=True)

    page = relationship("Page")


class LLMCall(Base):
    __tablename__ = "llm_call"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    task_kind = Column(String(50), nullable=False)  # classify_pages / extract_policy / extract_coverages / qa / claim
    model_id = Column(String(100), nullable=False)
    provider = Column(String(30), default="ark")
    input_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    reasoning_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    ok = Column(Boolean, default=True)
    error = Column(Text, nullable=True)
    request_digest = Column(String(255), nullable=True)
    response_path = Column(String(255), nullable=True)
    verify_summary_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)


class Reminder(Base):
    __tablename__ = "reminder"

    id = Column(String(26), primary_key=True, default=generate_ulid)
    policy_id = Column(String(26), ForeignKey("policy.id", ondelete="CASCADE"), index=True, nullable=True)
    member_id = Column(String(26), ForeignKey("member.id", ondelete="SET NULL"), index=True, nullable=True)
    kind = Column(String(50), nullable=False)  # expiring_60d / expiring_30d / expiring_7d / waiting_end / payment_due
    due_date = Column(String(20), nullable=False)  # YYYY-MM-DD
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending / dismissed / resolved
    created_at = Column(DateTime(timezone=True), default=now_utc)

    policy = relationship("Policy")
    member = relationship("Member")


class AppSetting(Base):
    __tablename__ = "app_setting"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)  # JSON string or plain text
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

