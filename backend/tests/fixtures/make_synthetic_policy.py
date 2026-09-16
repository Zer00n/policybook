from pathlib import Path
import fitz
from PIL import Image, ImageDraw, ImageFont


def create_synthetic_fixtures(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "synthetic_policy.pdf"
    scanned_png_path = output_dir / "synthetic_scanned_page.png"

    # 1. 生成合成保单 PDF
    doc = fitz.open()

    # 第 1 页：基本信息页
    page1 = doc.new_page(width=595, height=842)  # A4
    text1 = """
家庭人身意外伤害保险合同

基本保单信息
保单号码：955110012345678901
合同类型：长期人身险
投保日期：2025年03月15日
生效日期：2025年03月16日零时

关系人信息
投保人姓名：张伟明
投保人证件号码：110101199003072375
投保人联系电话：138 1234 5678
投保人电子邮箱：zhangweiming@example.com
被保险人姓名：张伟
被保险人身份证号：31010119950812123X
家庭通讯地址：北京市朝阳区建国门外大街1号院3号楼802室

缴费与结算信息
缴费方式：银行自动转账
扣款银行账户：6222021001123456789
开户银行：中国工商银行北京分行

非有效身份证样本（用于容错校验）：110101199003072378
""".strip()

    page1.insert_text((50, 60), text1, fontsize=12, fontname="china-ss")

    # 第 2 页：保险责任条款
    page2 = doc.new_page(width=595, height=842)
    text2 = """
第二条 保险责任

2.1 意外身故保险金
被保险人遭受意外伤害事故，并自该事故发生之日起一百八十日内因该事故身故的，
本公司按基本保险金额 500,000.00 元给付身故保险金，本合同终止。

2.2 意外伤残保险金
被保险人遭受意外伤害事故，并自该事故发生之日起一百八十日内因该事故造成本合同所附
《人身保险伤残评定标准》所列伤残之一的，按评定等级对应比例给付伤残保险金。

2.3 意外医疗保险金
在保险期间内，被保险人遭受意外伤害事故在二级以上（含二级）公立医院接受治疗的，
本公司对其实际支出的符合当地社会基本医疗保险支付范围的医疗费用，在扣除 100 元免赔额后，
按 100% 的比例给付意外医疗保险金。若未经社保报销，赔付比例为 80%。
基本保额限额为 30,000 元。

第三条 责任免除
被保险人从事潜水、跳伞、攀岩、蹦极等高风险运动期间遭受的意外伤害，本公司不承担给付保险金责任。
""".strip()

    page2.insert_text((50, 60), text2, fontsize=12, fontname="china-ss")
    doc.save(pdf_path)
    doc.close()

    # 2. 生成纯图片扫描版（无文本层，纯图片）
    img = Image.new("RGB", (1200, 1600), color=(250, 248, 242))
    draw = ImageDraw.Draw(img)

    # 模拟手绘扫描文字
    scanned_text = [
        "平安财产保险股份有限公司 - 意外伤害批单",
        "保单号：PA9551100987654321",
        "被保险人姓名：李晓华",
        "身份证件号码：110101199003072375",
        "联系手机号码：13912345678",
        "意外医疗限额：20,000 元",
        "免赔额：0 元，赔付比例：100%",
        "特别约定：被保险人因交通事故意外住院医疗费用正常报销。",
    ]

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 36)
    except Exception:
        font = ImageFont.load_default()

    y = 120
    for line in scanned_text:
        draw.text((100, y), line, font=font, fill=(30, 30, 30))
        y += 80

    img.save(scanned_png_path, "PNG")



if __name__ == "__main__":
    fixtures_dir = Path(__file__).resolve().parent
    create_synthetic_fixtures(fixtures_dir)
    print(f"Fixtures created in {fixtures_dir}")
