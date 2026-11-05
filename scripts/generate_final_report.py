"""
Academic Report Generator for Veritas Multimodal Intelligence.
Generates a comprehensive, submission-ready Final Year Project Report
in Microsoft Word (.docx) format and Markdown (.md) format.
"""

import os
import sys
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

DOCS_DIR = os.path.join(os.path.abspath("."), "docs")
os.makedirs(DOCS_DIR, exist_ok=True)
DOCX_PATH = os.path.join(DOCS_DIR, "VERITAS_Final_Year_Project_Report.docx")
MD_PATH = os.path.join(DOCS_DIR, "FINAL_YEAR_PROJECT_REPORT.md")


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets internal padding for table cells."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def set_cell_shading(cell, color_hex="F1F5F9"):
    """Sets background shading color for a table cell."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def format_table_header(row, col_widths=None):
    """Styles the header row of an academic table."""
    for idx, cell in enumerate(row.cells):
        set_cell_shading(cell, "1E293B")
        set_cell_margins(cell, top=140, bottom=140, left=160, right=160)
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.bold = True
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.name = "Times New Roman"
        if col_widths and idx < len(col_widths):
            cell.width = col_widths[idx]


def format_table_data(table, col_widths=None):
    """Styles data rows in an academic table."""
    for r_idx, row in enumerate(table.rows[1:]):
        bg = "FFFFFF" if r_idx % 2 == 0 else "F8FAFC"
        for c_idx, cell in enumerate(row.cells):
            set_cell_shading(cell, bg)
            set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9.5)
                    run.font.name = "Times New Roman"
            if col_widths and c_idx < len(col_widths):
                cell.width = col_widths[c_idx]


def add_callout_box(doc, title, body_text):
    """Inserts a styled note/callout box into the document."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_shading(cell, "F0F9FF")
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)
    
    # Left accent border
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>\n'
        f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="0284C7"/>\n'
        f'  <w:top w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f'  <w:bottom w:val="none"/>\n'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    run_t = p.add_run(f"KEY HIGHLIGHT: {title}\n")
    run_t.font.bold = True
    run_t.font.size = Pt(10)
    run_t.font.color.rgb = RGBColor(2, 132, 199)
    run_t.font.name = "Times New Roman"
    
    run_b = p.add_run(body_text)
    run_b.font.size = Pt(9.5)
    run_b.font.italic = True
    run_b.font.color.rgb = RGBColor(51, 65, 85)
    run_b.font.name = "Times New Roman"
    doc.add_paragraph()  # spacer


def add_ascii_diagram(doc, title, ascii_art):
    """Inserts a formatted monospace diagram box."""
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(8)
    p_title.paragraph_format.space_after = Pt(2)
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run(f"Figure: {title}")
    run_title.font.bold = True
    run_title.font.size = Pt(10)
    run_title.font.color.rgb = RGBColor(30, 41, 59)
    run_title.font.name = "Times New Roman"

    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_shading(cell, "0F172A")
    set_cell_margins(cell, top=120, bottom=120, left=160, right=160)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(ascii_art.strip())
    run.font.name = "Courier New"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(56, 189, 248)
    doc.add_paragraph()


print("[*] Academic Report Generator initialized.")

