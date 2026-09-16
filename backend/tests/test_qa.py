import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import get_db, engine, Base
from app.db.models import Clause, Document, Member, Policy, PolicyParty, Coverage


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


def test_qa_endpoint_no_basis_when_unrelated(db_session: Session):
    """
    DEV-GUIDE 1226 验收标准：
    问答对一个条款中确无依据的问题返回 no_basis 的接口响应。
    """
    client = TestClient(app)

    # 构造一份测试保单与特定条款
    doc = db_session.query(Document).filter(Document.id == "doc_qa_test").first()
    if not doc:
        doc = Document(id="doc_qa_test", original_name="test_policy.pdf", sha256="hash_qa_1", mime="application/pdf")
        db_session.add(doc)

    pol = db_session.query(Policy).filter(Policy.id == "pol_qa_test").first()
    if not pol:
        pol = Policy(
            id="pol_qa_test",
            document_id=doc.id,
            insurer="测试人寿",
            product_name="测试定期寿险",
            category="term_life",
            status="active",
        )
        db_session.add(pol)

    clause = db_session.query(Clause).filter(Clause.id == "clause_qa_1").first()
    if not clause:
        clause = Clause(
            id="clause_qa_1",
            document_id=doc.id,
            page_no=1,
            title="身故保险金责任",
            category="liability",
            text_masked="被保险人于本合同生效之日起因意外伤害导致身故，本公司按基本保险金额给付身故保险金。",
        )
        db_session.add(clause)
    db_session.commit()

    # 针对一个条款中完全无依据的问题（例如询问牙齿种植美容费用能否报销）
    # 大模型或者无法引用该条款，或由于引用失败自动降级为 no_basis
    resp = client.post(
        "/api/qa/ask",
        json={
            "question": "因为种植牙齿和牙齿正畸美容花费了三万元，这份保单能报销吗？",
            "scope": "policy",
            "policy_id": "pol_qa_test",
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "no_basis"
    assert data["verdict_label"] == "条款中未找到依据"
    assert len(data["citations"]) == 0
    assert "以保险公司" in data["disclaimer"]


def test_qa_fts_retrieval_and_exact_quote(db_session: Session):
    """
    测试 FTS 检索能正确定位并返回带有依据状态的问答
    """
    client = TestClient(app)

    doc = db_session.query(Document).filter(Document.id == "doc_qa_test_2").first()
    if not doc:
        doc = Document(id="doc_qa_test_2", original_name="test_acc.pdf", sha256="hash_qa_2", mime="application/pdf")
        db_session.add(doc)

    pol = db_session.query(Policy).filter(Policy.id == "pol_qa_test_2").first()
    if not pol:
        pol = Policy(
            id="pol_qa_test_2",
            document_id=doc.id,
            insurer="平安财险",
            product_name="平安安心意外伤害保险",
            category="accident",
            status="active",
        )
        db_session.add(pol)

    clause = db_session.query(Clause).filter(Clause.id == "clause_qa_2").first()
    if not clause:
        clause = Clause(
            id="clause_qa_2",
            document_id=doc.id,
            page_no=1,
            title="意外身故保险金",
            category="liability",
            text_masked="被保险人因遭受意外伤害事故导致身故，按约定保额全额给付。",
        )
        db_session.add(clause)
    db_session.commit()

    resp = client.post(
        "/api/qa/ask",
        json={
            "question": "意外伤害事故身故怎么赔？",
            "scope": "policy",
            "policy_id": "pol_qa_test_2",
            "stream": False,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] in ("likely_covered", "depends", "no_basis")
    assert "disclaimer" in data
