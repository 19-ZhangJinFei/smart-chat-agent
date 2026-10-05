"""将内容稿迁入原始学校DOCX，逐字节保留未编辑ZIP部件。

原模板和个人信息在外部私有目录；不使用LibreOffice保存模板。
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import zipfile

from lxml import etree as E

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "r": R}


def tag(name):
    return f"{{{W}}}{name}"


def xml(element):
    return E.tostring(element, xml_declaration=True, encoding="UTF-8", standalone=True)


def text(element):
    return "".join(element.xpath(".//w:t/text()", namespaces=NS))


def replace_text(paragraph, value, cover=False):
    prototype = paragraph.find("w:r/w:rPr", NS)
    for item in list(paragraph):
        if item.tag != tag("pPr"):
            paragraph.remove(item)
    run = E.SubElement(paragraph, tag("r"))
    properties = deepcopy(prototype) if prototype is not None else E.Element(tag("rPr"))
    for shade in properties.findall("w:shd", NS):
        properties.remove(shade)
    color = properties.find("w:color", NS)
    if color is None:
        color = E.SubElement(properties, tag("color"))
    color.set(tag("val"), "000000")
    run.append(properties)
    content = E.SubElement(run, tag("t"))
    content.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    content.text = value


def apply(reference, content, profile, output):
    if output.resolve() in {reference.resolve(), content.resolve()}:
        raise ValueError("输出不得覆盖原模板或内容稿")
    with zipfile.ZipFile(reference) as archive:
        original = {name: archive.read(name) for name in archive.namelist()}
    with zipfile.ZipFile(content) as archive:
        donor = {name: archive.read(name) for name in archive.namelist()}
    result = dict(original)
    doc = E.fromstring(original["word/document.xml"])
    body = doc.find("w:body", NS)
    paragraphs = body.findall("w:p", NS)
    tables = body.findall("w:tbl", NS)
    cover = deepcopy(tables[0])
    info = json.loads(profile.read_text(encoding="utf-8-sig"))
    values = ["智聊——基于LangChain的智能客服系统", info["学院"], info["专业班级"],
              info["姓名"], info["学号"], info["指导教师"], info["答辩日期"]]
    for row, value in zip(cover.findall("w:tr", NS), values):
        cell = row.findall("w:tc", NS)[1]
        replace_text(cell.find("w:p", NS), value, cover=True)
    heading = {level: deepcopy(paragraphs[index]) for level, index in [(1,13),(2,15),(3,50)]}
    basic = deepcopy(paragraphs[52])
    cap = deepcopy(paragraphs[23])
    section = deepcopy(body.find("w:sectPr", NS))
    # 原封面的空白、标题与表格位置均保留，删除整个使用说明页。
    cover_nodes = []
    for item in body:
        if item.tag == tag("p") and text(item) == "报告使用说明":
            break
        cover_nodes.append(deepcopy(item))
    for i, item in enumerate(cover_nodes):
        if item.tag == tag("tbl"):
            cover_nodes[i] = cover
    for item in list(body):
        body.remove(item)
    for item in cover_nodes:
        body.append(item)
    # donor只提供内容与图片；正文段落和表格均从模板组件重新实例化。
    source_body = E.fromstring(donor["word/document.xml"]).find("w:body", NS)
    nodes = list(source_body)
    first = next(i for i, item in enumerate(nodes) if text(item) == "目录")
    pending_break = False
    for index, source in enumerate(nodes[first:]):
        if source.tag == tag("sectPr"):
            continue
        if source.tag == tag("tbl"):
            count = len(source.find("w:tr", NS).findall("w:tc", NS))
            prototype = tables[5] if count == 6 else tables[3] if count == 4 else tables[1]
            target = deepcopy(prototype)
            rows = target.findall("w:tr", NS)
            for row in rows:
                target.remove(row)
            # 两列表采用原三列表的视觉组件，几何沿用内容稿明确列宽。
            grid = target.find("w:tblGrid", NS)
            target.replace(grid, deepcopy(source.find("w:tblGrid", NS)))
            for number, source_row in enumerate(source.findall("w:tr", NS)):
                row = deepcopy(rows[0 if number == 0 else 1])
                source_cells = source_row.findall("w:tc", NS)
                cells = row.findall("w:tc", NS)
                for cell in cells:
                    row.remove(cell)
                for position, source_cell in enumerate(source_cells):
                    cell = deepcopy(cells[min(position, len(cells)-1)])
                    cell_props = cell.find("w:tcPr", NS)
                    width = source_cell.find("w:tcPr/w:tcW", NS)
                    old_width = cell_props.find("w:tcW", NS)
                    if width is not None:
                        if old_width is not None:
                            cell_props.remove(old_width)
                        cell_props.append(deepcopy(width))
                    p = cell.find("w:p", NS)
                    replace_text(p, text(source_cell))
                    if number == 0:
                        props = p.find("w:pPr", NS)
                        justify = props.find("w:jc", NS)
                        if justify is None:
                            justify = E.SubElement(props, tag("jc"))
                        justify.set(tag("val"), "center")
                    for extra in cell.findall("w:p", NS)[1:]:
                        cell.remove(extra)
                    row.append(cell)
                props = row.find("w:trPr", NS)
                if props is None:
                    props = E.SubElement(row, tag("trPr"))
                if props.find("w:cantSplit", NS) is None:
                    E.SubElement(props, tag("cantSplit"))
                if number == 0 and props.find("w:tblHeader", NS) is None:
                    E.SubElement(props, tag("tblHeader"))
                target.append(row)
            body.append(target)
            continue
        if source.tag != tag("p"):
            raise ValueError("内容稿包含未支持组件")
        value = text(source)
        if not value and source.xpath('.//w:br[@w:type="page"]', namespaces=NS):
            pending_break = True
            continue
        style = source.find("w:pPr/w:pStyle", NS)
        level = int(style.get(tag("val"))[-1]) if style is not None and re.fullmatch(r"Heading[123]", style.get(tag("val"), "")) else None
        is_picture = bool(source.xpath(".//w:drawing", namespaces=NS))
        is_field = bool(source.xpath(".//w:fldChar", namespaces=NS))
        is_code = bool(source.xpath('.//w:rFonts[@w:ascii="Consolas"]', namespaces=NS))
        if level:
            target = deepcopy(heading[level])
            replace_text(target, value)
            props = target.find("w:pPr", NS)
            keep = props.find("w:keepNext", NS)
            if keep is None:
                keep = E.SubElement(props, tag("keepNext"))
            keep.set(tag("val"), "true")
            if level == 1:
                before = props.find("w:pageBreakBefore", NS)
                if before is None:
                    E.SubElement(props, tag("pageBreakBefore"))
                # 内容稿章节前的显式分页合并为标题分页属性。
                previous = body[-1] if len(body) else None
                if previous is not None and previous.xpath('.//w:br[@w:type="page"]', namespaces=NS):
                    body.remove(previous)
        elif is_picture or is_field or is_code or not value:
            target = deepcopy(source)
        else:
            target = deepcopy(cap if re.match(r"^[图表]\d+　", value) else basic)
            replace_text(target, value)
            props = target.find("w:pPr", NS)
            if value == "目录":
                props = deepcopy(heading[1].find("w:pPr", NS))
                ps = props.find("w:pStyle", NS)
                if ps is not None:
                    props.remove(ps)
                target.replace(target.find("w:pPr", NS), props)
                E.SubElement(props, tag("jc")).set(tag("val"), "center")
                E.SubElement(props, tag("pageBreakBefore"))
                rpr = target.find("w:r/w:rPr", NS)
                size = rpr.find("w:sz", NS)
                size.set(tag("val"), "32")
            elif not re.match(r"^[图表]\d+　", value):
                indent = props.find("w:ind", NS)
                if indent is not None:
                    indent.set(tag("firstLineChars"), "200")
                if value.startswith(("实现思路：", "关键代码：", "运行效果：")):
                    if indent is not None:
                        indent.set(tag("firstLine"), "0")
                        indent.set(tag("firstLineChars"), "0")
                    prefix, remainder = value.split("：", 1)
                    run = target.find("w:r", NS)
                    run.find("w:t", NS).text = prefix + "："
                    E.SubElement(run.find("w:rPr", NS), tag("b"))
                    if remainder:
                        extra = deepcopy(run)
                        extra.find("w:t", NS).text = remainder
                        extra.find("w:rPr", NS).remove(extra.find("w:rPr/w:b", NS))
                        target.append(extra)
                if re.match(r"^\[\d+\]", value):
                    indent.set(tag("firstLine"), "0")
                    indent.set(tag("firstLineChars"), "0")
                    justify = props.find("w:jc", NS)
                    justify.set(tag("val"), "left")
                    spacing = props.find("w:spacing", NS)
                    spacing.set(tag("line"), "240")
                    target.find("w:r/w:rPr/w:sz", NS).set(tag("val"), "21")
            else:
                E.SubElement(props, tag("keepNext" if value.startswith("表") else "keepLines"))
        if pending_break:
            properties = target.find("w:pPr", NS)
            if properties is None:
                properties = E.Element(tag("pPr"))
                target.insert(0, properties)
            if properties.find("w:pageBreakBefore", NS) is None:
                E.SubElement(properties, tag("pageBreakBefore"))
            pending_break = False
        body.append(target)
    body.append(section)
    rels = E.fromstring(original["word/_rels/document.xml.rels"])
    donor_rels = E.fromstring(donor["word/_rels/document.xml.rels"])
    used = {x.get("Id") for x in rels}
    mapping = {}
    for rel in donor_rels:
        if not rel.get("Type", "").endswith("/image"):
            continue
        number = 100
        while f"rId{number}" in used:
            number += 1
        new_id = f"rId{number}"
        used.add(new_id)
        mapping[rel.get("Id")] = new_id
        target = f"media/smartchat-{number}{Path(rel.get('Target')).suffix}"
        result[f"word/{target}"] = donor[f"word/{rel.get('Target')}"]
        item = deepcopy(rel)
        item.set("Id", new_id)
        item.set("Target", target)
        rels.append(item)
    for element in doc.iter():
        for key in [f"{{{R}}}embed", f"{{{R}}}link"]:
            if element.get(key) in mapping:
                element.set(key, mapping[element.get(key)])
    result["word/document.xml"] = xml(doc)
    result["word/_rels/document.xml.rels"] = xml(rels)
    settings = E.fromstring(original["word/settings.xml"])
    update = settings.find("w:updateFields", NS)
    if update is None:
        update = E.SubElement(settings, tag("updateFields"))
    update.set(tag("val"), "true")
    result["word/settings.xml"] = xml(settings)
    types = E.fromstring(original["[Content_Types].xml"])
    if not any(item.get("Extension") == "png" for item in types):
        E.SubElement(types, "{http://schemas.openxmlformats.org/package/2006/content-types}Default",
                     Extension="png", ContentType="image/png")
    result["[Content_Types].xml"] = xml(types)
    if "【" in text(doc) or "填写提示" in text(doc):
        raise ValueError("报告仍有模板占位符")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in result.items():
            archive.writestr(name, data)
    audit = {"reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
             "preserved_parts": [name for name in original if original[name] == result[name]],
             "edited_parts": [name for name in original if original[name] != result[name]],
             "new_parts": sorted(set(result)-set(original)), "word_fields_refreshed": False}
    output.with_suffix(".template-audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print("原模板组件已填充；未编辑部件逐字节保留，待Word域更新及渲染验收。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for argument in ["reference", "content", "profile", "output"]:
        parser.add_argument(f"--{argument}", type=Path, required=True)
    args = parser.parse_args()
    apply(args.reference, args.content, args.profile, args.output)
