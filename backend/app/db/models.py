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
    status = Column(String(20), default="queued", index=True)  # queued / running / succeeded / failed
    step = Column(String(50), default="init")
    payload_json = Column(Text, nullable=True)
    progress = Column(Float, default=0.0)
    error = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now_utc)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
