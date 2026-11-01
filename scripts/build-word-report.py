"""Build or extend the Albanian report without changing the reference template.

The source document is read only. Later installments extend the same report.
TOC/PAGE fields remain live; an isolated renderer can review them without a GUI.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Inches, Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
FONT = 'Palatino Linotype'
BLUE = '2E75B5'
TITLE = 'Monitorimi i burimeve dhe observabiliteti i aplikacioneve në kontejnerë'
HEADINGS = [
    ('I. Përshkrimi i problemit', '_CloudLab_Chapter1', 1, '3'),
    ('1.1. Problemi dhe motivimi', '_CloudLab_1_1', 2, '3'),
    ('1.2. Qëllimi dhe objektivat', '_CloudLab_1_2', 2, '3'),
    ('1.3. Kufijtë e implementimit', '_CloudLab_1_3', 2, '4'),
]
CHAPTER2_HEADINGS = [
    ('II. Teknologjitë e përdorura', '_CloudLab_Chapter2', 1, '5'),
    ('2.1. Teknologjitë dhe përgjegjësitë', '_CloudLab_2_1', 2, '5'),
    ('2.2. Konfigurimi i mjedisit punues', '_CloudLab_2_2', 2, '6'),
    ('2.3. Infrastruktura dhe arkitektura', '_CloudLab_2_3', 2, '7'),
    ('2.4. Docker Compose dhe vendosja', '_CloudLab_2_4', 2, '8'),
]
CHAPTER3_HEADINGS = [
    ('III. Implementimi / Zhvillimi', '_CloudLab_Chapter3', 1, '9'),
    ('3.1. Organizimi i kodit dhe koordinimi', '_CloudLab_3_1', 2, '9'),
    ('3.2. Ngarkesat Compute dhe Data', '_CloudLab_3_2', 2, '10'),
    ('3.3. MongoDB, historiku dhe ndërfaqja', '_CloudLab_3_3', 2, '11'),
    ('3.4. Monitorimi dhe Grafana', '_CloudLab_3_4', 2, '12'),
    ('3.5. Gjurmimi i shpërndarë', '_CloudLab_3_5', 2, '14'),
    ('3.6. Alokimi i burimeve dhe replikat', '_CloudLab_3_6', 2, '15'),
    ('3.7. Eksperimentet dhe analiza e rezultateve', '_CloudLab_3_7', 2, '17'),
    ('3.8. Testimi, sfidat dhe kufizimet', '_CloudLab_3_8', 2, '21'),
]
CHAPTER4_HEADINGS = [
    ('IV. Përfundime', '_CloudLab_Chapter4', 1, '22'),
    ('4.1. Arritjet kryesore', '_CloudLab_4_1', 2, '22'),
    ('4.2. Gjetjet dhe kufizimet', '_CloudLab_4_2', 2, '22'),
    ('4.3. Zhvillimi i ardhshëm', '_CloudLab_4_3', 2, '22'),
]
FINAL_HEADINGS = [('Abstrakti', '_CloudLab_Abstract', 1, '3')] + [
    (title, anchor, level, str(int(page) + 1))
    for title, anchor, level, page in HEADINGS + CHAPTER2_HEADINGS + CHAPTER3_HEADINGS + CHAPTER4_HEADINGS
] + [('V. Referencat', '_CloudLab_Chapter5', 1, '24')]
OLD_NETWORK_PARAGRAPH = ('Docker Compose bashkon shërbimet në rrjetin bridge të projektit. Brenda tij përdoren emrat e shërbimeve, si compute ose mongodb. '
    'Në pajisje publikohen vetëm Controller në portën 5000, Grafana në 3000 dhe Prometheus në 9090; të tria lidhen me 127.0.0.1. '
    'MongoDB dhe endpoint-et e punës mbeten pa porta të publikuara në host.')
NEW_NETWORK_PARAGRAPH = ('Docker Compose bashkon shërbimet në rrjetin bridge të projektit. Brenda tij përdoren emrat e shërbimeve, si compute ose mongodb. '
    'Në pajisje publikohen Controller në portën 5000, Grafana në 3000, Prometheus në 9090 dhe MongoDB në 27017 për inspektim lokal me Compass. '
    'Të katër portat lidhen me 127.0.0.1; endpoint-et e punës së Compute dhe Data nuk publikohen në host.')


def child(parent, name, **attributes):
    element = OxmlElement('w:' + name)
    for key, value in attributes.items():
        element.set(qn('w:' + key), str(value))
    parent.append(element)
    return element


def field(paragraph, instruction, cached=''):
    child(paragraph.add_run()._r, 'fldChar', fldCharType='begin')
    code = child(paragraph.add_run()._r, 'instrText')
    code.set(qn('xml:space'), 'preserve')
    code.text = ' ' + instruction + ' '
    child(paragraph.add_run()._r, 'fldChar', fldCharType='separate')
    if cached:
        paragraph.add_run(cached)
    child(paragraph.add_run()._r, 'fldChar', fldCharType='end')


def bookmark(paragraph, name, identifier):
    start = OxmlElement('w:bookmarkStart')
    start.set(qn('w:id'), str(identifier))
    start.set(qn('w:name'), name)
    paragraph._p.insert(0, start)
    child(paragraph._p, 'bookmarkEnd', id=identifier)


def border(paragraph, side):
    borders = child(paragraph._p.get_or_add_pPr(), 'pBdr')
    child(borders, side, val='single', sz=12, space=1, color='000000')


def style_font(style, size=11, bold=False, color='000000'):
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor.from_string(color)
    for key in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
        style.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:' + key), FONT)


def configure(doc, template):
    # The reference uses direct Palatino/blue formatting over generic styles.
    # Normalize that actual appearance into reusable semantic paragraph styles.
    with ZipFile(template) as archive:
        original_styles = parse_xml(archive.read('word/styles.xml'))
    styles_element = doc.styles.element
    for element in list(styles_element):
        styles_element.remove(element)
    for element in original_styles:
        styles_element.append(deepcopy(element))
    defaults = styles_element.find(qn('w:docDefaults'))
    default_run = defaults.find(qn('w:rPrDefault')).find(qn('w:rPr'))
    fonts = default_run.find(qn('w:rFonts'))
    for key in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
        fonts.set(qn('w:' + key), FONT)
    default_run.find(qn('w:lang')).set(qn('w:val'), 'sq-AL')

    normal = doc.styles['Normal']
    style_font(normal)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.line_spacing = 1
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.widow_control = True
    for name, size, indent in (('Heading 1', 16, 0), ('Heading 2', 14, .5)):
        style = doc.styles[name]
        style_font(style, size, True, BLUE)
        style.paragraph_format.left_indent = Inches(indent)
        style.paragraph_format.first_line_indent = Inches(0)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        style.paragraph_format.line_spacing = 1
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(10)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.keep_together = True
    doc.styles['Heading 1'].paragraph_format.tab_stops.add_tab_stop(Inches(.5))
    for name, indent in (('toc 1', 0), ('toc 2', .2)):
        style = doc.styles[name]
        style_font(style)
        style.paragraph_format.left_indent = Inches(indent)
        style.paragraph_format.line_spacing = 1
        style.paragraph_format.space_after = Pt(8)
        style.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    front = doc.styles.add_style('Cloud Front Title', WD_STYLE_TYPE.PARAGRAPH)
    front.base_style = normal
    style_font(front, 16, False, BLUE)
    front.paragraph_format.space_after = Pt(18)
    front.paragraph_format.keep_with_next = True
    bullet = doc.styles.add_style('Cloud Objective', WD_STYLE_TYPE.PARAGRAPH)
    bullet.base_style = normal
    style_font(bullet)
    bullet.paragraph_format.left_indent = Inches(.2)
    bullet.paragraph_format.first_line_indent = Inches(-.15)
    bullet.paragraph_format.line_spacing = 1
    bullet.paragraph_format.space_after = Pt(4)
    numbering = doc.part.numbering_part.element
    abstract_id = 1 + max(int(n.get(qn('w:abstractNumId'))) for n in numbering.findall(qn('w:abstractNum')))
    number_id = 1 + max(int(n.get(qn('w:numId'))) for n in numbering.findall(qn('w:num')))
    abstract = child(numbering, 'abstractNum', abstractNumId=abstract_id)
    child(abstract, 'multiLevelType', val='singleLevel')
    level = child(abstract, 'lvl', ilvl=0)
    child(level, 'start', val=1)
    child(level, 'numFmt', val='bullet')
    child(level, 'lvlText', val='•')
    number = child(numbering, 'num', numId=number_id)
    child(number, 'abstractNumId', val=abstract_id)
    properties = child(bullet.element.get_or_add_pPr(), 'numPr')
    child(properties, 'ilvl', val=0)
    child(properties, 'numId', val=number_id)

    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(1)
    section.left_margin = section.right_margin = Inches(1)
    section.header_distance = section.footer_distance = Inches(.5)
    section.different_first_page_header_footer = True
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    header.paragraph_format.space_after = Pt(0)
    header.add_run('Monitorimi i burimeve dhe observabiliteti')
    border(header, 'bottom')
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.paragraph_format.space_after = Pt(0)
    border(footer, 'top')
    footer.add_run('Faqe ')
    field(footer, 'PAGE', '2')
    # Keep the last checked TOC visible without Word's update-on-open dialog.
    # The TOC/PAGEREF fields remain live and can be updated after each chapter.
    child(doc.settings.element, 'updateFields', val='false')
    doc.core_properties.title = TITLE
    doc.core_properties.subject = 'Dokumentim teknik — drafti i Kapitullit I'
    doc.core_properties.author = 'Grupi [për plotësim]'
    doc.core_properties.last_modified_by = 'Grupi [për plotësim]'
    doc.core_properties.language = 'sq-AL'
    doc.core_properties.comments = 'Ballina, përmbajtja dhe Kapitulli I. Kapitujt vijues shtohen pas rishikimit.'
    doc.core_properties.created = doc.core_properties.modified = datetime(2026, 11, 1, tzinfo=timezone.utc)


def cover_paragraph(doc, text='', size=11, bold=False, align=WD_ALIGN_PARAGRAPH.CENTER,
                    before=0, after=0, color='000000'):
    paragraph = doc.add_paragraph()
    paragraph.alignment = align
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = 1.15
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    return paragraph


def cover(doc):
    cover_paragraph(doc, 'Universiteti i Prishtinës “Hasan Prishtina”', 20, True, after=12)
    cover_paragraph(doc, 'Fakulteti i Inxhinierisë Elektrike dhe Kompjuterike', 18, True, after=30)
    logo = doc.add_table(rows=1, cols=1)
    logo.alignment = WD_TABLE_ALIGNMENT.CENTER
    logo.autofit = False
    logo.columns[0].width = Inches(1.8)
    logo.rows[0].height = Inches(1.6)
    cell = logo.cell(0, 0)
    cell.width = Inches(1.8)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    props = cell._tc.get_or_add_tcPr()
    borders = child(props, 'tcBorders')
    for side in ('top', 'left', 'bottom', 'right'):
        child(borders, side, val='single', sz=4, color='C9CDD3')
    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cell.paragraphs[0].paragraph_format.space_after = Pt(0)
    run = cell.paragraphs[0].add_run('[VEND PËR LOGON]\nLogoja e universitetit')
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor.from_string('666666')
    cover_paragraph(doc, 'Dokumentim teknik i projektit', 16, True, before=28, after=30)
    cover_paragraph(doc, 'Lënda: [PLOTËSONI EMRIN E LËNDËS]', 12, True,
                    align=WD_ALIGN_PARAGRAPH.LEFT, after=12)
    cover_paragraph(doc, 'Titulli i projektit: ' + TITLE, 14, True,
                    align=WD_ALIGN_PARAGRAPH.LEFT, after=12)
    cover_paragraph(doc, 'Grupi: [PLOTËSONI]', 12, align=WD_ALIGN_PARAGRAPH.LEFT, after=32)
    table = doc.add_table(rows=2, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for column, width in zip(table.columns, (2.15, 2.2, 2.15)):
        column.width = Inches(width)
    headers = ('Profesori / asistenti', 'Emri dhe mbiemri i studentëve', 'Email adresa')
    values = ('[PLOTËSONI]', '[PLOTËSONI ANËTARËT]', '[PLOTËSONI EMAIL-ET]')
    for index, row in enumerate(table.rows):
        for cell, text in zip(row.cells, headers if index == 0 else values):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            properties = cell._tc.get_or_add_tcPr()
            if index == 1:
                child(properties, 'shd', fill='EEEEEE', val='clear')
            margins = child(properties, 'tcMar')
            for side in ('top', 'bottom', 'left', 'right'):
                child(margins, side, w=100, type='dxa')
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(text)
            run.bold = index == 0
            run.font.size = Pt(10)
    cover_paragraph(doc, 'Prishtinë, 2026', before=28)


def contents(doc):
    doc.add_page_break()
    doc.add_paragraph('Përmbajtja', 'Cloud Front Title')
    # A real TOC field with bookmarked cached entries, not a manually typed list.
    sdt = child(doc.element.body, 'sdt')
    doc.element.body.remove(sdt)
    doc.element.body.insert(len(doc.element.body) - 1, sdt)
    properties = child(sdt, 'sdtPr')
    child(properties, 'alias', val='Përmbajtja automatike')
    gallery = child(properties, 'docPartObj')
    child(gallery, 'docPartGallery', val='Table of Contents')
    child(gallery, 'docPartUnique')
    child(sdt, 'sdtEndPr')
    populate_contents(doc, sdt, HEADINGS)


def populate_contents(doc, sdt, headings):
    content = sdt.find(qn('w:sdtContent'))
    if content is None:
        content = child(sdt, 'sdtContent')
    for old in list(content):
        content.remove(old)
    for index, (text, anchor, level, page) in enumerate(headings):
        paragraph = doc.add_paragraph(style='toc ' + str(level))
        content.append(paragraph._p)
        if index == 0:
            child(paragraph.add_run()._r, 'fldChar', fldCharType='begin')
            instruction = child(paragraph.add_run()._r, 'instrText')
            instruction.set(qn('xml:space'), 'preserve')
            instruction.text = ' TOC \\o "1-2" \\h \\z \\u '
            child(paragraph.add_run()._r, 'fldChar', fldCharType='separate')
        hyperlink = child(paragraph._p, 'hyperlink', anchor=anchor)
        run = child(hyperlink, 'r')
        child(run, 't').text = text
        child(run, 'tab')
        field(paragraph, 'PAGEREF ' + anchor + ' \\h', page)
    paragraph = doc.add_paragraph()
    content.append(paragraph._p)
    child(paragraph.add_run()._r, 'fldChar', fldCharType='end')


def chapter2_styles(doc):
    for name, color, size in (
        ('Cloud Table Caption', '000000', 11),
        ('Cloud Figure Caption', '1F497D', 11),
        ('Cloud Command', '000000', 9.5),
    ):
        style = doc.styles[name] if name in doc.styles else doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = doc.styles['Normal']
        style_font(style, size, False, color)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER if 'Caption' in name else WD_ALIGN_PARAGRAPH.LEFT
        style.paragraph_format.space_before = Pt(4)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = name != 'Cloud Figure Caption'
    doc.styles['Cloud Command'].font.name = 'Consolas'


def caption(doc, label, number, title):
    paragraph = doc.add_paragraph(style='Cloud Table Caption' if label == 'Tabela' else 'Cloud Figure Caption')
    paragraph.add_run(label + ' ')
    field(paragraph, 'SEQ ' + label + ' \\* ARABIC', str(number))
    paragraph.add_run(': ' + title)
    return paragraph


def data_table(doc, lines, widths):
    rows = [[cell.strip() for cell in line.strip().strip('|').split('|')] for line in lines]
    rows = [rows[0], *rows[2:]]  # The Markdown separator is not document content.
    table = doc.add_table(rows=0, cols=len(widths))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for column, width in zip(table.columns, widths):
        column.width = Inches(width)
    props = table._tbl.tblPr
    borders = child(props, 'tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        child(borders, side, val='single', sz=4, color='C9CDD3')
    for index, values in enumerate(rows):
        row = table.add_row()
        child(row._tr.get_or_add_trPr(), 'cantSplit')
        if index == 0:
            child(row._tr.get_or_add_trPr(), 'tblHeader')
        assert len(values) == len(widths)
        for cell, text, width in zip(row.cells, values, widths):
            cell.width = Inches(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell_props = cell._tc.get_or_add_tcPr()
            margins = child(cell_props, 'tcMar')
            for side, value in (('top', 75), ('bottom', 75), ('left', 100), ('right', 100)):
                child(margins, side, w=value, type='dxa')
            if index == 0:
                child(cell_props, 'shd', fill='F3F4F6', val='clear')
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.keep_with_next = index == 0
            run = paragraph.add_run(text)
            run.font.name = 'Arial'
            run.font.size = Pt(10 if index == 0 else 9.5)
            run.bold = index == 0
    after = doc.add_paragraph()
    after.paragraph_format.space_after = Pt(0)
    after.paragraph_format.line_spacing = Pt(4)
    after.add_run().font.size = Pt(4)


def figure_placeholder(doc, number, title, source, note, height_cm):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(6.5)
    table.rows[0].height = Cm(height_cm)
    table.rows[0].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    child(table.rows[0]._tr.get_or_add_trPr(), 'cantSplit')
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    props = cell._tc.get_or_add_tcPr()
    child(props, 'shd', fill='FAFAFA', val='clear')
    borders = child(props, 'tcBorders')
    for side in ('top', 'left', 'bottom', 'right'):
        child(borders, side, val='single', sz=4, color='C9CDD3')
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.keep_with_next = True
    run = paragraph.add_run(f'[VEND PËR FIGURËN {number}]')
    run.bold = True
    run.font.size = Pt(10)
    for text, font_size in (('Burimi: ' + source, 8.5), (note, 9)):
        paragraph = cell.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(4)
        paragraph.paragraph_format.keep_with_next = True
        run = paragraph.add_run(text)
        run.font.size = Pt(font_size)
        run.font.color.rgb = RGBColor.from_string('555555')
        if text.startswith('Burimi: docs/'):
            run.font.name = 'Consolas'
    caption(doc, 'Figura', number, title)


def append_chapter2(doc):
    if any(p.style.name == 'Heading 1' and p.text.startswith('II.') for p in doc.paragraphs):
        raise ValueError('Chapter II is already present. Preserve edits instead of appending it twice.')
    chapter2_styles(doc)
    source = (ROOT / 'docs/raporti/kapitulli-2.md').read_text(encoding='utf-8')
    heading_index = 0
    widths = None
    for block in source.strip().split('\n\n'):
        if block.startswith('# '):
            paragraph = doc.add_paragraph(block[2:].replace('II. ', 'II.\t', 1), 'Heading 1')
            paragraph.paragraph_format.page_break_before = True
            paragraph.paragraph_format.space_before = Pt(0)
        elif block.startswith('## '):
            text = block[3:]
            paragraph = doc.add_paragraph(text, 'Heading 2')
            if not text.startswith('2.1.'):
                paragraph.paragraph_format.page_break_before = True
                paragraph.paragraph_format.space_before = Pt(0)
        elif block.startswith('[[TABLE|'):
            _, number, title, sizes = block[2:-2].split('|')
            caption(doc, 'Tabela', int(number), title)
            widths = [float(value) for value in sizes.split(',')]
            continue
        elif block.startswith('|'):
            data_table(doc, block.splitlines(), widths)
            continue
        elif block.startswith('[[FIGURE|'):
            _, number, title, source_path, note, height = block[2:-2].split('|')
            figure_placeholder(doc, int(number), title, source_path, note, float(height))
            continue
        elif block.startswith('[[COMMAND|'):
            doc.add_paragraph(block[10:-2], 'Cloud Command')
            continue
        else:
            doc.add_paragraph(block.replace('\n', ' '))
            continue
        bookmark(paragraph, CHAPTER2_HEADINGS[heading_index][1], 5 + heading_index)
        heading_index += 1
    assert heading_index == len(CHAPTER2_HEADINGS)
    toc = doc.element.body.find(qn('w:sdt'))
    if toc is None:
        raise ValueError('The existing automatic table of contents is missing.')
    populate_contents(doc, toc, HEADINGS + CHAPTER2_HEADINGS)
    doc.core_properties.subject = 'Dokumentim teknik — Kapitujt I–II'
    doc.core_properties.comments = 'Ballina, përmbajtja dhe Kapitujt I–II. Kapitulli III shtohet pas rishikimit.'


def append_chapter3(doc):
    titles = [p.text for p in doc.paragraphs if p.style.name == 'Heading 1']
    if not any(title.startswith('II.') for title in titles):
        raise ValueError('Chapter III requires a base containing Chapters I–II.')
    if any(title.startswith('III.') for title in titles):
        raise ValueError('Chapter III is already present; do not append it twice.')
    # The user added local Compass access after Chapter II was written.
    # Correct only this documented fact; preserve all other base content.
    for paragraph in doc.paragraphs:
        if paragraph.text == OLD_NETWORK_PARAGRAPH:
            paragraph.text = NEW_NETWORK_PARAGRAPH
            break
        if paragraph.text == NEW_NETWORK_PARAGRAPH:
            break
    else:
        raise ValueError('The network paragraph has manual edits; preserve and reconcile them before updating it.')
    chapter2_styles(doc)
    for name, size, color in (('Cloud Detail Heading', 12, BLUE), ('Cloud Note', 9.5, '555555')):
        style = doc.styles[name] if name in doc.styles else doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = doc.styles['Normal']
        style_font(style, size, name == 'Cloud Detail Heading', color)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        style.paragraph_format.space_before = Pt(8 if name == 'Cloud Detail Heading' else 0)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True
    source = (ROOT / 'docs/raporti/kapitulli-3.md').read_text(encoding='utf-8')
    heading_index = 0
    widths = None
    new_page = False
    for block in source.strip().split('\n\n'):
        if block == '[[PAGE]]':
            new_page = True
            continue
        if block.startswith('### '):
            paragraph = doc.add_paragraph(block[4:], 'Cloud Detail Heading')
            paragraph.paragraph_format.page_break_before = new_page
            if new_page:
                paragraph.paragraph_format.space_before = Pt(0)
            new_page = False
            continue
        if block.startswith('# '):
            paragraph = doc.add_paragraph(block[2:].replace('III. ', 'III.\t', 1), 'Heading 1')
            paragraph.paragraph_format.page_break_before = True
            paragraph.paragraph_format.space_before = Pt(0)
        elif block.startswith('## '):
            text = block[3:]
            paragraph = doc.add_paragraph(text, 'Heading 2')
            if not text.startswith('3.1.'):
                paragraph.paragraph_format.page_break_before = True
                paragraph.paragraph_format.space_before = Pt(0)
        elif block.startswith('[[TABLE|'):
            _, number, title, sizes = block[2:-2].split('|')
            caption(doc, 'Tabela', int(number), title)
            widths = [float(value) for value in sizes.split(',')]
            continue
        elif block.startswith('|'):
            data_table(doc, block.splitlines(), widths)
            continue
        elif block.startswith('[[FIGURE|'):
            _, number, title, source_path, note, height = block[2:-2].split('|')
            figure_placeholder(doc, int(number), title, source_path, note, float(height))
            continue
        elif block.startswith('[[NOTE|'):
            doc.add_paragraph(block[7:-2], 'Cloud Note')
            continue
        else:
            doc.add_paragraph(block.replace('\n', ' '))
            continue
        bookmark(paragraph, CHAPTER3_HEADINGS[heading_index][1], 10 + heading_index)
        heading_index += 1
    assert heading_index == len(CHAPTER3_HEADINGS)
    populate_contents(doc, doc.element.body.find(qn('w:sdt')), HEADINGS + CHAPTER2_HEADINGS + CHAPTER3_HEADINGS)
    doc.core_properties.subject = 'Dokumentim teknik — Kapitujt I–III'
    doc.core_properties.comments = 'Ballina, përmbajtja dhe Kapitujt I–III; figurat janë vende për plotësim. Kapitujt IV–V dhe abstrakti shtohen pas rishikimit.'


def append_chapter4(doc):
    titles = [p.text for p in doc.paragraphs if p.style.name == 'Heading 1']
    if not all(any(title.startswith(prefix) for title in titles) for prefix in ('I.', 'II.', 'III.')):
        raise ValueError('Chapter IV requires a base containing Chapters I–III.')
    if any(title.startswith('IV.') or title.startswith('V.') for title in titles):
        raise ValueError('Chapter IV or a later chapter is already present; do not append it twice.')
    toc = doc.element.body.find(qn('w:sdt'))
    if toc is None:
        raise ValueError('The existing automatic table of contents is missing.')
    source = (ROOT / 'docs/raporti/kapitulli-4.md').read_text(encoding='utf-8')
    heading_index = 0
    for block in source.strip().split('\n\n'):
        if block.startswith('# '):
            paragraph = doc.add_paragraph(block[2:].replace('IV. ', 'IV.\t', 1), 'Heading 1')
            paragraph.paragraph_format.page_break_before = True
            paragraph.paragraph_format.space_before = Pt(0)
        elif block.startswith('## '):
            paragraph = doc.add_paragraph(block[3:], 'Heading 2')
        else:
            doc.add_paragraph(block.replace('\n', ' '))
            continue
        bookmark(paragraph, CHAPTER4_HEADINGS[heading_index][1], 19 + heading_index)
        heading_index += 1
    assert heading_index == len(CHAPTER4_HEADINGS)
    populate_contents(doc, toc, HEADINGS + CHAPTER2_HEADINGS + CHAPTER3_HEADINGS + CHAPTER4_HEADINGS)
    doc.core_properties.subject = 'Dokumentim teknik — Kapitujt I–IV'
    doc.core_properties.comments = 'Ballina, përmbajtja dhe Kapitujt I–IV; figurat janë vende për plotësim. Kapitulli V dhe abstrakti shtohen pas rishikimit.'


def citation(paragraph, references):
    """Link each printed citation number to its bibliography bookmark."""
    paragraph.add_run('\u00a0[')
    for index, number in enumerate(references):
        if index:
            paragraph.add_run(',\u00a0')
        link = child(paragraph._p, 'hyperlink', anchor=f'_CloudLab_Ref{number}', history='1')
        run = child(link, 'r')
        props = child(run, 'rPr')
        child(props, 'color', val=BLUE)
        child(run, 't').text = str(number)
    paragraph.add_run(']')


def external_link(paragraph, url):
    link = child(paragraph._p, 'hyperlink', history='1')
    link.set(qn('r:id'), paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True))
    run = child(link, 'r')
    props = child(run, 'rPr')
    child(props, 'color', val=BLUE)
    child(props, 'u', val='single')
    child(run, 't').text = url


def finish_report(doc):
    """Add the abstract, numbered references and citations to the checked I–IV base."""
    titles = [p.text for p in doc.paragraphs if p.style.name == 'Heading 1']
    if not all(any(title.startswith(prefix) for title in titles) for prefix in ('I.', 'II.', 'III.', 'IV.')):
        raise ValueError('Finishing requires a base containing Chapters I–IV.')
    if any(title.startswith('V.') or title == 'Abstrakti' for title in titles):
        raise ValueError('The abstract or references are already present; do not finish the report twice.')
    toc = doc.element.body.find(qn('w:sdt'))
    if toc is None:
        raise ValueError('The existing automatic table of contents is missing.')
    references = json.loads((ROOT / 'docs/raporti/referencat.json').read_text(encoding='utf-8'))
    numbers = {entry['id'] for entry in references['entries']}
    mappings = json.loads((ROOT / 'docs/raporti/citimet.json').read_text(encoding='utf-8'))
    for mapping in mappings:
        matches = [p for p in doc.paragraphs if p.text.startswith(mapping['prefix'])]
        if len(matches) != 1:
            raise ValueError(f"Citation paragraph needs reconciliation: {mapping['prefix']}")
        if not set(mapping['references']).issubset(numbers):
            raise ValueError('A citation has no corresponding reference.')
        citation(matches[0], mapping['references'])

    first_chapter = next(p for p in doc.paragraphs if p.style.name == 'Heading 1' and p.text.startswith('I.'))
    source = (ROOT / 'docs/raporti/abstrakti.md').read_text(encoding='utf-8')
    for block in source.strip().split('\n\n'):
        if block.startswith('# '):
            paragraph = first_chapter.insert_paragraph_before(block[2:], 'Heading 1')
            paragraph.paragraph_format.page_break_before = True
            paragraph.paragraph_format.space_before = Pt(0)
            bookmark(paragraph, '_CloudLab_Abstract', 23)
        elif block.startswith('Fjalë kyçe:'):
            paragraph = first_chapter.insert_paragraph_before()
            paragraph.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.add_run('Fjalë kyçe:').bold = True
            paragraph.add_run(block.removeprefix('Fjalë kyçe:'))
        else:
            first_chapter.insert_paragraph_before(block.replace('\n', ' '))

    paragraph = doc.add_paragraph('V.\tReferencat', 'Heading 1')
    paragraph.paragraph_format.page_break_before = True
    paragraph.paragraph_format.space_before = Pt(0)
    bookmark(paragraph, '_CloudLab_Chapter5', 24)
    doc.add_paragraph('Burimet elektronike janë konsultuar më 1 nëntor 2026. Kodi dhe konfigurimet e projektit citohen në [1]; evidenca e rezultateve dhe e verifikimeve në [15].')
    for entry in references['entries']:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.left_indent = Inches(.3)
        paragraph.paragraph_format.first_line_indent = Inches(-.3)
        paragraph.paragraph_format.space_after = Pt(10)
        paragraph.paragraph_format.keep_together = True
        paragraph.paragraph_format.page_break_before = entry['id'] == 9
        paragraph.add_run(f"[{entry['id']}] {entry['author'].rstrip('.')}. ").bold = True
        paragraph.add_run(f"{entry['title']}. {entry['description']} ")
        external_link(paragraph, entry['url'])
        bookmark(paragraph, f"_CloudLab_Ref{entry['id']}", 24 + entry['id'])
    populate_contents(doc, toc, FINAL_HEADINGS)
    doc.core_properties.subject = 'Dokumentim teknik — abstrakti dhe Kapitujt I–V'
    doc.core_properties.comments = 'Teksti i raportit është plotësuar; ballina dhe 16 vendet për figura mbeten të redaktueshme për plotësim nga grupi.'


def body(doc):
    source = (ROOT / 'docs/raporti/kapitulli-1.md').read_text(encoding='utf-8')
    heading_index = 0
    for block in source.strip().split('\n\n'):
        if block.startswith('# '):
            paragraph = doc.add_paragraph(block[2:].replace('I. ', 'I.\t', 1), 'Heading 1')
            paragraph.paragraph_format.page_break_before = True
            paragraph.paragraph_format.space_before = Pt(0)
        elif block.startswith('## '):
            paragraph = doc.add_paragraph(block[3:], 'Heading 2')
        elif block.startswith('- '):
            for line in block.splitlines():
                doc.add_paragraph(line.removeprefix('- '), 'Cloud Objective')
            continue
        else:
            doc.add_paragraph(block.replace('\n', ' '))
            continue
        bookmark(paragraph, HEADINGS[heading_index][1], heading_index + 1)
        heading_index += 1
    assert heading_index == len(HEADINGS)
    return len(re.findall(r'\S+', source))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path)
    parser.add_argument('--base', type=Path, help='Append the selected chapter to a checked draft; the base is never modified.')
    parser.add_argument('--chapter', type=int, choices=(2, 3, 4), default=2, help='Chapter to append with --base (default: 2).')
    parser.add_argument('--finish', action='store_true', help='Add abstract, references and in-text citations to a checked I–IV base.')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/Raporti_Projektit_Monitorimi_i_Burimeve.docx')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    if bool(args.template) == bool(args.base):
        parser.error('Choose --template for the initial draft or --base to append a chapter, not both.')
    if args.template and args.chapter != 2:
        parser.error('--chapter is used only with --base.')
    if args.finish and (not args.base or args.chapter != 2):
        parser.error('--finish requires --base and cannot be combined with --chapter.')
    if args.output.exists() and not args.overwrite:
        parser.error('Output exists. Use --overwrite only when regenerating intentionally; preserve any manual Word edits first.')
    original = args.base or args.template
    if original.resolve() == args.output.resolve():
        parser.error('The input and output must differ; preserve the checked original.')
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    if args.base:
        document = Document(args.base)
        if args.finish:
            finish_report(document)
        else:
            {2: append_chapter2, 3: append_chapter3, 4: append_chapter4}[args.chapter](document)
    else:
        document = Document()
        configure(document, args.template)
        cover(document)
        contents(document)
        body(document)
    document.save(args.output)
    assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
    with ZipFile(args.output) as archive:
        assert not any(name.startswith('word/media/') for name in archive.namelist())
    print(f'Created {args.output}. Input unchanged; no embedded images.')


if __name__ == '__main__':
    main()
