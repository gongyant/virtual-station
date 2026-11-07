from __future__ import annotations

import csv
import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "虚拟水文站实验总报告_2026-07-26.docx"
BASE = ROOT / "outputs" / "virtual_station_mainline"

BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
PALE_BLUE = "EAF2F8"
LIGHT_BLUE = "D9EAF7"
PALE_GREEN = "E2F0D9"
PALE_AMBER = "FFF2CC"
PALE_RED = "FCE4D6"
GRAY = "F2F4F7"
MID_GRAY = "6B6B6B"
TEXT = "222222"
WHITE = "FFFFFF"


def load_json(relative: str):
    with (ROOT / relative).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_csv(relative: str):
    with (ROOT / relative).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def set_cell_shading(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, width_dxa: int):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def set_row_repeat(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_row_cant_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant = OxmlElement("w:cantSplit")
    tr_pr.append(cant)


def set_table_geometry(table, widths):
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), "9360")
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")
    dxa = [round(9360 * w) for w in widths]
    dxa[-1] += 9360 - sum(dxa)
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        set_row_cant_split(row)
        for idx, cell in enumerate(row.cells):
            set_cell_width(cell, dxa[idx])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def set_table_borders(table, color="D0D7DE", size=6):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), str(size))
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)
        borders.append(element)


def set_run_font(run, size=None, bold=None, color=None, italic=None):
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def style_paragraph(paragraph, size=10, bold=False, color=TEXT, align=None):
    if align is not None:
        paragraph.alignment = align
    for run in paragraph.runs:
        set_run_font(run, size=size, bold=bold, color=color)


def add_text(paragraph, text, bold=False, color=TEXT, size=10, italic=False):
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color, italic=italic)
    return run


def add_table(doc, headers, rows, widths, header_fill=GRAY, font_size=8.6, first_col_bold=False, trailing=True):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    set_table_geometry(table, widths)
    set_table_borders(table)
    header = table.rows[0]
    set_row_repeat(header)
    for i, value in enumerate(headers):
        cell = header.cells[i]
        set_cell_shading(cell, header_fill)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        add_text(p, str(value), bold=True, color=DARK_BLUE, size=font_size)
    for row_values in rows:
        row = table.add_row()
        set_row_cant_split(row)
        for i, value in enumerate(row_values):
            cell = row.cells[i]
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            if i > 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_text(p, str(value), bold=(first_col_bold and i == 0), size=font_size)
    if trailing:
        doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(8)
    add_text(p, text, italic=True, color=MID_GRAY, size=9)


def add_picture(doc, relative, caption, width=6.25, alt=""):
    path = ROOT / relative
    if not path.exists():
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    shape = run.add_picture(str(path), width=Inches(width))
    try:
        shape._inline.docPr.set("descr", alt or caption)
    except Exception:
        pass
    add_caption(doc, caption)


def add_callout(doc, title, body, fill=PALE_BLUE):
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [1.0])
    set_table_borders(table, color=fill, size=0)
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(3)
    add_text(p, title, bold=True, color=DARK_BLUE, size=10.5)
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    add_text(p2, body, size=9.4)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def add_page_number(paragraph):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)
    set_run_font(run, size=8, color=MID_GRAY)


def add_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    return p


def add_body(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.10
    if bold_prefix and text.startswith(bold_prefix):
        add_text(p, bold_prefix, bold=True, size=10.2)
        add_text(p, text[len(bold_prefix):], size=10.2)
    else:
        add_text(p, text, size=10.2)
    return p


def add_section_break(doc):
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)


def setup_document(doc):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string(TEXT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10
    for name, size, color, before, after in (
        ("Title", 34, DARK_BLUE, 0, 8),
        ("Subtitle", 14, MID_GRAY, 0, 8),
        ("Heading 1", 16, BLUE, 16, 8),
        ("Heading 2", 13, BLUE, 12, 6),
        ("Heading 3", 12, DARK_BLUE, 8, 4),
    ):
        style = styles[name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = name.startswith("Heading") or name == "Title"
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    header = section.header
    p = header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_after = Pt(2)
    add_text(p, "DEEPBAS · VIRTUAL HYDROLOGICAL STATION", bold=True, color=BLUE, size=8)
    p_pr = p._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), BLUE)
    borders.append(bottom)
    p_pr.append(borders)

    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_text(p, "DeepBas-VHS-GT-Lite-v0.1  |  第 ", color=MID_GRAY, size=8)
    add_page_number(p)
    add_text(p, " 页", color=MID_GRAY, size=8)


