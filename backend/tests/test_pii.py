import pytest
from app.ingest.pii import (
    PiiDeidentifier,
    verify_id_checksum,
    verify_luhn,
)


def test_gb11643_id_checksum():
    # 合法身份证号（GB 11643 校验位验证）
    assert verify_id_checksum("110101199003072375") is True
    assert verify_id_checksum("31010119950812123X") is True

    # 错误校验位（最后一位计算不符）
    assert verify_id_checksum("110101199003072378") is False
    assert verify_id_checksum("110101199003072379") is False
    assert verify_id_checksum("123456") is False



def test_bank_card_luhn_and_context():
    # 合法 16/19 位卡号
    valid_card = "6222021001123456789"
    assert verify_luhn(valid_card) is True

    deidentifier = PiiDeidentifier()

    # 带银行/账号上下文：应当脱敏为卡号
    text_with_context = f"缴费银行账户：{valid_card}，扣款正常。"
    res = deidentifier.deidentify_text(text_with_context)
    assert valid_card not in res.masked_text
    assert "〔卡号" in res.masked_text

    # 与卡号等长的保单号无银行上下文：不得误伤脱敏为卡号
    policy_no_card_len = "955110012345678901"
    text_policy = f"本次保险的合同编号为：{policy_no_card_len}，请知悉。"
    res2 = deidentifier.deidentify_text(text_policy)
    assert "〔卡号" not in res2.masked_text
    assert "〔保单号〕" in res2.masked_text


def test_phone_number_with_spaces():
    deidentifier = PiiDeidentifier()
    text = "联系电话：138 1234 5678，紧急联系电话：139-9876-5432。"
    res = deidentifier.deidentify_text(text)
    assert "138 1234 5678" not in res.masked_text
    assert "139-9876-5432" not in res.masked_text
    assert "〔电话1〕" in res.masked_text
    assert "〔电话2〕" in res.masked_text


def test_member_name_longest_match():
    # 模拟张伟明（成员A）与张伟（成员B），避免短名字误伤
    members = [
        {"real_name": "张伟", "placeholder": "〔成员B〕"},
        {"real_name": "张伟明", "placeholder": "〔成员A〕"},
    ]
    deidentifier = PiiDeidentifier(members)
    text = "投保人为张伟明先生，被保险人为张伟先生。"
    res = deidentifier.deidentify_text(text)

    # 张伟明 必须替换为 〔成员A〕，不能变成 〔成员B〕明
    assert "〔成员A〕先生" in res.masked_text
    assert "〔成员B〕先生" in res.masked_text
    assert "张伟" not in res.masked_text


def test_secondary_pass_residual_pii_zero_hits():
    members = [
        {"real_name": "张伟明", "placeholder": "〔成员A〕"},
    ]
    deidentifier = PiiDeidentifier(members)
    synthetic_doc_text = """
    保单号码：955110012345678901
    投保人姓名：张伟明
    投保人身份证号：110101199003072375
    手机：138 1234 5678
    邮箱：zhangweiming@example.com
    扣款银行账户：6222021001123456789
    家庭住址：北京市朝阳区建国门外大街1号
    非有效身份证：110101199003072378
    """.strip()

    res = deidentifier.deidentify_text(synthetic_doc_text)
    assert res.pii_status == "success"

    # 验证二次检查 residual pii 为 0
    assert deidentifier._check_residual_pii(res.masked_text) == 0
    assert "110101199003072375" not in res.masked_text

    assert "138 1234 5678" not in res.masked_text
    assert "6222021001123456789" not in res.masked_text
    assert "zhangweiming@example.com" not in res.masked_text
    assert "北京市朝阳区建国门外大街1号" not in res.masked_text

    # 非法校验位的数字串不应被当作身份证脱敏
    assert "110101199003072378" in res.masked_text
