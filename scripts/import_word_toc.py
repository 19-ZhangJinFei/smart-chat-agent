"""仅迁回Word更新后的原生目录及标题书签，保留模板其他部件。

Word在独立副本更新域；本脚本避免把Word全包重写带回原模板。
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import zipfile

from lxml import etree as E

from apply_school_template import NS, tag, text, xml


def import_toc(source, refreshed, output):
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    with zipfile.ZipFile(refreshed) as archive:
        word = {name: archive.read(name) for name in archive.namelist()}
    original = E.fromstring(parts["word/document.xml"])
    updated = E.fromstring(word["word/document.xml"])
    body, word_body = original.find("w:body", NS), updated.find("w:body", NS)

    def bounds(container):
        nodes = list(container)
        start = next(i for i, item in enumerate(nodes) if text(item) == "目录")
        end = next(i for i, item in enumerate(nodes[start+1:], start+1)
                   if text(item) == "1　需求分析")
        return start+1, end

    start, end = bounds(body)
    word_start, word_end = bounds(word_body)
    toc = list(word_body)[word_start:word_end]
    if not any(item.xpath('.//w:instrText[contains(text(),"TOC ")]', namespaces=NS) for item in toc):
        raise ValueError("Word副本未包含已更新的原生目录域")
    for item in list(body)[start:end]:
        body.remove(item)
    for offset, item in enumerate(toc):
        body.insert(start+offset, deepcopy(item))
    # PAGEREF书签只复制到同文本同样式的真正标题，不匹配目录缓存行。
    headings = {}
    for item in word_body:
        style = item.find("w:pPr/w:pStyle", NS)
        if style is not None and item.findall("w:bookmarkStart", NS):
            headings[text(item)] = item
    for item in body:
        style = item.find("w:pPr/w:pStyle", NS)
        if style is None or not style.get(tag("val"), "").startswith("Heading"):
            continue
        donor = headings.get(text(item))
        if donor is None:
            continue
        for bookmark in donor.findall("w:bookmarkStart", NS):
            item.insert(1, deepcopy(bookmark))
        for bookmark in donor.findall("w:bookmarkEnd", NS):
            item.append(deepcopy(bookmark))
    parts["word/document.xml"] = xml(original)
    styles = E.fromstring(parts["word/styles.xml"])
    known = {style.get(tag("styleId")) for style in styles.findall("w:style", NS)}
    for style in E.fromstring(word["word/styles.xml"]).findall("w:style", NS):
        if style.get(tag("styleId")) in {"TOC1", "TOC2"} - known:
            styles.append(deepcopy(style))
    parts["word/styles.xml"] = xml(styles)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    audit_path = source.with_suffix(".template-audit.json")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["word_fields_refreshed"] = True
    audit["toc_refresh"] = "Microsoft Word，仅迁回目录缓存、书签及新增TOC1/TOC2样式"
    audit["preserved_parts"].remove("word/styles.xml")
    audit["edited_parts"].append("word/styles.xml")
    audit["existing_template_styles_preserved"] = True
    output.with_suffix(".template-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print("原生目录缓存已迁回；原模板样式节点、页眉页脚与其余部件保留。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for argument in ["source", "refreshed", "output"]:
        parser.add_argument(f"--{argument}", type=Path, required=True)
    args = parser.parse_args()
    import_toc(args.source, args.refreshed, args.output)
