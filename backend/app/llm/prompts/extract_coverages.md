<!-- version: 1.0 -->
你处理的是经过脱敏的保险合同。〔成员A〕〔证件1〕这类方括号占位符代表被隐藏的个人信息，原样保留，不要猜测其真实内容。

引用规则：
1. quote 必须从给定页面文本中逐字复制，包括标点，不得改写、概括或拼接不相邻的句子。
2. 单条 quote 不超过 200 字。
3. 找不到依据时，字段值填 null，quote 填 null，不要编造。

任务：从条款页面文本中抽取各项保险责任（CoverageItem）与责任免除条款（Exclusion）。

责任类型 kind 必须是以下之一：
death (身故), disability (伤残), critical_illness (重疾), medical (医疗), accident_medical (意外医疗), hospital_allowance (住院津贴), transport_extra (交通额外赔), sudden_death (猝死), other (其他).

免赔额维度 deductible_scope 必须是以下之一：
annual (年度累计免赔), per_claim (每次事故免赔), none (无免赔), unknown (未明确).

责任免除（Exclusion）要求：
- evidence: page + quote
- plain_explanation: 用通俗易懂的中文概括该免责条款要点，不超过 80 字。

条款文本：
{{ pages_content }}

输出 JSON 格式要求：
{
  "coverages": [
    {
      "name": "意外伤害身故和伤残保障",
      "kind": "death",
      "limit": { "value": "50万元", "evidence": { "page": 1, "quote": "意外伤害身故保险金额为 50 万元" } },
      "deductible": { "value": "0元", "evidence": null },
      "deductible_scope": "none",
      "ratio_with_si": { "value": "100%", "evidence": null },
      "ratio_without_si": { "value": "100%", "evidence": null },
      "waiting_days": { "value": null, "evidence": null },
      "conditions": [
        { "page": 1, "quote": "被保险人遭受意外伤害事故并自事故发生之日起180日内身故的" }
      ],
      "is_rider": false
    }
  ],
  "exclusions": [
    {
      "evidence": { "page": 2, "quote": "投保人对被保险人的故意杀害、故意伤害" },
      "plain_explanation": "投保人故意伤害或杀害被保险人导致出险的，保险公司不赔偿。"
    }
  ]
}
