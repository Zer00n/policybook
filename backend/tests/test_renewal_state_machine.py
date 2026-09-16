import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ulid import ULID

from app.db.models import Base, Coverage, Document, Policy, ChatSession, SourceRecord
from app.renewal.search import FaultInjectionSearchProvider, MockSearchProvider
from app.renewal.state_machine import (
    InvalidStateTransitionError,
    RenewalStateMachine,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_policy(db_session):
    doc = Document(
        id=str(ULID()),
        sha256="fake_sha256_for_test",
        original_name="test_accident.pdf",
        mime="application/pdf",
    )
    db_session.add(doc)
    db_session.flush()

    policy = Policy(
        id=str(ULID()),
        document_id=doc.id,
        product_name="平安安心综合意外险2024",
        insurer="中国平安财产保险股份有限公司",
        category="accident",
        premium_cents=29900,
    )
    db_session.add(policy)
    db_session.flush()

    cov1 = Coverage(
        id=str(ULID()),
        policy_id=policy.id,
        name="意外身故伤残",
        kind="death",
        limit_cents=50000000,
    )
    cov2 = Coverage(
        id=str(ULID()),
        policy_id=policy.id,
        name="意外伤害医疗",
        kind="accident_medical",
        limit_cents=2000000,
        deductible_cents=10000,
        ratio_with_si=1000,
    )
    db_session.add_all([cov1, cov2])
    db_session.commit()
    return policy


@pytest.mark.asyncio
async def test_state_machine_init(db_session, sample_policy):
    session = ChatSession(
        id=str(ULID()),
        kind="renewal",
        policy_id=sample_policy.id,
        state="START",
    )
    db_session.add(session)
    db_session.commit()

    sm = RenewalStateMachine(session, db_session)
    welcome_msg = await sm.initialize()

    assert session.state == "COLLECT_NEEDS"
    assert "平安安心综合意外险2024" in welcome_msg


def test_state_machine_illegal_transition(db_session, sample_policy):
    session = ChatSession(
        id=str(ULID()),
        kind="renewal",
        policy_id=sample_policy.id,
        state="START",
    )
    db_session.add(session)
    db_session.commit()

    sm = RenewalStateMachine(session, db_session)
    # START cannot transition directly to SEARCH or REPORT
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to("SEARCH")

    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to("REPORT")


@pytest.mark.asyncio
async def test_state_machine_collect_needs_and_ask_user(db_session, sample_policy):
    session = ChatSession(
        id=str(ULID()),
        kind="renewal",
        policy_id=sample_policy.id,
        state="START",
    )
    db_session.add(session)
    db_session.commit()

    sm = RenewalStateMachine(session, db_session)
    await sm.initialize()

    # User says they travel more this year
    turn_res = await sm.process_user_turn(user_text="今年出差坐飞机高铁变多了，经常加班需要猝死保障")
    
    # State should advance to ASK_USER with max 2 questions
    assert turn_res["state"] == "ASK_USER"
    questions = turn_res["questions"]
    assert 1 <= len(questions) <= 2
    for q in questions:
        assert q.dimension
        assert q.why.startswith("影响意外险")
        assert len(q.options) > 0

    # Profile should have recorded travel_mode and sudden_death from user statement
    assert "travel_mode" in turn_res["profile"]
    assert "sudden_death" in turn_res["profile"]


@pytest.mark.asyncio
async def test_state_machine_skip_to_search_and_complete(db_session, sample_policy):
    session = ChatSession(
        id=str(ULID()),
        kind="renewal",
        policy_id=sample_policy.id,
        state="START",
    )
    db_session.add(session)
    db_session.commit()

    sm = RenewalStateMachine(session, db_session, search_provider=MockSearchProvider())
    await sm.initialize()

    # User says skip questions
    turn_res = await sm.process_user_turn(user_text="跳过其余提问，直接推荐对比", skip=True)

    assert turn_res["state"] == "END"
    report = turn_res["report"]
    assert report.status == "complete"
    assert report.comparison_matrix is not None
    assert len(report.comparison_matrix.products) >= 2
    assert len(report.customer_service_questions) >= 1
    assert len(report.source_records) >= 1

    # Check Red Line 6: all URLs in narrative must be in source_record
    recorded_urls = {r.url for r in report.source_records}
    import re
    urls_in_narrative = re.findall(r"https?://[^\s()\[\]{}<>'\"`“”‘’（）【】《》]+", report.difference_narrative)
    for u in urls_in_narrative:
        clean_u = u.rstrip(".,;:!?，。；：！？）)]}>\"'")
        assert clean_u in recorded_urls


@pytest.mark.asyncio
async def test_state_machine_search_timeout_disclosure(db_session, sample_policy):
    """
    DEV-GUIDE 10.8 验收项: 模拟 search_web 超时后报告中披露失败的接口响应
    (Red Line 7: 搜索失败必须披露，不得用模型记忆补全)
    """
    fault_provider = FaultInjectionSearchProvider(
        base_provider=MockSearchProvider(),
        fault_type="timeout",
        on_call=1,
    )

    session = ChatSession(
        id=str(ULID()),
        kind="renewal",
        policy_id=sample_policy.id,
        state="START",
    )
    db_session.add(session)
    db_session.commit()

    sm = RenewalStateMachine(session, db_session, search_provider=fault_provider)
    await sm.initialize()

    turn_res = await sm.process_user_turn(user_text="直接对比", skip=True)

    assert turn_res["state"] == "END"
    report = turn_res["report"]
    assert report.status == "search_failed"
    assert "超时" in report.search_failure_reason
    assert "检索未完成" in report.difference_narrative
    assert "超时" in report.difference_narrative
    assert "防编造" in report.difference_narrative
