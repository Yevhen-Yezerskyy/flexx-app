from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas

from flexx.models import TippgeberContractText


@dataclass(frozen=True)
class TippgeberContractTextPdfBuildResult:
    pdf_bytes: bytes
    filename: str


_CENTER_BLOCK_RE = re.compile(r"!!([\s\S]*?)!!")
_WORD_OR_SPACE_RE = re.compile(r"\S+|\s+")
_NUMBERED_POINT_RE = re.compile(r"^\s*(\d+\))\s*")
_LETTERED_POINT_RE = re.compile(r"^\s*([A-Za-z]\))\s*")
_BULLET_POINT_RE = re.compile(r"^\s*([•\-])\s+")
_RESET_LIST_RE = re.compile(r"^\s*%%%\s*")
_PAGE_BREAK_RE = re.compile(r"\{\s*BR\s*\}")


def _normalize_text(value: str | None) -> str:
    txt = "" if value is None else str(value)
    return txt.replace("\r\n", "\n").replace("\r", "\n")


def _split_center_blocks(text: str) -> list[tuple[bool, str]]:
    chunks: list[tuple[bool, str]] = []
    pos = 0
    for match in _CENTER_BLOCK_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            chunks.append((False, text[pos:start]))
        chunks.append((True, match.group(1)))
        pos = end
    if pos < len(text):
        chunks.append((False, text[pos:]))
    if not chunks:
        chunks.append((False, text))
    return chunks


def _tokenize_text_with_bold(text: str) -> list[tuple[str, str, bool, bool, bool]]:
    tokens: list[tuple[str, str, bool, bool, bool]] = []
    bold_open = False
    underline_open = False
    raw_open = False
    plain_buf: list[str] = []

    def flush_plain() -> None:
        if plain_buf:
            tokens.append(("text", "".join(plain_buf), bold_open, underline_open, raw_open))
            plain_buf.clear()

    i = 0
    while i < len(text):
        if text.startswith("****", i):
            flush_plain()
            raw_open = not raw_open
            i += 4
            continue
        if raw_open:
            if text.startswith("**", i):
                flush_plain()
                bold_open = not bold_open
                i += 2
                continue
            ch = text[i]
            if ch == "\n":
                flush_plain()
                tokens.append(("newline", "\n", bold_open, underline_open, raw_open))
            elif ch == "\t":
                flush_plain()
                tokens.append(("tab", "\t", bold_open, underline_open, raw_open))
            else:
                plain_buf.append(ch)
            i += 1
            continue
        page_break_match = _PAGE_BREAK_RE.match(text, i)
        if page_break_match:
            flush_plain()
            tokens.append(("page_break", "", bold_open, underline_open, raw_open))
            i = page_break_match.end()
            continue
        if text.startswith("__", i):
            flush_plain()
            underline_open = not underline_open
            i += 2
            continue
        if text.startswith("**", i):
            flush_plain()
            bold_open = not bold_open
            i += 2
            continue
        ch = text[i]
        if ch == "\n":
            flush_plain()
            tokens.append(("newline", "\n", bold_open, underline_open, raw_open))
        elif ch == "\t":
            flush_plain()
            tokens.append(("tab", "\t", bold_open, underline_open, raw_open))
        else:
            plain_buf.append(ch)
        i += 1
    flush_plain()
    return tokens


def _font_name(is_bold: bool) -> str:
    return "Helvetica-Bold" if is_bold else "Helvetica"


def _split_token_text(token_text: str) -> list[str]:
    return _WORD_OR_SPACE_RE.findall(token_text)


def _split_long_piece(piece: str, *, max_width: float, font_name: str, font_size: float) -> list[str]:
    out: list[str] = []
    buf = ""
    for ch in piece:
        next_buf = buf + ch
        if buf and stringWidth(next_buf, font_name, font_size) > max_width:
            out.append(buf)
            buf = ch
        else:
            buf = next_buf
    if buf:
        out.append(buf)
    return out or [piece]


def _split_inline_bold_markers(text: str, base_bold: bool) -> list[tuple[str, bool]]:
    if "**" not in text:
        return [(text, base_bold)]
    parts: list[tuple[str, bool]] = []
    buf: list[str] = []
    bold = base_bold
    i = 0
    while i < len(text):
        if text.startswith("**", i):
            if buf:
                parts.append(("".join(buf), bold))
                buf.clear()
            bold = not bold
            i += 2
            continue
        buf.append(text[i])
        i += 1
    if buf:
        parts.append(("".join(buf), bold))
    return parts


def _line_entries_to_plain(entries: list[tuple[str, str, bool, bool, bool]]) -> str:
    out: list[str] = []
    for token_type, token_value, _, _, _ in entries:
        if token_type == "tab":
            out.append("\t")
        else:
            out.append(token_value)
    return "".join(out)