def cover(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(18)
    p_pr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    top = OxmlElement("w:top")
    top.set(qn("w:val"), "single")
    top.set(qn("w:sz"), "6")
    top.set(qn("w:space"), "1")
    top.set(qn("w:color"), BLUE)
    bdr.append(top)
    p_pr.append(bdr)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(12)
    add_text(p, "阶段性最终交付 · 2026-07-26", bold=True, color="7A7A7A", size=8)

    p = doc.add_paragraph(style="Title")
    p.paragraph_format.space_before = Pt(42)
    add_text(p, "面向中哈跨境流域的\n虚拟水文站实验总报告", bold=True, color=DARK_BLUE, size=34)

    p = doc.add_paragraph(style="Subtitle")
    add_text(p, "三情景建模、GNN 骨架审计与统一安全输出", color=MID_GRAY, size=14)

    add_callout(
        doc,
        "报告定位",
        "本报告将自然河道、水库/水工建筑物、农业引水—下渗—地下水回补三类情景统一到同一虚拟水文站交付体系中。所有结论均以证据门槛和安全门控为边界，不把未通过监督与外部验证的模型输出解释为可靠流量。",
        fill=PALE_BLUE,
    )

    table = doc.add_table(rows=4, cols=2)
    set_table_geometry(table, [0.28, 0.72])
    set_table_borders(table, color="FFFFFF", size=0)
    details = [
        ("项目版本", "DeepBas-VHS-GT-Lite-v0.1"),
        ("统一输出", "3 个虚拟站 · 2,555 行 · 2,488 行有效流量"),
        ("质量状态", "负流量 0 · 站点-日期重复 0 · 自动测试 48 项通过"),
        ("交付范围", "中文总报告、关键实验表、虚拟站状态、复现材料与限制说明"),
    ]
    for row, (key, value) in zip(table.rows, details):
        set_cell_shading(row.cells[0], GRAY)
        for idx, text in enumerate((key, value)):
            p = row.cells[idx].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            add_text(p, text, bold=(idx == 0), color=(DARK_BLUE if idx == 0 else TEXT), size=9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(55)
    ribbon = doc.add_table(rows=1, cols=3)
    set_table_geometry(ribbon, [0.34, 0.33, 0.33])
    set_table_borders(ribbon, color=BLUE, size=0)
    for cell, (top, bottom) in zip(ribbon.rows[0].cells, [
        ("自然河道", "几何状态 / 流量暂缓"),
        ("水库情景", "历史缺测重建已授权"),
        ("农业循环", "端点基线 / 修正关闭"),
    ]):
        set_cell_shading(cell, BLUE)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_text(p, top, bold=True, color=WHITE, size=10)
        p2 = cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_text(p2, bottom, color=WHITE, size=8.5)

    add_section_break(doc)


def build():
    manifest = load_json("outputs/virtual_station_mainline/unified_virtual_station_delivery/final_delivery_manifest.json")
    statuses = load_csv("outputs/virtual_station_mainline/unified_virtual_station_delivery/unified_virtual_station_status.csv")
    natural = load_json("outputs/virtual_station_mainline/natural_reach_gnn_input_round/natural_reach_gnn_input_summary.json")
    reservoir = load_json("outputs/virtual_station_mainline/reservoir_regulation_head_round/reservoir_regulation_summary.json")
    agriculture = load_json("outputs/virtual_station_mainline/agriculture_vhs_integration_round/agriculture_vhs_integration_manifest.json")
    falsification = load_json("outputs/virtual_station_mainline/irrigation_memory_falsification_round/memory_falsification_summary.json")
    shared = load_json("outputs/virtual_station_mainline/shared_backbone_negative_transfer_round/shared_backbone_negative_transfer_summary.json")
    partial = load_json("outputs/virtual_station_mainline/partial_shared_backbone_round/partial_shared_backbone_summary.json")
    external = load_json("outputs/virtual_station_mainline/external_2000_2001/frozen_predictions/blind_scoring/external_validation_summary.json")

    doc = Document()
    setup_document(doc)
    cover(doc)

    add_heading(doc, "执行摘要", 1)
    add_body(doc, "本项目已完成三类虚拟水文站的统一数据接口、情景路由、安全门控、关键实验验证与最终输出。统一交付包含 3 个虚拟站、2,555 条站点—日期记录，其中 2,488 条提供非缺失流量；未发现负流量和重复站点—日期记录。最终架构不共享跨情景可训练权重，仅共享数据模式、证据门槛、非负约束、来源追踪和输出格式。")
    add_callout(doc, "核心结论", "目前可以稳定交付的是“分情景、分证据等级”的虚拟站产品，而不是一个对所有河段统一出流量的黑箱模型。水库历史缺测重建已达到授权条件；农业站保留无目标标签构造的端点基线；自然河道因缺少同期 Q/H 监督，正确做法是暂缓流量输出。", fill=PALE_GREEN)

    status_rows = []
    status_map = {
        "natural_reach": ("自然河道", "暂缓", "仅卫星几何状态，不作流量结论"),
        "reservoir_or_hydraulic_structure": ("水库/水工建筑物", "已授权", "历史有测站缺测重建；不等同于无测站泄量反演"),
        "irrigation_groundwater_return_loop": ("农业引水—地下水回补", "基线可用", "严格端点基线；农业修正与区间关闭"),
    }
    for s in statuses:
        label, state, claim = status_map[s["regime"]]
        status_rows.append([s["station_name"], label, f'{s["first_date"]}\n— {s["last_date"]}', s["rows"], s["discharge_output_rows"], state, claim])
    add_table(doc, ["虚拟站", "情景", "时间范围", "记录", "流量输出", "状态", "允许表述"], status_rows, [0.08, 0.16, 0.16, 0.07, 0.09, 0.10, 0.34], font_size=7.5, first_col_bold=True)
    add_caption(doc, "表 1  统一虚拟水文站最终状态（状态字段以安全门控为准）")
    add_picture(doc, "outputs/virtual_station_mainline/unified_virtual_station_delivery/unified_virtual_station_overview.png", "图 1  统一虚拟水文站交付概览", alt="三类虚拟水文站的统一输出状态与时间覆盖")

    add_heading(doc, "1 研究问题与老师要求的三类情景", 1)
    add_body(doc, "老师提出的主线不是单一自然河道宽度反演，而是要求虚拟水文站同时覆盖：天然河道断面、水库或水工建筑物下游、以及上下游站点之间受农田引水—灌溉—下渗—地下水回补影响的河段。三类情景的观测机制不同，因此必须采用分情景专家模型与不同的证据门槛。")
    add_table(doc, ["情景", "老师关注的问题", "本项目的技术回答", "当前结论"], [
        ["自然河道", "能否由河宽、坡度和断面反推 Q？", "卫星多源河宽/水面高程作为几何输入；Q/H 监督缺失时关闭流量损失与物理锚定", "数据层完成，监督训练被证据门槛阻断"],
        ["水库/建筑物", "有历史流量与宽度时能否反推？", "训练期释放比边界 + 因果滚动异常 + 有界调节头", "仅授权历史有测站缺测重建"],
        ["农业循环", "引水、下渗和回补会否改变上下游 Q 关系？", "端点几何基线 + 快/慢回补诊断 + 季节错位安慰剂检验", "农业机制不具特异性，修正关闭"],
    ], [0.14, 0.25, 0.38, 0.23], font_size=8.2, first_col_bold=True)
    add_caption(doc, "表 2  三类情景与技术路线的对应关系")

    add_heading(doc, "2 数据与实验协议", 1)
    add_heading(doc, "2.1 数据来源与时间结构", 2)
    add_body(doc, "自然河道站 BYBLK 使用 Landsat、Sentinel-2 与 SWOT 构造不插值的观测日几何特征；水库站 DSK 使用 1978—1983 年历史资料实施严格时间切分；农业站 XQM 使用 ALAR—XQM—AQK 三点拓扑和 2005 年同期日流量。现有可用流量资料主要止于 2011 年以前，这一现实决定了模型必须明确区分历史回放、已打开测试和真正外部验证。")
    add_table(doc, ["模块", "核心数据", "时间/样本", "标签使用规则"], [
        ["自然河道 BYBLK", f"Landsat {natural['recent_landsat_observation_days']} 天；Sentinel-2 {natural['sentinel_observation_days']} 天；SWOT {natural['swot_observation_days']} 天", f"{natural['daily_rows']} 日\n{natural['date_range'][0]}—{natural['date_range'][1]}", "同期 Q=0 天、H=0 天；缺测不插值"],
        ["水库 DSK", "历史流量 + 物理参考量 + 因果异常特征", "训练 1978—1981；验证 1982；封存测试 1983", "测试标签不参与选模；不使用目标流量滞后"],
        ["农业 XQM", "上下游端点流量 + 日历 + 农业诊断代理", "2005 年 300 日；测试段 55 日", "XQM 标签不用于构造端点点预测；农业特征仅作诊断"],
    ], [0.18, 0.34, 0.25, 0.23], font_size=8.3, first_col_bold=True)
    add_caption(doc, "表 3  数据与标签使用协议")

    add_heading(doc, "2.2 验证纪律", 2)
    add_body(doc, "所有模型均遵循时间顺序切分、目标观测从输入中屏蔽、仅用训练期估计约束或归一化参数、测试期不再调参。已经查看过标签的区间只用于发展性审计，不再宣称为新的盲测。对外部 2000—2001 冻结预测的评分显示，虚拟站集成 NSE=0.419，低于预先声明的面积缩放 lag-1 基线 NSE=0.511，因此未晋级。")

    add_heading(doc, "3 统一虚拟水文站架构", 1)
    add_body(doc, "最终架构采用“情景识别 → 独立专家模型 → 证据门槛 → 安全路由 → 统一输出”的流程。三个专家不共享可训练编码器权重；共享的是字段模式、缺测掩码、非负约束、证据状态、来源追踪和输出契约。安全门关闭时，模型必须精确回退到物理参考或不输出 Q。")
    add_table(doc, ["共享层", "是否共享", "原因"], [
        ["输入字段、掩码、来源追踪", "是", "保证三情景在同一输出协议中可比较、可审计"],
        ["非负约束与证据门槛", "是", "避免负流量和越过证据边界的自动晋级"],
        ["可训练编码器/归一化", "否", "跨情景全共享与部分共享均出现负迁移"],
        ["情景输出头与修正边界", "否", "自然、水库、农业具有不同过程与允许表述"],
    ], [0.30, 0.16, 0.54], font_size=8.7, first_col_bold=True)
    add_caption(doc, "表 4  统一层与情景专家的职责划分")

    add_heading(doc, "4 自然河道虚拟站：数据层完成，流量层暂缓", 1)
    add_heading(doc, "4.1 已完成工作", 2)
    add_body(doc, f"BYBLK（SWORD 河段 {natural['sword_reach_id']}）已构造 {natural['daily_rows']} 天的 GNN 日尺度输入框架，包含 Landsat 河宽、Sentinel-2 河宽、SWOT 水面高程/河宽/坡度及其不确定性、观测掩码和空间位置类别。所有卫星几何缺测保留为 NaN，不做时间插值，从源头避免把无观测日伪装为连续观测。")
    add_table(doc, ["证据项", "当前值", "最小门槛", "判定"], [
        ["同期卫星—流量配对", "0", "≥30", "未通过"],
        ["SWOT—水位配对", "0", "≥10", "未通过"],
        ["流量覆盖年数", "0", "≥2 年", "未通过"],
        ["多源卫星几何观测日", f"Landsat {natural['recent_landsat_observation_days']} / Sentinel-2 {natural['sentinel_observation_days']} / SWOT {natural['swot_observation_days']}", "用于输入，不替代 Q/H 标签", "输入层完成"],
    ], [0.27, 0.25, 0.25, 0.23], font_size=8.5, first_col_bold=True)
    add_caption(doc, "表 5  自然河道监督学习证据门槛")
    add_picture(doc, "outputs/virtual_station_mainline/natural_sensor_harmonization_round/sensor_harmonization_diagnostics.png", "图 2  自然河道多源传感器一致性诊断", alt="Landsat、Sentinel-2 和 SWOT 河道几何观测的一致性诊断")
    add_heading(doc, "4.2 物理约束与当前决定", 2)
    add_body(doc, "历史 Manning 约束不能在缺少同期水位、断面与流量监督的条件下稳定识别 Q；早期 2001 年评估曾得到 NSE=-2.424，说明静态坡度与单一河宽不足以作为可迁移流量关系。当前正确的物理限制是：Q≥0；仅在有可靠断面/水位/流量配对时启用水力损失；无监督时不生成流量。这不是实验失败，而是证据门槛发挥作用。")
    add_callout(doc, "自然河道站可交付内容", "可交付卫星观测日期、河宽/水面高程/坡度及不确定性、观测掩码和监督就绪状态；不可交付连续 Q 序列，也不可把几何变化直接解释为流量变化。", fill=PALE_AMBER)

    add_heading(doc, "5 水库/水工建筑物虚拟站：历史缺测重建已授权", 1)
    add_heading(doc, "5.1 模型与约束", 2)
    add_body(doc, "DSK 采用有界水库调节头：以外部物理参考为中心，用季节项与 7/30/90 日因果异常特征估计受控修正；释放比被限制在训练期第 1—99 百分位 [0.380, 4.105] 内，并强制 Q≥0。该模型使用 1978—1982 年目标站标签，因此只能用于历史有测站缺测重建。")
    test_metrics = {m["method"]: m for m in reservoir["daily_metrics"] if m["split"] == "test"}
    add_table(doc, ["1983 封存测试方法", "RMSE (m³/s)", "MAE", "NSE", "KGE", "PBIAS (%)"], [
        ["物理基线", f"{test_metrics['physical_baseline']['rmse']:.2f}", f"{test_metrics['physical_baseline']['mae']:.2f}", f"{test_metrics['physical_baseline']['nse']:.3f}", f"{test_metrics['physical_baseline']['kge']:.3f}", f"{test_metrics['physical_baseline']['pbias']:.2f}"],
        ["全局比例", f"{test_metrics['global_ratio']['rmse']:.2f}", f"{test_metrics['global_ratio']['mae']:.2f}", f"{test_metrics['global_ratio']['nse']:.3f}", f"{test_metrics['global_ratio']['kge']:.3f}", f"{test_metrics['global_ratio']['pbias']:.2f}"],
        ["有界调节头", f"{test_metrics['bounded_regulation_head']['rmse']:.2f}", f"{test_metrics['bounded_regulation_head']['mae']:.2f}", f"{test_metrics['bounded_regulation_head']['nse']:.3f}", f"{test_metrics['bounded_regulation_head']['kge']:.3f}", f"{test_metrics['bounded_regulation_head']['pbias']:.2f}"],
    ], [0.30, 0.14, 0.12, 0.12, 0.12, 0.20], font_size=8.5, first_col_bold=True)
    add_caption(doc, "表 6  水库情景 1983 年封存测试结果")
    add_picture(doc, "outputs/virtual_station_mainline/reservoir_regulation_head_round/reservoir_regulation_diagnostics.png", "图 3  水库调节头训练、验证和测试诊断", alt="水库物理基线、比例基线与有界调节头的诊断对比")
    add_heading(doc, "5.2 结论边界", 2)
    add_body(doc, "有界调节头在 1983 年日尺度测试达到 NSE=0.693、KGE=0.808、RMSE=31.63 m³/s，明显优于物理基线和全局比例基线。年平均流量为 31.00 m³/s，接近观测 29.66 m³/s。模型可用于 DSK 历史缺测时段重建，但不能迁移到完全无测水库，也不能表述为已恢复真实水库泄量过程；如需后者，必须补充库水位、库容或闸门泄量。")

    add_heading(doc, "6 农业引水—地下水回补虚拟站：机制诊断完成", 1)
    add_heading(doc, "6.1 点预测与不确定性", 2)
    agri_test = agriculture["previously_opened_test"]
    add_body(doc, "XQM 位于 ALAR 与 AQK 之间。点预测使用上下游端点流量的几何均值，构造过程不使用 XQM 观测标签；农业头则只增加端点差、暖季门控、快速回补和慢速储量等诊断特征。因缺少实测引水、灌区面积和地下水代理，农业修正门保持关闭。")
    add_table(doc, ["测试项", "结果", "解释"], [
        ["严格端点基线（55 日）", f"RMSE={agri_test['rmse']:.2f}; NSE={agri_test['nse']:.3f}; KGE={agri_test['kge']:.3f}; PBIAS={agri_test['pbias']:.2f}%", "可作为标签独立的物理点预测"],
        ["90% 分割保形区间", f"半径={agriculture['uncertainty']['radius_m3s']:.1f} m³/s；半径/中位预测={agriculture['uncertainty']['radius_to_test_median_prediction_ratio']:.2f}", "覆盖率虽高但区间过宽，不具操作信息量"],
        ["农业修正", "correction_enabled=0", "未通过代理数据、季节特异性与盲测增益三重门槛"],
    ], [0.23, 0.43, 0.34], font_size=8.4, first_col_bold=True)
    add_caption(doc, "表 7  农业虚拟站的点预测、区间与修正状态")
    add_picture(doc, "outputs/virtual_station_mainline/agriculture_vhs_integration_round/agriculture_vhs_integration_diagnostics.png", "图 4  农业虚拟站点预测与诊断特征", alt="上下游端点基线、农业诊断特征和测试期误差")

    add_heading(doc, "6.2 反证实验", 2)
    spec = falsification["specificity"]
    gate = falsification["teacher_aligned_gate"]
    add_body(doc, f"对 69 天左右的慢速记忆解释进行了 35 个季节相位错位安慰剂检验。老师对齐的暖季门控在验证期 RMSE={gate['validation_rmse_m3s']:.2f} m³/s、NSE={gate['validation_nse']:.3f}，在已打开测试期 RMSE={gate['test_rmse_m3s']:.2f} m³/s、NSE={gate['test_nse']:.3f}。共有 {spec['placebos_outperform_teacher_gate_on_validation']}/35 个安慰剂在验证期更好，{spec['placebos_outperform_teacher_gate_on_test']}/35 个在测试期更好，因此不能把慢速状态解释为已识别的农业因果循环。")
    add_callout(doc, "农业模块完成度", "现有数据可完成的 6/6 层实验已完成；完整证据矩阵约为 6/8（75%）。剩余两类证据依赖外部数据：实测引水/灌区/地下水代理，以及一个未被使用的 2011 年以前独立年份。", fill=PALE_AMBER)

    add_heading(doc, "7 GNN 共同骨架审计", 1)
    add_heading(doc, "7.1 全共享与部分共享均存在负迁移", 2)
    add_body(doc, "项目已实现同一时刻节点编码、定向消息传递和三情景输出头，并通过“门关闭时精确回退物理参考”的契约测试（最大差值 0.0 m³/s）。随后比较全共享、部分共享和完全分离编码器。由于 2005 年目标标签已在此前轮次查看，这些结果被标记为结构发展审计，不作为新的盲测结论。")
    add_table(doc, ["情景", "全共享：ΔNSE vs 分离", "全共享 RMSE 比", "部分共享：ΔNSE vs 分离", "部分共享 RMSE 比", "决定"], [
        ["水库", f"{shared['negative_transfer']['reservoir']['shared_minus_separate_nse']:.3f}", f"{shared['negative_transfer']['reservoir']['shared_to_separate_rmse_ratio']:.3f}", f"{partial['decisions']['reservoir']['partial_minus_separate_nse']:.3f}", f"{partial['decisions']['reservoir']['partial_to_separate_rmse_ratio']:.3f}", "分离编码器"],
        ["农业", f"{shared['negative_transfer']['agriculture']['shared_minus_separate_nse']:.3f}", f"{shared['negative_transfer']['agriculture']['shared_to_separate_rmse_ratio']:.3f}", f"{partial['decisions']['agriculture']['partial_minus_separate_nse']:.3f}", f"{partial['decisions']['agriculture']['partial_to_separate_rmse_ratio']:.3f}", "分离编码器"],
    ], [0.12, 0.19, 0.16, 0.20, 0.17, 0.16], font_size=8.0, first_col_bold=True)
    add_caption(doc, "表 8  跨情景共享导致的负迁移（负 ΔNSE、RMSE 比>1 表示变差）")
    add_picture(doc, "outputs/virtual_station_mainline/partial_shared_backbone_round/partial_shared_architecture_comparison.png", "图 5  全共享、部分共享与分离架构比较", alt="不同共享策略在水库和农业情景的性能比较")
    add_heading(doc, "7.2 最终架构决定", 2)
    add_body(doc, "全共享使水库和农业相对分离模型均变差；仅共享消息传递层仍存在材料性负迁移。因此最终保留情景独立编码器和独立输出头，只在外部安全路由器中统一状态、格式和回退规则。自然河道头继续冻结，直至获得同期 Q/H 监督。")

    add_heading(doc, "8 统一输出与虚拟站状态", 1)
    add_heading(doc, "8.1 最终输出质量", 2)
    add_table(doc, ["质量指标", "结果", "验收判定"], [
        ["总站点数", manifest["stations"], "3 类情景均进入统一文件"],
        ["总记录数", manifest["rows"], "覆盖 3 个站点的不同时期"],
        ["非缺失流量记录", manifest["nonmissing_discharge_rows"], "自然站 67 个几何观测日不输出 Q"],
        ["负流量记录", manifest["negative_discharge_rows"], "通过；满足 Q≥0"],
        ["重复站点—日期", manifest["duplicate_station_date_rows"], "通过；主键唯一"],
        ["SHA-256", manifest["output_sha256"], "可用于交付文件完整性校验"],
    ], [0.24, 0.32, 0.44], font_size=8.5, first_col_bold=True)
    add_caption(doc, "表 9  统一输出验收结果")
    add_heading(doc, "8.2 输出字段的解释原则", 2)
    add_body(doc, "每条记录同时保存虚拟站编号、日期、情景、点流量或缺失值、采用的方法、主状态、修正是否启用、允许表述范围和数据来源。状态字段不是附注，而是产品的一部分：任何下游分析都必须先读取状态，再决定是否可以使用流量值。")
    add_table(doc, ["状态", "含义", "下游可执行动作"], [
        ["withheld_insufficient_evidence", "证据不足，流量被主动暂缓", "仅使用几何/覆盖状态，不填补 Q"],
        ["specialist_output_authorized", "情景专家通过指定范围验收", "仅在 claim_scope 范围内使用"],
        ["physical_baseline_fallback", "学习修正未通过，回退物理基线", "可使用点基线，同时保留机制不确定性说明"],
    ], [0.30, 0.36, 0.34], font_size=8.3, first_col_bold=True)
    add_caption(doc, "表 10  虚拟站状态与使用规则")

    add_heading(doc, "9 可复现材料", 1)
    add_body(doc, "复现入口按“数据准备—情景实验—统一交付—自动测试”组织。所有路径均相对项目根目录，统一输出清单记录源文件与 SHA-256。运行环境以 pyproject.toml 为依赖入口；自动测试当前为 48 项通过。报告不包含 CDS 私人 API token，密钥应只保存在用户目录的 .cdsapirc 中。")
    add_table(doc, ["用途", "关键材料", "复现说明"], [
        ["统一输出", "scripts/generate_unified_virtual_station_output.py\noutputs/.../unified_virtual_station_delivery/", "生成最终日表、状态表、概览图和交付清单"],
        ["安全路由", "src/vhs/router.py\nsrc/vhs/regime_model.py", "实现情景选择、门控、边界与物理回退"],
        ["自然河道", "scripts/prepare_natural_reach_gnn_inputs.py\noutputs/.../natural_reach_gnn_input_round/", "重建多源卫星日尺度特征与监督就绪审计"],
        ["水库", "scripts/evaluate_reservoir_regulation_head.py\noutputs/.../reservoir_regulation_head_round/", "重现训练/验证/1983 封存测试及约束"],
        ["农业", "src/vhs/agriculture.py\nscripts/integrate_agriculture_virtual_station_head.py", "重现端点基线、农业诊断、回补记忆与安全关闭"],
        ["共享审计", "scripts/evaluate_shared_backbone_negative_transfer.py\nscripts/evaluate_partial_shared_backbone.py", "比较全共享、部分共享和分离编码器"],
        ["自动测试", "tests/\npytest -q", "当前 48 项测试通过；建议在交付前再次运行"],
    ], [0.18, 0.43, 0.39], font_size=7.9, first_col_bold=True)
    add_caption(doc, "表 11  复现材料索引")

    add_heading(doc, "10 当前结论、限制与下一步", 1)
    add_heading(doc, "10.1 可以向老师汇报的结论", 2)
    add_body(doc, "第一，已经按照老师要求把自然河道、水库和农业循环三种情况分开解决，并在同一虚拟水文站输出协议中整合。第二，水库历史缺测重建是当前最强的定量结果；自然河道已完成数据与几何输入但因缺乏同期 Q/H 正确暂缓；农业循环已完成现有数据条件下的机制反证，证明不能把季节相关性直接当成灌溉—地下水回补因果。第三，GNN 共同骨架完成了结构审计，实验结果支持“分情景独立专家 + 统一安全路由”，而不是跨情景共享权重。")
    add_heading(doc, "10.2 关键限制", 2)
    add_table(doc, ["限制", "影响", "解除条件"], [
        ["自然站缺少同期 Q/H", "不能率定河宽—流量或断面水力关系", "至少 30 个卫星—Q 配对、10 个 SWOT—H 配对和 2 年流量"],
        ["水库缺少库水位/库容/泄量", "只能重建历史站流量，不能解释真实调度", "补充水位、库容曲线、闸门或泄量记录"],
        ["农业缺少引水/灌区/地下水代理", "农业修正无因果特异性，区间过宽", "补充引水量、灌溉面积、地下水位或基流代理"],
        ["近年流量资料不足", "不能直接证明对近期水文状态的泛化", "获取新的独立年份或开展现场同步观测"],
    ], [0.24, 0.37, 0.39], font_size=8.3, first_col_bold=True)
    add_caption(doc, "表 12  当前限制与数据补充优先级")
    add_heading(doc, "10.3 建议下一轮优先级", 2)
    add_body(doc, "优先级 1：向老师或数据管理部门申请自然河道同期流量、水位和断面资料，使 BYBLK 从“几何站”升级为可监督虚拟流量站。优先级 2：如短期拿不到自然站标签，优先补充水库水位/库容或农业引水/地下水代理，而不是继续扩大黑箱模型。优先级 3：保留当前统一输出作为基线版本；任何新模型必须在未打开独立时段上超过预先声明基线后，才允许改变状态字段。")
    add_callout(doc, "最终判断", "本阶段的工程任务可以结束并交付：统一虚拟站输出已生成、三类情景状态清晰、关键定量结果和失败证据均已留档、复现链完整。下一阶段的主要瓶颈不是继续堆叠模型，而是获取能够解除证据门槛的新观测数据。", fill=PALE_GREEN)

    add_heading(doc, "附录 A 统一交付文件", 1)
    add_table(doc, ["文件", "用途"], [
        ["unified_virtual_station_delivery/\nunified_virtual_station_output.csv", "2,555 行统一日尺度虚拟站输出"],
        ["unified_virtual_station_delivery/\nunified_virtual_station_status.csv", "三站时间范围、输出数、方法、状态和允许表述"],
        ["unified_virtual_station_delivery/\nfinal_delivery_manifest.json", "源文件、路由决定、质量统计和 SHA-256"],
        ["unified_virtual_station_delivery/\nunified_virtual_station_final_report_zh.md", "机器可读交付旁的中文简报"],
    ], [0.66, 0.34], font_size=8.0)
    add_caption(doc, "表 A-1  最终交付目录")

    add_heading(doc, "附录 B 指标释义", 1)
    add_table(doc, ["指标", "解释", "本报告使用方式"], [
        ["RMSE / MAE", "误差幅度，越小越好", "比较点预测的绝对误差"],
        ["NSE", "相对观测均值基线的效率；1 最优，0 等同均值，负值更差", "核心时序拟合指标"],
        ["KGE / PBIAS", "KGE 综合相关、变异与偏差；PBIAS 为总体偏差百分比", "判断过程一致性和系统偏差"],
        ["ΔNSE / RMSE 比", "共享模型相对分离模型的变化", "ΔNSE<0 且 RMSE 比>1 视为负迁移证据"],
    ], [0.18, 0.45, 0.37], font_size=7.6, first_col_bold=True, trailing=False)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
