from __future__ import annotations

import argparse
import html
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


DOCS: dict[str, list[tuple[str, str]]] = {
    "ru": [
        ("README.md", "Оглавление"),
        ("01-product-overview.md", "Назначение и пользовательские роли"),
        ("02-installation-and-launch.md", "Установка, предварительные требования и запуск"),
        ("03-system-architecture.md", "Архитектура системы"),
        ("04-data-hub.md", "Data Hub"),
        ("05-strategy-lab.md", "Strategy Lab"),
        ("06-ga-lab.md", "GA Lab"),
        ("07-model-development-guide.md", "Руководство модельера и разработчика компонентов"),
        ("08-testing-methodology.md", "Методики тестирования и сравнения моделей"),
        ("09-api-reference.md", "API и интеграции"),
        ("10-operations-and-delivery.md", "Эксплуатация, конфигурация и передача системы"),
        ("11-scientific-basis.md", "Научная база и публикации автора"),
        ("12-glossary.md", "Глоссарий"),
    ],
    "en": [
        ("README.md", "Contents"),
        ("01-product-overview.md", "Purpose and User Roles"),
        ("02-installation-and-launch.md", "Installation, Prerequisites, and Launch"),
        ("03-system-architecture.md", "System Architecture"),
        ("04-data-hub.md", "Data Hub"),
        ("05-strategy-lab.md", "Strategy Lab"),
        ("06-ga-lab.md", "GA Lab"),
        ("07-model-development-guide.md", "Modeler and Component Developer Guide"),
        ("08-testing-methodology.md", "Testing and Model Comparison Methodology"),
        ("09-api-reference.md", "API and Integrations"),
        ("10-operations-and-delivery.md", "Operations, Configuration, and Delivery"),
        ("11-scientific-basis.md", "Scientific Basis and Author Publications"),
        ("12-glossary.md", "Glossary"),
    ],
}


@dataclass(frozen=True)
class PdfContext:
    root: Path
    language: str
    output: Path
    title: str
    subtitle: str
    font_regular: str
    font_bold: str
    font_mono: str

    @property
    def source_dir(self) -> Path:
        return self.root if self.language == "ru" else self.root / "en"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ITS documentation PDFs.")
    parser.add_argument("--docs-dir", default="docs", type=Path)
    parser.add_argument("--language", choices=["ru", "en", "all"], default="all")
    args = parser.parse_args()

    docs_dir = args.docs_dir.resolve()
    output_dir = docs_dir / "pdf"
    output_dir.mkdir(parents=True, exist_ok=True)

    fonts = register_fonts()
    languages = ("ru", "en") if args.language == "all" else (args.language,)
    for language in languages:
        title = "Документация ITS" if language == "ru" else "ITS Documentation"
        subtitle = (
            "Интеллектуальная система формирования торговых стратегий"
            if language == "ru"
            else "Intelligent Trading Strategies system"
        )
        output = output_dir / f"its_documentation_{language}.pdf"
        context = PdfContext(
            root=docs_dir,
            language=language,
            output=output,
            title=title,
            subtitle=subtitle,
            font_regular=fonts["regular"],
            font_bold=fonts["bold"],
            font_mono=fonts["mono"],
        )
        build_pdf(context)
        print(f"Built {output}")