def _consume_prefix_chars(entries: list[tuple[str, str, bool, bool, bool]], char_count: int) -> list[tuple[str, str, bool, bool, bool]]:
    remain = max(char_count, 0)
    out: list[tuple[str, str, bool, bool, bool]] = []
    for token_type, token_value, token_bold, token_underlined, token_raw in entries:
        if remain <= 0:
            out.append((token_type, token_value, token_bold, token_underlined, token_raw))
            continue
        token_len = 1 if token_type == "tab" else len(token_value)
        if remain >= token_len:
            remain -= token_len
            continue
        if token_type == "tab":
            out.append((token_type, token_value, token_bold, token_underlined, token_raw))
        else:
            out.append((token_type, token_value[remain:], token_bold, token_underlined, token_raw))
        remain = 0
    return out


def _strip_leading_whitespace_entries(entries: list[tuple[str, str, bool, bool, bool]]) -> list[tuple[str, str, bool, bool, bool]]:
    out: list[tuple[str, str, bool, bool, bool]] = []
    trimming = True
    for token_type, token_value, token_bold, token_underlined, token_raw in entries:
        if trimming:
            if token_type == "tab":
                continue
            if token_type == "text":
                stripped = token_value.lstrip()
                if not stripped:
                    continue
                out.append((token_type, stripped, token_bold, token_underlined, token_raw))
                trimming = False
                continue
            trimming = False
        out.append((token_type, token_value, token_bold, token_underlined, token_raw))
    return out


