<!-- version: 1.0 -->
你处理的是经过脱敏的保险合同。〔成员A〕〔证件1〕这类方括号占位符代表被隐藏的个人信息，原样保留，不要猜测其真实内容。

引用规则：
1. quote 必须从给定页面文本中逐字复制，包括标点，不得改写、概括或拼接不相邻的句子。
2. 单条 quote 不超过 200 字。
3. 找不到依据时，字段值填 null，quote 填 null，不要编造。

任务：从保险合同页面文本中抽取保单基本信息、投保人、被保险人、受益人、保额保费、期间与缴费方式。
险种大类 category 必须是以下之一：
critical_illness (重疾险), medical (医疗险), accident (意外险), term_life (定期寿险), whole_life (终身寿险), annuity (年金险), endowment_whole_life (增额终身寿), property (财产险), auto (车险), other (其他).

合同文本：
{{ pages_content }}

输出 JSON 格式要求：
{
  "insurer": { "value": "保险公司名称", "evidence": { "page": 1, "quote": "包含保险公司名称的原文句子" } },
  "product_name": { "value": "保险产品名称", "evidence": { "page": 1, "quote": "包含产品名称的原文句子" } },
  "category": "accident",
  "subcategory": { "value": "如意外综合险", "evidence": null },
  "term_type": { "value": "long_term", "evidence": null },
  "applicant": { "value": "〔成员A〕", "evidence": { "page": 1, "quote": "投保人姓名:〔成员A〕" } },
  "insureds": [
    { "value": "〔成员B〕", "evidence": { "page": 1, "quote": "被保险人姓名:〔成员B〕" } }
  ],
  "beneficiaries": [
    { "value": "法定", "evidence": null }
  ],
  "sum_insured": { "value": "50万元", "evidence": { "page": 1, "quote": "基本保额:500,000.00元" } },
  "premium": { "value": "1280元", "evidence": { "page": 1, "quote": "首年保费:1,280元" } },
  "pay_mode": { "value": "年交", "evidence": { "page": 1, "quote": "交费方式:年交" } },
  "pay_years": { "value": "20年", "evidence": { "page": 1, "quote": "交费期间:20年" } },
  "apply_date": { "value": "2025-03-15", "evidence": { "page": 1, "quote": "投保日期:2025年03月15日" } },
  "effective_date": { "value": "2025-03-16", "evidence": { "page": 1, "quote": "生效日期:2025年03月16日零时" } },
  "expiry_date": { "value": "2026-03-15", "evidence": { "page": 1, "quote": "保险期间届满日:2026年03月15日二十四时" } },
  "cooling_days": { "value": "15天", "evidence": null },
  "waiting_days": { "value": "90天", "evidence": { "page": 1, "quote": "等待期为90天" } },
  "guaranteed_renewal": { "value": "否", "evidence": null }
}
