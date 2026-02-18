from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Any

from babel.dates import format_date
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from flexx.contract_helpers import build_stueckzinsen_rows_for_issue
from flexx.models import Contract


def _format_text(value) -> str:
    txt = "" if value is None else str(value)
    txt = txt.replace("\\t", "\t")
    txt = txt.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    txt = re.sub(r"\*\*(?=\S)([\s\S]+?)(?<=\S)\*\*", r"<b>\1</b>", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt

@dataclass(frozen=True)
class ContractPdfBuildResult:
    pdf_bytes: bytes
    filename: str


class ContractPdfCreator:
    # --- PDF settings ---
    PAGE_SIZE = A4

    FONT_FAMILY = "Helvetica"
    FONT_FAMILY_BOLD = "Helvetica-Bold"

    FONT_SIZE_HEADER_1 = 14
    FONT_SIZE_HEADER_2 = 11
    FONT_SIZE_TEXT = 10
    FONT_SIZE_SMALL = 7.5
    PARAGRAPH_TOP_GAP = 4

    MARGIN_LEFT = 28
    MARGIN_RIGHT = 28
    MARGIN_TOP = 30
    MARGIN_BOTTOM = 36

    BLOCK_GAP_MD = 8
    BLOCK_GAP_LG = 10
    BLOCK_GAP_XXL = 16

    def __init__(self, contract_id: int):
        self.contract = Contract.objects.select_related("issue", "client").get(id=int(contract_id))
        self.issue = self.contract.issue
        self.client = self.contract.client
        self.content: dict = {}
        self.y: float = 0.0

    @property
    def content_width(self) -> float:
        return self.PAGE_SIZE[0] - self.MARGIN_LEFT - self.MARGIN_RIGHT

    def _cursor_reset(self) -> None:
        self.y = self.PAGE_SIZE[1] - self.MARGIN_TOP

    def _cursor_gap(self, gap: float) -> None:
        self.y -= gap

    def _build_paragraph(
        self,
        text: str,
        font_size: float,
        *,
        font_name: str | None = None,
        alignment: int = TA_JUSTIFY,
    ) -> Paragraph:
        paragraph_text = _format_text(text).replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;").replace("\n", "<br/>")
        style = ParagraphStyle(
            name="contract-text",
            fontName=font_name or self.FONT_FAMILY,
            fontSize=font_size,
            leading=font_size * 1.2,
            alignment=alignment,
        )
        return Paragraph(paragraph_text, style)

    def _split_paragraphs(self, text: str) -> list[str]:
        normalized = _format_text(text)
        if not normalized:
            return []
        return [part.lstrip() for part in normalized.split("\n\n")]

    def draw_text(self, c: Canvas, text: str, y_top: float | None = None, font_size: float | None = None) -> float:
        size = font_size or self.FONT_SIZE_TEXT
        y = self.y if y_top is None else y_top
        x = self.MARGIN_LEFT
        width = self.content_width
        parts = self._split_paragraphs(text)
        for idx, part in enumerate(parts):
            if idx > 0:
                y -= self.PARAGRAPH_TOP_GAP
            paragraph = self._build_paragraph(part, size)
            _, h = paragraph.wrap(width, self.PAGE_SIZE[1])
            paragraph.drawOn(c, x, y - h)
            y -= h
        self.y = y
        return self.y

    def draw_text_footnote(self, c: Canvas, text: str, y_top: float | None = None, font_size: float | None = None) -> float:
        size = font_size or self.FONT_SIZE_SMALL
        y = self.y if y_top is None else y_top
        x_marker = self.MARGIN_LEFT
        indent = 12.0
        x_text = x_marker + indent
        width = self.content_width - indent

        for raw_line in _format_text(text).split("\n"):
            if not raw_line.strip():
                y -= self.PARAGRAPH_TOP_GAP
                continue

            marker = ""
            line_text = raw_line
            m = re.match(r"^(\*{1,2})\s*(.*)$", raw_line)
            if m:
                marker = m.group(1)
                line_text = m.group(2)

            paragraph = self._build_paragraph(line_text, size)
            _, h = paragraph.wrap(max(width, 1), self.PAGE_SIZE[1])

            if marker:
                c.setFont(self.FONT_FAMILY, size)
                c.drawString(x_marker, y - size, marker)
            paragraph.drawOn(c, x_text, y - h)
            y -= h

        self.y = y
        return self.y

    def draw_framed_text(
        self,
        c: Canvas,
        text: str,
        y_top: float | None = None,
        font_size: float | None = None,
        frame_width: float | None = None,
        left_indent: float | None = None,
    ) -> float:
        size = font_size or self.FONT_SIZE_TEXT
        y = self.y if y_top is None else y_top
        x = self.MARGIN_LEFT if left_indent is None else left_indent
        width = frame_width or self.content_width
        padding = 6.0
        parts = self._split_paragraphs(text)
        inner_width = max(width - (padding * 2), 1)
        paragraph_heights: list[float] = []
        for part in parts:
            paragraph = self._build_paragraph(part, size)
            _, h = paragraph.wrap(inner_width, self.PAGE_SIZE[1])
            paragraph_heights.append(h)
        total_text_h = sum(paragraph_heights)
        if len(paragraph_heights) > 1:
            total_text_h += self.PARAGRAPH_TOP_GAP * (len(paragraph_heights) - 1)
        box_height = total_text_h + (padding * 2)
        y_bottom = y - box_height

        c.setLineWidth(0.7)
        c.rect(x, y_bottom, width, box_height)

        draw_y = y - padding
        for idx, part in enumerate(parts):
            if idx > 0:
                draw_y -= self.PARAGRAPH_TOP_GAP
            paragraph = self._build_paragraph(part, size)
            _, h = paragraph.wrap(inner_width, self.PAGE_SIZE[1])
            paragraph.drawOn(c, x + padding, draw_y - h)
            draw_y -= h
        self.y = y_bottom
        return y_bottom

    def _measure_text_height(self, text: str, font_size: float, width: float) -> float:
        parts = self._split_paragraphs(text)
        if not parts:
            return 0.0
        total = 0.0
        for idx, part in enumerate(parts):
            paragraph = self._build_paragraph(part, font_size)
            _, h = paragraph.wrap(max(width, 1), self.PAGE_SIZE[1])
            total += h
            if idx > 0:
                total += self.PARAGRAPH_TOP_GAP
        return total

    def _ensure_space(self, c: Canvas, needed_height: float) -> None:
        if self.y - needed_height < self.MARGIN_BOTTOM:
            c.showPage()
            self._cursor_reset()

    def _resolve_from_path(self, source: dict[str, Any], path: str) -> Any:
        current: Any = source
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
            if current is None:
                break
        return current

    def _draw_paragraph_in_cell(
        self,
        c: Canvas,
        text: str,
        x: float,
        y_top: float | None,
        width: float,
        top_pad: float,
        font_size: float,
        *,
        font_name: str | None = None,
        alignment: int = TA_JUSTIFY,
    ) -> None:
        if not _format_text(text).strip():
            return
        paragraph = self._build_paragraph(text, font_size, font_name=font_name, alignment=alignment)
        _, h = paragraph.wrap(max(width, 1), self.PAGE_SIZE[1])
        paragraph.drawOn(c, x, y_top - top_pad - h)

    def draw_table(
        self,
        c: Canvas,
        y_top: float | None,
        rows: int,
        cols: list[list[float]],
        cell_map: list[list[dict[str, Any]]],
        *,
        source: dict[str, Any] | None = None,
        table_width: float | None = None,
        left_indent: float | None = None,
        row_height: float | None = None,
        label_font_size: float = 6.0,
        value_font_size: float | None = None,
        label_top_pad: float = 0.5,
        value_top_pad: float = 9.0,
        label_align: int = TA_JUSTIFY,
        value_align: int = TA_JUSTIFY,
        label_bold: bool = False,
        value_bold: bool = False,
        row_bottom_pad: float = 2.0,
        min_row_height: float = 24.0,
    ) -> float:
        value_size = self.FONT_SIZE_TEXT if value_font_size is None else value_font_size
        src = source or self.content
        y = self.y if y_top is None else y_top
        x = self.MARGIN_LEFT if left_indent is None else left_indent
        width = table_width or self.content_width
        default_row_h = min_row_height if row_height is None else float(row_height)

        row_heights: list[float] = []
        for row_idx in range(rows):
            if row_height is not None:
                row_heights.append(default_row_h)
                continue

            row_cols = cols[row_idx]
            row_cells = cell_map[row_idx]
            row_needed_h = default_row_h
            for col_idx, share in enumerate(row_cols):
                cell_w = width * share
                cell_cfg = row_cells[col_idx] if col_idx < len(row_cells) else {}
                cell_data = self._resolve_from_path(src, cell_cfg["from"]) if "from" in cell_cfg else cell_cfg
                label = _format_text((cell_data or {}).get(cell_cfg.get("label_key", "label"), ""))
                value = _format_text((cell_data or {}).get(cell_cfg.get("value_key", "value"), ""))

                content_w = max(cell_w - 8, 1)
                label_h = 0.0
                if label.strip():
                    label_p = self._build_paragraph(
                        label,
                        label_font_size,
                        font_name=self.FONT_FAMILY_BOLD if label_bold else self.FONT_FAMILY,
                        alignment=label_align,
                    )
                    _, label_h = label_p.wrap(content_w, self.PAGE_SIZE[1])

                value_h = 0.0
                if value.strip():
                    value_p = self._build_paragraph(
                        value,
                        value_size,
                        font_name=self.FONT_FAMILY_BOLD if value_bold else self.FONT_FAMILY,
                        alignment=value_align,
                    )
                    _, value_h = value_p.wrap(content_w, self.PAGE_SIZE[1])

                needed_h = max(label_top_pad + label_h, value_top_pad + value_h) + row_bottom_pad
                row_needed_h = max(row_needed_h, needed_h)

            row_heights.append(row_needed_h)

        total_height = sum(row_heights)

        c.setLineWidth(0.7)
        c.rect(x, y - total_height, width, total_height)

        y_cursor = y
        for row_idx in range(rows):
            row_h = row_heights[row_idx]
            y_next = y_cursor - row_h
            if row_idx > 0:
                c.line(x, y_cursor, x + width, y_cursor)

            row_cols = cols[row_idx]
            row_cells = cell_map[row_idx]
            cx = x
            for col_idx, share in enumerate(row_cols):
                cell_w = width * share
                if col_idx > 0:
                    c.line(cx, y_cursor, cx, y_next)

                cell_cfg = row_cells[col_idx] if col_idx < len(row_cells) else {}
                cell_data = self._resolve_from_path(src, cell_cfg["from"]) if "from" in cell_cfg else cell_cfg
                label = _format_text((cell_data or {}).get(cell_cfg.get("label_key", "label"), ""))
                value = _format_text((cell_data or {}).get(cell_cfg.get("value_key", "value"), ""))

                self._draw_paragraph_in_cell(
                    c,
                    label,
                    cx + 4,
                    y_cursor,
                    cell_w - 8,
                    label_top_pad,
                    label_font_size,
                    font_name=self.FONT_FAMILY_BOLD if label_bold else self.FONT_FAMILY,
                    alignment=label_align,
                )
                self._draw_paragraph_in_cell(
                    c,
                    value,
                    cx + 4,
                    y_cursor,
                    cell_w - 8,
                    value_top_pad,
                    value_size,
                    font_name=self.FONT_FAMILY_BOLD if value_bold else self.FONT_FAMILY,
                    alignment=value_align,
                )
                cx += cell_w

            y_cursor = y_next

        self.y = y - total_height
        return self.y

    def draw_framed_calc_block(
        self,
        c: Canvas,
        table_code: dict[str, Any],
        y_top: float | None = None,
        font_size: float | None = None,
        frame_width: float | None = None,
        left_indent: float | None = None,
    ) -> float:
        size = font_size or self.FONT_SIZE_TEXT
        calc_row_gap = 7.0
        calc_col_gap = 7.0
        calc_sign_col_w = 20.0
        calc_value_col_w = 60.0
        calc_eur_col_w = 40.0
        calc_padding_top = 10.0
        calc_padding_bottom = 10.0
        y = self.y if y_top is None else y_top
        x = self.MARGIN_LEFT if left_indent is None else left_indent
        width = frame_width or self.content_width
        padding = 6.0

        rows = table_code.get("rows", [])
        inner_x = x + padding
        inner_w = max(width - (padding * 2), 1)
        gap = calc_col_gap
        sign_w = calc_sign_col_w
        value_w = calc_value_col_w
        currency_w = calc_eur_col_w

        x_sign = inner_x
        x_value = x_sign + sign_w + gap
        x_currency = x_value + value_w + gap
        x_text = x_currency + currency_w + gap
        text_w = max(inner_w - (x_text - inner_x), 1)

        row_heights: list[float] = []
        for row in rows:
            p = self._build_paragraph(_format_text(row.get("text", "")), size)
            _, h = p.wrap(max(text_w - (padding * 2), 1), self.PAGE_SIZE[1])
            row_heights.append(max(h, size * 1.2))

        baselines: list[float] = []
        baseline_cursor = y - calc_padding_top
        for idx, h in enumerate(row_heights):
            if idx > 0:
                baseline_cursor -= calc_row_gap
            baselines.append(baseline_cursor - size)
            baseline_cursor -= h

        total_h = calc_padding_top + calc_padding_bottom + sum(row_heights)
        if row_heights:
            total_h += calc_row_gap * (len(row_heights) - 1)
        y_bottom = y - total_h

        c.setLineWidth(0.7)
        c.rect(x, y_bottom, width, total_h)

        draw_y = y - calc_padding_top
        for idx, row in enumerate(rows):
            if idx > 0:
                draw_y -= calc_row_gap
            h = row_heights[idx]

            c.setFont(self.FONT_FAMILY_BOLD, size)
            sign_txt = _format_text(row.get("sign", ""))
            value_txt = _format_text(row.get("value", ""))
            currency_txt = _format_text(row.get("currency", ""))

            sign_w_txt = c.stringWidth(sign_txt, self.FONT_FAMILY_BOLD, size)
            value_w_txt = c.stringWidth(value_txt, self.FONT_FAMILY_BOLD, size)
            eur_w_txt = c.stringWidth(currency_txt, self.FONT_FAMILY_BOLD, size)

            c.drawString(x_sign + max(sign_w - sign_w_txt - 2, 0), draw_y - size, sign_txt)
            c.drawString(x_value + max(value_w - value_w_txt - 2, 0), draw_y - size, value_txt)
            c.drawString(x_currency + max((currency_w - eur_w_txt) / 2, 0), draw_y - size, currency_txt)

            if row.get("underline_value_cell") and idx + 1 < len(baselines):
                line_y = (baselines[idx] + baselines[idx + 1]) / 2.0
                if idx == 1:
                    line_y += 4.0
                if idx == 3:
                    line_y -= 3.0
                c.setLineWidth(0.7)
                c.line(x_value + 2, line_y, x_currency + currency_w - 2, line_y)

            p = self._build_paragraph(_format_text(row.get("text", "")), size)
            p.wrap(max(text_w - (padding * 2), 1), self.PAGE_SIZE[1])
            p.drawOn(c, x_text, draw_y - h)
            draw_y -= h

        self.y = y_bottom
        return y_bottom

    def draw_signature_block(
        self,
        c: Canvas,
        y_top: float | None = None,
        gap_between_lines: float = 40.0,
    ) -> float:
        y = self.y if y_top is None else y_top
        y -= 20.0
        x = self.MARGIN_LEFT
        width = self.content_width
        line_y = y
        label_gap = 2.0
        label_y = line_y - label_gap - self.FONT_SIZE_TEXT + 3.0

        line_w = (width - gap_between_lines) / 2.0
        left_x1 = x
        left_x2 = left_x1 + line_w
        right_x1 = left_x2 + gap_between_lines
        right_x2 = right_x1 + line_w

        c.setLineWidth(0.7)
        c.line(left_x1, line_y, left_x2, line_y)
        c.line(right_x1, line_y, right_x2, line_y)
        lower_line_y = line_y - 35.0
        c.line(x, lower_line_y, x + width, lower_line_y)

        c.setFont(self.FONT_FAMILY, self.FONT_SIZE_SMALL)
        c.drawString(left_x1, label_y, "Ort, Datum")
        c.drawString(right_x1, label_y, "Unterschrift des Käufers / Zeichners")
        c.setFont(self.FONT_FAMILY, self.FONT_SIZE_SMALL)
        c.drawString(
            x,
            lower_line_y - 3.0 - self.FONT_SIZE_SMALL,
            "(nur von der FleXXLager GmbH & Co. KG auszufüllen)",
        )
        c.setFont(self.FONT_FAMILY, self.FONT_SIZE_TEXT)
        c.drawString(
            x,
            lower_line_y - 29.0 - self.FONT_SIZE_TEXT,
            "Zeichnung in Höhe von __________________ Inhaber-Teilschuldverschreibungen angenommen.",
        )

        self.y = label_y - self.BLOCK_GAP_LG
        return self.y

    def draw_bottom_company_footer(self, c: Canvas) -> None:
        c.setFont(self.FONT_FAMILY, self.FONT_SIZE_TEXT)
        c.drawString(
            self.MARGIN_LEFT,
            self.MARGIN_BOTTOM + 2.0,
            "Siegen, den _______________      _______________________ / FleXXLager GmbH & Co. KG",
        )

    def draw_interest_tables_headers(self, c: Canvas, y_top: float | None = None) -> float:
        y = self.y if y_top is None else y_top
        x = self.MARGIN_LEFT
        width = self.content_width
        gap = 12.0
        table_w = (width - (gap * 2)) / 3.0

        bond_price = Decimal(self.issue.bond_price) if self.issue.bond_price is not None else None
        if bond_price is None:
            bond_price_text = "[__]"
        else:
            bond_price_text = f"{bond_price.quantize(Decimal('0.01'))}".replace(".", ",")

        left_header = f"Stückzinsen je Teilschuldverschreibung zu EUR {bond_price_text}\nin EUR"
        right_header = "Datum der Einzahlung"

        for idx in range(3):
            tx = x + idx * (table_w + gap)
            self.draw_table(
                c,
                y_top=y,
                rows=1,
                cols=[[0.52, 0.48]],
                cell_map=[[{"label": "", "value": left_header}, {"label": "", "value": right_header}]],
                table_width=table_w,
                left_indent=tx,
                label_font_size=self.FONT_SIZE_SMALL,
                value_font_size=self.FONT_SIZE_SMALL,
                label_top_pad=0.0,
                value_top_pad=5.0,
                value_align=1,
                value_bold=True,
                row_bottom_pad=5.0,
            )

        self.y = min(self.y, y)
        return self.y

    def draw_interest_tables_rows(self, c: Canvas, y_top: float | None = None) -> float:
        y = self.y if y_top is None else y_top
        x = self.MARGIN_LEFT
        width = self.content_width
        gap = 12.0
        table_w = (width - (gap * 2)) / 3.0
        content_top_pad = 5.0
        content_bottom_pad = 5.0

        if not (self.issue.issue_date and self.issue.term_months and self.issue.interest_rate and self.issue.bond_price):
            self.y = y
            return self.y

        rows = build_stueckzinsen_rows_for_issue(
            issue_date=self.issue.issue_date,
            term_months=self.issue.term_months,
            interest_rate_percent=Decimal(self.issue.interest_rate),
            nominal_value=Decimal(self.issue.bond_price),
            decimals=6,
            holiday_country="DE",
            holiday_subdiv=None,
        )
        period_start = self.issue.issue_date
        try:
            period_end = period_start.replace(year=period_start.year + 1) - timedelta(days=1)
        except ValueError:
            # 29 Feb -> 28 Feb next year, then minus one day.
            period_end = period_start.replace(year=period_start.year + 1, month=2, day=28) - timedelta(days=1)

        period_rows = [r for r in rows if period_start <= r.pay_date <= period_end]
        if not period_rows:
            self.y = y
            return self.y

        per_col = (len(period_rows) + 2) // 3
        split_cols = [period_rows[i * per_col:(i + 1) * per_col] for i in range(3)]
        num_w = max((table_w * 0.52) - 8, 1)
        date_w = max((table_w * 0.48) - 8, 1)
        num_h_max = 0.0
        date_h_max = 0.0
        for r in period_rows:
            p_num = self._build_paragraph(r.stueckzins_de, self.FONT_SIZE_SMALL)
            _, h_num = p_num.wrap(num_w, self.PAGE_SIZE[1])
            num_h_max = max(num_h_max, h_num)

            p_date = self._build_paragraph(
                format_date(r.pay_date, format="d. LLL yy", locale="de_DE"),
                self.FONT_SIZE_SMALL,
            )
            _, h_date = p_date.wrap(date_w, self.PAGE_SIZE[1])
            date_h_max = max(date_h_max, h_date)

        row_h = max(content_top_pad + num_h_max, content_top_pad + date_h_max) + content_bottom_pad
        max_rows = max(len(c_rows) for c_rows in split_cols)
        row_offset = 0
        last_bottom = y
        while row_offset < max_rows:
            available_h = y - self.MARGIN_BOTTOM
            rows_fit = max(1, int(available_h // row_h))
            take = min(rows_fit, max_rows - row_offset)

            bottoms: list[float] = []
            for idx, all_rows in enumerate(split_cols):
                col_rows = all_rows[row_offset:row_offset + take]
                if not col_rows:
                    continue
                tx = x + idx * (table_w + gap)
                cell_map = [[
                    {"label": "", "value": r.stueckzins_de},
                    {"label": "", "value": format_date(r.pay_date, format="d. LLL yy", locale="de_DE")},
                ] for r in col_rows]
                bottom = self.draw_table(
                    c,
                    y_top=y,
                    rows=len(cell_map),
                    cols=[[0.52, 0.48] for _ in range(len(cell_map))],
                    cell_map=cell_map,
                    table_width=table_w,
                    left_indent=tx,
                    row_height=row_h,
                    label_font_size=self.FONT_SIZE_SMALL,
                    value_font_size=self.FONT_SIZE_SMALL,
                    label_top_pad=0.0,
                    value_top_pad=content_top_pad,
                    value_align=1,
                    row_bottom_pad=content_bottom_pad,
                    min_row_height=0.0,
                )
                bottoms.append(bottom)

            if bottoms:
                last_bottom = min(bottoms)

            row_offset += take
            if row_offset < max_rows:
                c.showPage()
                self._cursor_reset()
                y = self.y

        self.y = last_bottom
        return self.y

    def _build_framed_block_2(self) -> dict[str, Any]:
        def _fmt_6(v: Decimal | None) -> str:
            if v is None:
                return "[__]"
            return f"{v.quantize(Decimal('0.000001'))}".replace(".", ",")

        def _fmt_2(v: Decimal | None) -> str:
            if v is None:
                return "[__]"
            return f"{v.quantize(Decimal('0.01'))}".replace(".", ",")

        bond_price = Decimal(self.issue.bond_price) if self.issue.bond_price is not None else None
        nominal = Decimal(self.contract.nominal_amount) if self.contract.nominal_amount is not None else None
        total = Decimal(self.contract.nominal_amount_plus_percent) if self.contract.nominal_amount_plus_percent is not None else None
        qty = self.contract.bonds_quantity

        st_total = (total - nominal) if (total is not None and nominal is not None) else None
        per_bond_st = (st_total / Decimal(qty)) if (st_total is not None and qty) else None
        per_bond_total = (bond_price + per_bond_st) if (bond_price is not None and per_bond_st is not None) else None

        qty_text = str(qty) if qty else "[__]"
        bond_price_text = _fmt_2(bond_price)
        return {
            "cols": {
                "sign": 0.08,
                "value": 0.22,
                "currency": 0.10,
                "text": 0.60,
            },
            "rows": [
                {"sign": "", "value": bond_price_text, "currency": "EUR", "text": "Ausgabebetrag (Ausgabekurs 100%)"},
                {
                    "sign": "+",
                    "value": _fmt_6(per_bond_st),
                    "currency": "EUR",
                    "text": "Stückzinsen gemäß Stückzinstabelle zum Tag der Zeichnung**",
                    "underline_value_cell": True,
                },
                {
                    "sign": "=",
                    "value": _fmt_6(per_bond_total),
                    "currency": "EUR",
                    "text": "Ausgabepreis/Kaufpreis pro Inhaber-Teilschuldverschreibung**",
                },
                {
                    "sign": "x",
                    "value": qty_text,
                    "currency": "",
                    "text": f"Stückzahl (mindestens fünftausend (5.000) Inhaber-Teilschuldverschreibungen i.H.v. EUR {bond_price_text})",
                    "underline_value_cell": True,
                },
                {"sign": "=", "value": _fmt_2(total), "currency": "EUR", "text": "**Gesamtbetrag (Kaufsumme)**"},
            ],
        }

    def load_content(self) -> None:
        issue_contract = self.issue.contract if isinstance(self.issue.contract, dict) else {}
        full_name = f"{_format_text(self.client.first_name)} {_format_text(self.client.last_name)}".strip()
        zip_city = f"{_format_text(self.client.zip_code)} {_format_text(self.client.city)}".strip()
        issue_date = format_date(self.issue.issue_date, format="d. MMMM y", locale="de_DE") if self.issue.issue_date else ""

        self.content = {
            "framed_block_1": {
                "text_1": "**Bitte vollständig ausgefüllt und unterzeichnet zurücksenden an:**\n\n",
                "text_2": _format_text(issue_contract.get("unternehmen_emittent")),
            },
            "header_1": _format_text( "**Zeichnungsschein / Wertpapierkaufantrag**" ),
            "text_block_1": _format_text(issue_contract.get("ueberschrift_emission")),
            "header_2": _format_text( "**Käufer / Zeichner:**" ),
            "fill_table_1": {
                "field_1": {"label": "Name", "value": _format_text(self.client.last_name)},
                "field_2": {"label": "Vorname", "value": _format_text(self.client.first_name)},
                "field_3": {
                    "label": "Geburtsdatum (TTMMJJJJ)",
                    "value": self.client.birth_date.strftime("%d%m%Y") if self.client.birth_date else "",
                },
                "field_4": {"label": "Firma", "value": _format_text(self.client.company)},
                "field_5": {"label": "Straße, Hausnummer", "value": _format_text(self.client.street)},
                "field_6": {
                    "label": "PLZ, Ort",
                    "value": zip_city,
                },
                "field_7": {"label": "Telefon", "value": _format_text(self.client.phone)},
                "field_8": {"label": "Mobiltelefon", "value": _format_text(self.client.mobile_phone)},
                "field_9": {"label": "Fax-Nr.", "value": _format_text(self.client.fax)},
                "field_10": {"label": "E-Mail", "value": _format_text(self.client.email)},
                "field_11": {"label": "Nur bei Firmen: Handelsregister", "value": _format_text(self.client.handelsregister)},
                "field_12": {"label": "Handelsregister-Nummer", "value": _format_text(self.client.handelsregister_number)},
                "field_13": {"label": "Ansprechpartner", "value": _format_text(self.client.contact_person)},
            },
            "text_block_2": _format_text(issue_contract.get("text_zwischen_1")),
            "framed_block_2": self._build_framed_block_2(),
            "framed_block_3": _format_text(issue_contract.get("banking")),
            "small_text_1": _format_text(
                "* Es besteht kein Anspruch auf Zuteilung.\n"
                f"** Gerundet. Stückzinsen fallen bei einer Zeichnung ab dem {issue_date} an.\n"
                "Die Emittentin ist berechtigt, sofern der angeforderte Einzahlungsbetrag nicht innerhalb "
                "der benannten Frist eingeht, weitere Stückzinsen bis zum Tag des vollständigen "
                "Zahlungseingangs zu berechnen."
            ),
            "text_block_3": _format_text(issue_contract.get("text_zwischen_2")),
            "text_block_4": "Die Inhaber-Teilschuldverschreibungen sollen in nachfolgendes Depot eingebucht werden:",
            "fill_table_2": {
                "title": "Depot-Informationen des Käufers / Zeichners:",
                "field_1": {"label": "Depotinhaber (Vorname und Nachname oder Firma)", "value": full_name},
                "field_2": {"label": "Depotnummer", "value": _format_text(self.client.bank_depo_depotnummer)},
                "field_3": {"label": "Bank / Kreditinstitut", "value": _format_text(self.client.bank_depo_name)},
                "field_4": {"label": "BLZ", "value": _format_text(self.client.bank_depo_blz)},
            },
            #new page
            "text_block_5": (
                "Im Falle der Kürzung oder Ablehnung von Zeichnungen soll die zu viel gezahlte Kaufsumme "
                "durch Überweisung auf das nachfolgend benannte Konto erstattet werden:"
            ),
            "fill_table_3": {
                "title": "Konto-Informationen des Käufers / Zeichners:",
                "field_1": {"label": "Kontoinhaber (Vorname und Nachname oder Firma)", "value": full_name},
                "field_2": {"label": "IBAN / Kontonummer", "value": _format_text(self.client.bank_iban)},
                "field_3": {"label": "Bank / Kreditinstitut", "value": _format_text(self.client.bank_name)},
                "field_4": {"label": "BIC / BLZ", "value": _format_text(self.client.bank_bic)},
            },
            "text_block_6": _format_text(issue_contract.get("text_zwischen_3")),
            "header_3": _format_text(issue_contract.get("ueberschrift_ergaenzung")),
            "text_block_7": _format_text(issue_contract.get("ergaenzung_text_1")),
            "text_block_8": _format_text(issue_contract.get("ergaenzung_beispiel")),
        }

    def build(self) -> ContractPdfBuildResult:
        self.load_content()
        buffer = BytesIO()
        c = rl_canvas.Canvas(buffer, pagesize=self.PAGE_SIZE)
        self._cursor_reset()

        block_1 = self.content.get("framed_block_1", {})
        block_1_text = f"{block_1.get('text_1', '')}\n{block_1.get('text_2', '')}"
        self.draw_framed_text(
            c,
            block_1_text,
            frame_width=self.content_width * 0.62,
            left_indent=self.MARGIN_LEFT + 30.0,
        )
        self._cursor_gap(self.BLOCK_GAP_XXL + 4)

        self.draw_text(c, self.content.get("header_1", ""), font_size=self.FONT_SIZE_HEADER_1)
        self._cursor_gap(self.BLOCK_GAP_MD - 2)
        self.draw_text(c, self.content.get("text_block_1", ""), font_size=self.FONT_SIZE_HEADER_2)
        self._cursor_gap(self.BLOCK_GAP_MD)

        self.draw_text(c, self.content.get("header_2", ""), font_size=self.FONT_SIZE_HEADER_2)
        self._cursor_gap(4)

        self.draw_table(
            c,
            y_top=None,
            rows=5,
            cols=[
                [0.34, 0.39, 0.27],
                [1.0],
                [0.5, 0.5],
                [0.2167, 0.2167, 0.2166, 0.35],
                [0.34, 0.33, 0.33],
            ],
            cell_map=[
                [{"from": "fill_table_1.field_1"}, {"from": "fill_table_1.field_2"}, {"from": "fill_table_1.field_3"}],
                [{"from": "fill_table_1.field_4"}],
                [{"from": "fill_table_1.field_5"}, {"from": "fill_table_1.field_6"}],
                [
                    {"from": "fill_table_1.field_7"},
                    {"from": "fill_table_1.field_8"},
                    {"from": "fill_table_1.field_9"},
                    {"from": "fill_table_1.field_10"},
                ],
                [{"from": "fill_table_1.field_11"}, {"from": "fill_table_1.field_12"}, {"from": "fill_table_1.field_13"}],
            ],
        )
        self._cursor_gap(4)

        self.draw_text(c, self.content.get("text_block_2", ""))
        self._cursor_gap(self.BLOCK_GAP_MD)

        self.draw_framed_calc_block(c, self.content.get("framed_block_2", {}))
        self.draw_framed_text(c, self.content.get("framed_block_3", ""))
        self._cursor_gap(self.BLOCK_GAP_MD - 4)

        self.draw_text_footnote(c, self.content.get("small_text_1", ""), font_size=self.FONT_SIZE_SMALL)
        self._cursor_gap(self.BLOCK_GAP_MD)

        self.draw_text(c, self.content.get("text_block_3", ""))
        self._cursor_gap(self.BLOCK_GAP_LG)

        self.draw_text(c, self.content.get("text_block_4", ""))
        self._cursor_gap(self.BLOCK_GAP_MD)

        self.draw_text(c, self.content.get("fill_table_2", {}).get("title", ""))
        self._cursor_gap(4)
        self.draw_table(
            c,
            y_top=None,
            rows=2,
            cols=[[0.5, 0.5], [0.5, 0.5]],
            cell_map=[
                [{"from": "fill_table_2.field_1"}, {"from": "fill_table_2.field_2"}],
                [{"from": "fill_table_2.field_3"}, {"from": "fill_table_2.field_4"}],
            ],
        )
        self._cursor_gap(self.BLOCK_GAP_LG)

        c.showPage()
        self._cursor_reset()
        self.draw_text(c, self.content.get("text_block_5", ""))
        self._cursor_gap(self.BLOCK_GAP_LG)

        self.draw_text(c, self.content.get("fill_table_3", {}).get("title", ""))
        self._cursor_gap(4)
        self.draw_table(
            c,
            y_top=None,
            rows=2,
            cols=[[0.5, 0.5], [0.5, 0.5]],
            cell_map=[
                [{"from": "fill_table_3.field_1"}, {"from": "fill_table_3.field_2"}],
                [{"from": "fill_table_3.field_3"}, {"from": "fill_table_3.field_4"}],
            ],
        )
        self._cursor_gap(self.BLOCK_GAP_LG)

        self.draw_text(c, self.content.get("text_block_6", ""))
        self._cursor_gap(self.BLOCK_GAP_XXL)
        self.draw_signature_block(c, gap_between_lines=40.0)
        self.draw_bottom_company_footer(c)

        c.showPage()
        self._cursor_reset()
        self.draw_text(c, self.content.get("header_3", ""), font_size=self.FONT_SIZE_HEADER_2)
        self._cursor_gap(self.BLOCK_GAP_MD)
        self.draw_text(c, self.content.get("text_block_7", ""))
        self._cursor_gap(self.BLOCK_GAP_LG + 10.0)
        self.draw_interest_tables_headers(c)
        self._cursor_gap(0.0)
        self.draw_interest_tables_rows(c)

        framed_text = self.content.get("text_block_8", "")
        needed_h = (self.BLOCK_GAP_LG + 5.0) + self._measure_text_height(
            framed_text,
            self.FONT_SIZE_TEXT,
            max(self.content_width - 12.0, 1),
        ) + 12.0
        self._ensure_space(c, needed_h)
        self._cursor_gap(self.BLOCK_GAP_LG + 5.0)
        self.draw_framed_text(c, framed_text)

        c.save()
        return ContractPdfBuildResult(
            pdf_bytes=buffer.getvalue(),
            filename=f"FleXXLager-Vertrag-IN{self.contract.id}.pdf",
        )


def build_contract_pdf(contract_id: int) -> ContractPdfBuildResult:
    creator = ContractPdfCreator(contract_id)
    return creator.build()