def build_tippgeber_contract_text_pdf() -> TippgeberContractTextPdfBuildResult:
    raw_text = TippgeberContractText.objects.filter(id=1).values_list("text", flat=True).first() or ""
    text = _normalize_text(raw_text)

    page_width, page_height = A4
    margin_left = 36.0
    margin_right = 36.0
    margin_top = 42.0
    margin_bottom = 42.0
    content_width = page_width - margin_left - margin_right

    font_size = 11.0
    leading = 14.0
    paragraph_spacing = leading * 0.5
    double_newline_extra_spacing = leading
    tab_step = 36.0

    def next_tab_stop(x: float) -> float:
        return (int(x / tab_step) + 1) * tab_step

    def draw_line(c: rl_canvas.Canvas, y: float, fragments: list[tuple[float, str, bool, bool]], centered: bool) -> None:
        if not fragments:
            return
        width = max((x + stringWidth(txt, _font_name(bold), font_size)) for x, txt, bold, _ in fragments)
        x_offset = max((content_width - width) / 2.0, 0.0) if centered else 0.0
        for x, txt, bold, underlined in fragments:
            c.setFont(_font_name(bold), font_size)
            draw_x = margin_left + x_offset + x
            c.drawString(draw_x, y, txt)
            if underlined and txt:
                txt_width = stringWidth(txt, _font_name(bold), font_size)
                underline_y = y - 2.2
                c.setLineWidth(1.0)
                c.line(draw_x, underline_y, draw_x + txt_width, underline_y)

    def flush_line(
        c: rl_canvas.Canvas,
        y: float,
        fragments: list[tuple[float, str, bool, bool]],
        centered: bool,
    ) -> tuple[rl_canvas.Canvas, float]:
        if y < margin_bottom:
            c.showPage()
            y = page_height - margin_top
        draw_line(c, y, fragments, centered)
        return c, y - leading

    buffer = BytesIO()
    canvas = rl_canvas.Canvas(buffer, pagesize=A4)
    y = page_height - margin_top

    chunks = _split_center_blocks(text)
    for centered, chunk_text in chunks:
        tokens = _tokenize_text_with_bold(chunk_text)
        list_indent_level = 0
        source_line_entries: list[tuple[str, str, bool, bool, bool]] = []
        current_line_has_text = False

        def render_source_line() -> None:
            nonlocal canvas, y, list_indent_level, source_line_entries
            entries = source_line_entries
            source_line_entries = []
            if not entries:
                return

            marker_text: str | None = None
            line_is_raw = any(token_raw for _, _, _, _, token_raw in entries)
            if not centered and not line_is_raw:
                plain_line = _line_entries_to_plain(entries)
                reset_match = _RESET_LIST_RE.match(plain_line)
                if reset_match:
                    entries = _consume_prefix_chars(entries, reset_match.end())
                    list_indent_level = 0
                    plain_line = _line_entries_to_plain(entries)
                number_match = _NUMBERED_POINT_RE.match(plain_line)
                letter_match = _LETTERED_POINT_RE.match(plain_line)
                bullet_match = _BULLET_POINT_RE.match(plain_line)
                if number_match:
                    marker_text = number_match.group(1)
                    entries = _consume_prefix_chars(entries, number_match.end())
                    entries = _strip_leading_whitespace_entries(entries)
                    list_indent_level = 1
                elif letter_match and list_indent_level >= 1:
                    marker_text = letter_match.group(1)
                    entries = _consume_prefix_chars(entries, letter_match.end())
                    entries = _strip_leading_whitespace_entries(entries)
                    list_indent_level = 2
                elif bullet_match and list_indent_level >= 2:
                    marker_text = bullet_match.group(1)
                    entries = _consume_prefix_chars(entries, bullet_match.end())
                    entries = _strip_leading_whitespace_entries(entries)
                    list_indent_level = 3
                elif bullet_match:
                    marker_text = bullet_match.group(1)
                    entries = _consume_prefix_chars(entries, bullet_match.end())
                    entries = _strip_leading_whitespace_entries(entries)
                    list_indent_level = 1
                else:
                    # Prevent list nesting from leaking into unrelated paragraphs/blocks.
                    # Keep current level only for explicitly indented continuation lines.
                    if plain_line.strip() and not plain_line[:1].isspace():
                        list_indent_level = 0

            line_indent = 0.0 if line_is_raw else ((tab_step * list_indent_level) if (list_indent_level > 0 and not centered) else 0.0
            )
            line: list[tuple[float, str, bool, bool]] = []
            if marker_text:
                marker_x = max(line_indent - tab_step, 0.0)
                line.append((marker_x, marker_text, False, False))
            cursor_x = line_indent

            def add_piece(piece: str, is_bold: bool, is_underlined: bool) -> None:
                nonlocal line, cursor_x, canvas, y
                if not piece:
                    return
                font_name = _font_name(is_bold)
                piece_width = stringWidth(piece, font_name, font_size)
                if cursor_x + piece_width <= content_width:
                    line.append((cursor_x, piece, is_bold, is_underlined))
                    cursor_x += piece_width
                    return
                if cursor_x > line_indent:
                    canvas, y = flush_line(canvas, y, line, centered)
                    line = []
                    cursor_x = line_indent
                if stringWidth(piece, font_name, font_size) <= content_width:
                    if piece.strip():
                        line.append((cursor_x, piece, is_bold, is_underlined))
                        cursor_x += stringWidth(piece, font_name, font_size)
                    return
                for part in _split_long_piece(piece, max_width=content_width - line_indent, font_name=font_name, font_size=font_size):
                    part_width = stringWidth(part, font_name, font_size)
                    if part_width > content_width:
                        continue
                    if cursor_x + part_width > content_width and cursor_x > line_indent:
                        canvas, y = flush_line(canvas, y, line, centered)
                        line = []
                        cursor_x = line_indent
                    line.append((cursor_x, part, is_bold, is_underlined))
                    cursor_x += part_width
                    if cursor_x >= content_width:
                        canvas, y = flush_line(canvas, y, line, centered)
                        line = []
                        cursor_x = line_indent

            if line_is_raw:
                for token_type, token_value, token_bold, token_underlined, _ in entries:
                    if token_type == "tab":
                        cursor_x = next_tab_stop(cursor_x)
                        continue
                    if token_type != "text" or not token_value:
                        continue
                    for seg_text, seg_bold in _split_inline_bold_markers(token_value, token_bold):
                        remaining = seg_text
                        while remaining:
                            part_limit = max(content_width - cursor_x, 1.0)
                            parts = _split_long_piece(
                                remaining,
                                max_width=part_limit,
                                font_name=_font_name(seg_bold),
                                font_size=font_size,
                            )
                            first = parts[0]
                            first_w = stringWidth(first, _font_name(seg_bold), font_size)
                            if cursor_x + first_w > content_width and cursor_x > line_indent:
                                canvas, y = flush_line(canvas, y, line, centered)
                                line = []
                                cursor_x = line_indent
                                continue
                            line.append((cursor_x, first, seg_bold, token_underlined))
                            cursor_x += first_w
                            remaining = remaining[len(first) :]
                            if remaining:
                                canvas, y = flush_line(canvas, y, line, centered)
                                line = []
                                cursor_x = line_indent
            else:
                for token_type, token_value, token_bold, token_underlined, _ in entries:
                    if token_type == "tab":
                        tab_x = next_tab_stop(cursor_x)
                        if tab_x > content_width:
                            canvas, y = flush_line(canvas, y, line, centered)
                            line = []
                            cursor_x = next_tab_stop(line_indent)
                        else:
                            cursor_x = tab_x
                        continue
                    for piece in _split_token_text(token_value):
                        add_piece(piece, token_bold, token_underlined)

            if line:
                canvas, y = flush_line(canvas, y, line, centered)

        for token_type, token_value, token_bold, token_underlined, token_raw in tokens:
            if token_type == "page_break":
                render_source_line()
                canvas.showPage()
                y = page_height - margin_top
                current_line_has_text = False
                continue
            if token_type == "newline":
                if source_line_entries:
                    render_source_line()
                elif token_raw:
                    # In raw zone every newline is a literal blank line.
                    y -= leading
                if not token_raw:
                    y -= paragraph_spacing
                    if not current_line_has_text:
                        y -= double_newline_extra_spacing
                current_line_has_text = False
                continue
            source_line_entries.append((token_type, token_value, token_bold, token_underlined, token_raw))
            if token_type == "text" and token_value.strip():
                current_line_has_text = True

        render_source_line()

    canvas.save()
    pdf_bytes = buffer.getvalue()
    return TippgeberContractTextPdfBuildResult(
        pdf_bytes=pdf_bytes,
        filename="FleXXLager-Tippgeber-Vertrag.pdf",
    )