def register_fonts() -> dict[str, str]:
    regular_path = first_existing(
        [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )
    bold_path = first_existing(
        [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    )
    mono_path = first_existing(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )

    if not regular_path:
        raise RuntimeError(
            "No Unicode TrueType font was found. Install Arial, DejaVu Sans, or Liberation Sans "
            "before generating the documentation PDF."
        )

    pdfmetrics.registerFont(TTFont("ITSDocRegular", regular_path))
    pdfmetrics.registerFont(TTFont("ITSDocBold", bold_path or regular_path))
    pdfmetrics.registerFont(TTFont("ITSDocMono", mono_path or regular_path))
    pdfmetrics.registerFontFamily(
        "ITSDoc",
        normal="ITSDocRegular",
        bold="ITSDocBold",
        italic="ITSDocRegular",
        boldItalic="ITSDocBold",
    )
    return {"regular": "ITSDocRegular", "bold": "ITSDocBold", "mono": "ITSDocMono"}


def first_existing(paths: Iterable[str]) -> str | None:
    for path in paths:
        if Path(path).exists():
            return path
    return None


def build_pdf(context: PdfContext) -> None:
    styles = build_styles(context)
    doc = SimpleDocTemplate(
        str(context.output),
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=context.title,
        author="ITS",
    )

    story = build_cover(context, styles)
    story.extend(build_toc(context, styles))

    for index, (filename, section_title) in enumerate(DOCS[context.language], start=1):
        source = context.source_dir / filename
        if not source.exists():
            raise FileNotFoundError(source)
        story.append(PageBreak())
        story.append(Paragraph(f"{index}. {escape_xml(section_title)}", styles["SectionLabel"]))
        markdown = source.read_text(encoding="utf-8")
        story.extend(markdown_to_flowables(markdown, source.parent, styles, doc.width, context))

    doc.build(
        story,
        onFirstPage=lambda canvas, document: draw_footer(canvas, document, context),
        onLaterPages=lambda canvas, document: draw_footer(canvas, document, context),
    )


def build_styles(context: PdfContext) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}
    styles["Title"] = ParagraphStyle(
        "ITSTitle",
        parent=sample["Title"],
        fontName=context.font_bold,
        fontSize=28,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8 * mm,
    )
    styles["Subtitle"] = ParagraphStyle(
        "ITSSubtitle",
        parent=sample["BodyText"],
        fontName=context.font_regular,
        fontSize=13,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10 * mm,
    )
    styles["Body"] = ParagraphStyle(
        "ITSBody",
        parent=sample["BodyText"],
        fontName=context.font_regular,
        fontSize=9.6,
        leading=14,
        textColor=colors.HexColor("#17202f"),
        spaceAfter=5,
    )
    styles["Small"] = ParagraphStyle(
        "ITSSmall",
        parent=styles["Body"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    )
    styles["H1"] = ParagraphStyle(
        "ITSH1",
        parent=styles["Body"],
        fontName=context.font_bold,
        fontSize=19,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=10,
    )
    styles["H2"] = ParagraphStyle(
        "ITSH2",
        parent=styles["Body"],
        fontName=context.font_bold,
        fontSize=14.5,
        leading=19,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=7,
    )
    styles["H3"] = ParagraphStyle(
        "ITSH3",
        parent=styles["Body"],
        fontName=context.font_bold,
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=5,
    )
    styles["Code"] = ParagraphStyle(
        "ITSCode",
        parent=sample["Code"],
        fontName=context.font_mono,
        fontSize=7.4,
        leading=9.5,
        textColor=colors.HexColor("#e5edf8"),
        backColor=colors.HexColor("#0f172a"),
        borderPadding=7,
        leftIndent=0,
        spaceAfter=8,
    )
    styles["Bullet"] = ParagraphStyle(
        "ITSBullet",
        parent=styles["Body"],
        leftIndent=11,
        firstLineIndent=0,
    )
    styles["SectionLabel"] = ParagraphStyle(
        "ITSSectionLabel",
        parent=styles["Small"],
        fontName=context.font_bold,
        textColor=colors.HexColor("#2563eb"),
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    return styles


def build_cover(context: PdfContext, styles: dict[str, ParagraphStyle]) -> list:
    generated = (
        f"Дата формирования: {date.today().isoformat()}"
        if context.language == "ru"
        else f"Generated: {date.today().isoformat()}"
    )
    return [
        Spacer(1, 58 * mm),
        Paragraph(escape_xml(context.title), styles["Title"]),
        Paragraph(escape_xml(context.subtitle), styles["Subtitle"]),
        Spacer(1, 8 * mm),
        Paragraph(escape_xml(generated), styles["Small"]),
        PageBreak(),
    ]


def build_toc(context: PdfContext, styles: dict[str, ParagraphStyle]) -> list:
    title = "Содержание" if context.language == "ru" else "Contents"
    rows = []
    for index, (_, section_title) in enumerate(DOCS[context.language], start=1):
        rows.append(
            [
                Paragraph(str(index), styles["Small"]),
                Paragraph(escape_xml(section_title), styles["Body"]),
            ]
        )
    table = Table(rows, colWidths=[14 * mm, 145 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [Paragraph(title, styles["H1"]), table]


def markdown_to_flowables(
    markdown: str,
    base_dir: Path,
    styles: dict[str, ParagraphStyle],
    max_width: float,
    context: PdfContext,
) -> list:
    lines = markdown.replace("\r\n", "\n").split("\n")
    flowables = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or should_skip_line(stripped):
            i += 1
            continue

        fence = re.match(r"^```([A-Za-z0-9_-]*)?\s*$", stripped)
        if fence:
            code_lines = []
            i += 1
            while i < len(lines) and not re.match(r"^```\s*$", lines[i].strip()):
                code_lines.append(lines[i])
                i += 1
            i += 1
            flowables.append(Preformatted("\n".join(code_lines), styles["Code"], maxLineLength=120))
            continue

        if is_table_start(lines, i):
            table_lines = [lines[i], lines[i + 1]]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                table_lines.append(lines[i])
                i += 1
            flowables.append(render_table(table_lines, styles, max_width, context))
            continue

        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if image_match:
            image = render_image(base_dir, image_match.group(2), max_width)
            if image:
                flowables.append(image)
                flowables.append(Spacer(1, 4 * mm))
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = inline_markup(heading.group(2), context)
            style = styles["H1"] if level == 1 else styles["H2"] if level == 2 else styles["H3"]
            flowables.append(Paragraph(text, style))
            i += 1
            continue

        if re.match(r"^\s*[-*+]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                item_text = re.sub(r"^\s*[-*+]\s+", "", lines[i]).strip()
                items.append(ListItem(Paragraph(inline_markup(item_text, context), styles["Bullet"])))
                i += 1
            flowables.append(ListFlowable(items, bulletType="bullet", leftIndent=12, bulletFontName=context.font_regular))
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                item_text = re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip()
                items.append(ListItem(Paragraph(inline_markup(item_text, context), styles["Bullet"])))
                i += 1
            flowables.append(ListFlowable(items, bulletType="1", leftIndent=14, bulletFontName=context.font_regular))
            continue

        paragraph_lines = []
        while i < len(lines) and lines[i].strip() and not is_block_start(lines, i):
            if not should_skip_line(lines[i].strip()):
                paragraph_lines.append(lines[i].strip())
            i += 1
        if paragraph_lines:
            flowables.append(Paragraph(inline_markup(" ".join(paragraph_lines), context), styles["Body"]))

    return flowables


def should_skip_line(stripped: str) -> bool:
    return stripped in {"[К оглавлению](README.md)", "[Back to Contents](README.md)"}


def is_block_start(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    return (
        stripped.startswith("```")
        or bool(re.match(r"^(#{1,6})\s+", stripped))
        or bool(re.match(r"^\s*[-*+]\s+", lines[index]))
        or bool(re.match(r"^\s*\d+\.\s+", lines[index]))
        or bool(re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped))
        or is_table_start(lines, index)
    )


def is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return "|" in lines[index] and bool(
        re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", lines[index + 1])
    )


def render_table(
    lines: list[str],
    styles: dict[str, ParagraphStyle],
    max_width: float,
    context: PdfContext,
) -> Table:
    rows = [split_table_row(line) for line in lines]
    header = rows[0]
    body = rows[2:]
    column_count = max(len(row) for row in [header, *body])
    data = []
    for row_index, row in enumerate([header, *body]):
        padded = row + [""] * (column_count - len(row))
        style = styles["Small"] if column_count > 3 else styles["Body"]
        data.append([Paragraph(inline_markup(cell, context), style) for cell in padded])

    col_width = max_width / column_count
    table = Table(data, colWidths=[col_width] * column_count, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9e1ec")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render_image(base_dir: Path, target: str, max_width: float) -> Image | None:
    target_path = (base_dir / unquote(target).split("#")[0]).resolve()
    if not target_path.exists():
        return None

    with PILImage.open(target_path) as img:
        width, height = img.size
    if width <= 0 or height <= 0:
        return None

    max_height = 145 * mm
    scale = min(max_width / width, max_height / height, 1.0)
    return Image(str(target_path), width=width * scale, height=height * scale, hAlign="LEFT")


def inline_markup(text: str, context: PdfContext | None) -> str:
    placeholders: list[str] = []

    def stash(value: str) -> str:
        token = f"@@ITS_PLACEHOLDER_{len(placeholders)}@@"
        placeholders.append(value)
        return token

    text = re.sub(
        r"`([^`]+)`",
        lambda match: stash(
            f'<font name="{context.font_mono if context else "ITSDocMono"}" backColor="#eef3f8">'
            f"{escape_xml(match.group(1))}</font>"
        ),
        text,
    )
    text = escape_xml(text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", lambda match: escape_xml(match.group(1)), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda match: f'<font color="#1769aa">{match.group(1)}</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    for index, value in enumerate(placeholders):
        text = text.replace(f"@@ITS_PLACEHOLDER_{index}@@", value)
    return text


def escape_xml(value: str) -> str:
    return html.escape(value, quote=False)


def draw_footer(canvas, document, context: PdfContext) -> None:
    canvas.saveState()
    canvas.setFont(context.font_regular, 7.5)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(document.leftMargin, 10 * mm, context.title)
    canvas.drawRightString(A4[0] - document.rightMargin, 10 * mm, str(document.page))
    canvas.restoreState()


if __name__ == "__main__":
    main()
