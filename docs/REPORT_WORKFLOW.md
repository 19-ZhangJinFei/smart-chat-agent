# 学校模板报告生成与核对

原始学校DOCX、个人信息JSON、报告、PDF和材料包均保存在Git忽略的`artifacts/private`或项目外目录。公开仓库只包含生成工具和去身份化验收摘要。报告仍需本人理解、修改和亲自演练。

使用独立文档运行环境的Python（需要python-docx、Pillow、lxml），不把文档工具依赖加入后端运行依赖。在Windows执行；绘图工具使用Windows字体，本机Word用于更新域。

1. 复制原模板到私有参考文件，记录SHA256；保留原件，先渲染并检查所有页。
2. 准备私有`report-profile.json`，键为学院、专业班级、姓名、学号、指导教师、答辩日期。
3. `build_report.py`生成内容稿；`apply_school_template.py`将其内容迁入原模板组件。
4. Word在独立副本更新域；`import_word_toc.py`只迁回目录缓存、标题书签和新增目录样式。
5. 渲染最终全部页，核对目录、页码、图表、字体和占位符；将技术核查结果存入私有`report-qa.json`。
6. 复制报告到学校指定私有交付目录；`package_delivery.py`从已提交Git版本导出源码并扫描秘密及个人身份。后续修改报告或源码后重新核对、导出。

命令示例（`python`指文档环境解释器）：

```powershell
python scripts/build_report.py --profile artifacts/private/report-profile.json --output artifacts/private/content.docx
python scripts/apply_school_template.py --reference artifacts/private/reference.docx --content artifacts/private/content.docx --profile artifacts/private/report-profile.json --output artifacts/private/report.docx
./scripts/refresh_report_fields.ps1 -Source "$PWD/artifacts/private/report.docx" -Output "$PWD/artifacts/private/word-refreshed.docx"
python scripts/import_word_toc.py --source artifacts/private/report.docx --refreshed artifacts/private/word-refreshed.docx --output artifacts/private/report-final.docx
```

模板原样式节点与未编辑ZIP部件保留，新增图片、目录和正文属于计划中的填写内容。优先使用独立文档工具渲染；本机工具因缺少 soffice.exe 无法运行时，可用独立 Word 副本导出 PDF，再用 pypdfium2 渲染全部页。refresh_report_fields.ps1 的 PdfOutput 参数用于这一导出；脚本只关闭其独立创建的 Word 进程。LibreOffice 渲染时不经其保存。Word更新后的完整副本不直接作为交付件，以免无关部件被整体重写。

已核对版本共20页：封面、目录各1页，七章正文17页、参考文献1页；全部30个原生目录页码与Word书签位置一致。不同机器字体、打印机及Office版本可能影响分页，本人最终编辑后应在提交机器更新域并重新检查。

学校要求先答辩，教师确认报告和代码后再提交。技术核查不代替本人复核或教师确认。
