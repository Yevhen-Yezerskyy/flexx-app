# FILE: web/flexx/pdf_contract.py  (обновлено — 2026-02-16)
# PURPOSE: Генерация PDF “Zeichnungsschein”: аккуратный layout без лишних вертикальных отступов,
#          единый _draw_wrapped_banking (абзацы + одинарные переносы), блок Käufer/Zeichner без “дыры” перед таблицей.

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import re

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from flexx.contract_helpers import build_stueckzinsen_rows_for_issue
from flexx.models import Contract


@dataclass(frozen=True)
class ContractPdfBuildResult:
    pdf_bytes: bytes
    filename: str


@dataclass(frozen=True)
class CalcBankingLayout:
    calc_top_pad: float = 16.0
    calc_line_h: float = 22.0
    calc_bottom_pad: float = 12.0

    x_sign: float = 18.0
    x_val: float = 58.0
    x_eur: float = 138.0
    x_text: float = 188.0

    banking_x_pad: float = 10.0
    banking_top_gap: float = 14.0
    banking_bottom_pad: float = 10.0

    table_stroke: float = 0.7
    after_block_gap: float = 10.0
    banking_leading: float = 10.8
    banking_para_mult: float = 1.4


CALC_BANKING_LAYOUT = CalcBankingLayout()



# --- helpers ---

def _t(issue_contract: dict, key: str) -> str:
    return _normalize_db_text(issue_contract.get(key) or "")


def _normalize_db_text(text: str) -> str:
    txt = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not txt:
        return ""
    txt = "\n".join(line.strip() for line in txt.split("\n"))
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt


def _db_cell_text(value) -> str:
    return _normalize_db_text(value).replace("\n", " ")


def _fmt_ddmmyyyy_no_sep(d: date | None) -> str:
    return d.strftime("%d%m%Y") if d else ""


def _draw_wrapped(
    c: Canvas,
    *,
    x: float,
    y_top: float,
    width: float,
    text: str,
    font: str = "Helvetica",
    font_size: float = 10,
    leading: float | None = None,
) -> float:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.strip() for p in text.split("\n")]

    c.setFont(font, font_size)
    lead = leading if leading is not None else (font_size + 2)

    def measure(s: str) -> float:
        return c.stringWidth(s, font, font_size)

    y = y_top
    for p in paragraphs:
        if not p:
            y -= lead
            continue
        words = p.split()
        cur = ""
        for w in words:
            cand = (cur + " " + w).strip()
            if measure(cand) <= width:
                cur = cand
            else:
                if cur:
                    c.drawString(x, y, cur)
                    y -= lead
                cur = w
        if cur:
            c.drawString(x, y, cur)
            y -= lead
    return y


def _draw_db_text(
    c: Canvas,
    *,
    x: float,
    y_top: float,
    width: float,
    text: str,
    font_size: float = 10.0,
    leading: float = 10.8,
    para_mult: float = 1.4,
) -> float:
    """
    DB text renderer:
    - trims all edges
    - single \n keeps manual line break
    - double \n makes paragraph gap via para_mult
    - **text** renders bold inline
    """
    normalized = _normalize_db_text(text)
    if not normalized:
        return y_top

    parts = normalized.split("\n\n")

    def measure(s: str, bold: bool) -> float:
        return c.stringWidth(s, "Helvetica-Bold" if bold else "Helvetica", font_size)

    y = y_top
    drew_any = False
    for pi, part in enumerate(parts):
        lines = part.split("\n")
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue

            segments: list[tuple[str, bool]] = []
            for i, seg in enumerate(ln.split("**")):
                if not seg:
                    continue
                segments.append((seg, i % 2 == 1))

            cur: list[tuple[str, bool]] = []
            cur_w = 0.0
            for seg_text, is_bold in segments:
                for word in seg_text.split():
                    token = f"{word} "
                    token_w = measure(token, is_bold)
                    if cur and (cur_w + token_w > width):
                        cx = x
                        for t, b in cur:
                            c.setFont("Helvetica-Bold" if b else "Helvetica", font_size)
                            c.drawString(cx, y, t)
                            cx += measure(t, b)
                        y -= leading
                        cur = []
                        cur_w = 0.0
                    cur.append((token, is_bold))
                    cur_w += token_w

            if cur:
                cx = x
                for t, b in cur:
                    c.setFont("Helvetica-Bold" if b else "Helvetica", font_size)
                    c.drawString(cx, y, t)
                    cx += measure(t, b)
                y -= leading
                drew_any = True

        if pi != len(parts) - 1:
            y -= leading * (para_mult - 1.0)

    if drew_any:
        y += leading

    return y


def _rect(c: Canvas, x: float, y: float, w: float, h: float, lw: float = 0.7) -> None:
    c.setLineWidth(lw)
    c.rect(x, y, w, h, stroke=1, fill=0)


def _draw_type1_table(
    c: Canvas,
    *,
    x: float,
    y_top: float,
    w: float,
    row_h: float,
    row_splits: list[list[float]],
    labels: list[list[str]],
    values: list[list[str]],
    label_font: float = 6.0,
    label_y_pad: float = 7.0,
    value_font: float = 10.0,
    value_y_pad: float = 7.0,
) -> tuple[float, float]:
    table_top = y_top

    for row_idx, splits in enumerate(row_splits):
        row_y = table_top - ((row_idx + 1) * row_h)
        _rect(c, x, row_y, w, row_h)

        c.setLineWidth(0.7)
        run = 0.0
        for s in splits[:-1]:
            run += s
            vx = x + (w * run)
            c.line(vx, row_y, vx, row_y + row_h)

    c.setFont("Helvetica", label_font)
    for row_idx, row_labels in enumerate(labels):
        row_y = table_top - ((row_idx + 1) * row_h)
        run = 0.0
        for col_idx, txt in enumerate(row_labels):
            cell_x = x + (w * run)
            c.drawString(cell_x + 6, row_y + row_h - label_y_pad, txt)
            run += row_splits[row_idx][col_idx]

    c.setFont("Helvetica", value_font)
    for row_idx, row_values in enumerate(values):
        row_y = table_top - ((row_idx + 1) * row_h)
        run = 0.0
        for col_idx, txt in enumerate(row_values):
            cell_x = x + (w * run)
            c.drawString(cell_x + 6, row_y + value_y_pad, txt)
            run += row_splits[row_idx][col_idx]

    table_bottom = table_top - (len(row_splits) * row_h)
    return table_top, table_bottom


def _draw_framed_text_block(
    c: Canvas,
    *,
    x: float,
    y_top: float,
    w: float,
    header: str,
    body: str,
    header_font: str = "Helvetica-Bold",
    header_size: float = 9.0,
    body_font: str = "Helvetica",
    body_size: float = 9.0,
    content_pad_x: float = 8.0,
    header_top_pad: float = 15.0,
    header_body_gap: float = 15.0,
    body_leading: float = 11.0,
    bottom_pad: float = 8.0,
    border_lw: float = 0.9,
) -> tuple[float, float, float, float]:
    c.setFont(header_font, header_size)
    c.drawString(x + content_pad_x, y_top - header_top_pad, header)

    body_y_end = _draw_db_text(
        c,
        x=x + content_pad_x,
        y_top=y_top - header_top_pad - header_body_gap,
        width=w - (content_pad_x * 2),
        text=body,
        font_size=body_size,
        leading=body_leading,
        para_mult=1.4,
    )
    y_bottom = body_y_end - bottom_pad
    h = y_top - y_bottom
    _rect(c, x, y_bottom, w, h, lw=border_lw)
    return x, y_bottom, w, h


# --- draw parts (page 1) ---

def draw_top_box(
    c: Canvas,
    *,
    page_h: float,
    issue_contract: dict,
    left: float | None = None,
    width: float | None = None,
) -> tuple[float, float, float, float]:
    x = 55 if left is None else left
    w = (A4[0] * (2 / 3)) if width is None else width
    y_top = page_h - 50
    return _draw_framed_text_block(
        c,
        x=x,
        y_top=y_top,
        w=w,
        header="Bitte vollständig ausgefüllt und unterzeichnet zurücksenden an:",
        body=_t(issue_contract, "unternehmen_emittent"),
        header_font="Helvetica-Bold",
        header_size=9,
        body_font="Helvetica",
        body_size=9,
        content_pad_x=8,
        header_top_pad=15,
        header_body_gap=15,
        body_leading=11,
        bottom_pad=8,
        border_lw=0.7,
    )


def draw_title_block(c: Canvas, *, left: float, y_top: float) -> float:
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, y_top, "Zeichnungsschein / Wertpapierkaufantrag")
    return y_top - 20


def draw_emission_block(c: Canvas, *, left: float, y_top: float, width: float, issue_contract: dict) -> float:
    y_after = _draw_db_text(
        c,
        x=left,
        y_top=y_top,
        width=width,
        text=_t(issue_contract, "ueberschrift_emission"),
        font_size=11,
        leading=13,
        para_mult=1.4,
    )
    return y_after - 10


def draw_kaufer_label(c: Canvas, *, left: float, y_top: float) -> float:
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y_top, "Käufer / Zeichner:")
    return y_top - 6  # было -14 (это и давало “дыру”)


def draw_kaufer_table(
    c: Canvas,
    *,
    x: float,
    y_top: float,
    w: float,
    client,
) -> tuple[float, float]:
    row_h = 26
    row_splits = [
        [0.30, 0.35, 0.35],
        [1.0],
        [0.60, 0.40],
        [1 / 3, 1 / 3, 1 / 3],
        [1 / 3, 1 / 3, 1 / 3],
    ]
    labels = [
        ["Name", "Vorname", "Geburtsdatum (TTMMJJJJ)"],
        ["Firma"],
        ["Straße, Hausnummer", "PLZ, Ort"],
        ["Telefon", "Fax-Nr.", "E-Mail"],
        ["Nur bei Firmen: Handelsregister", "Handelsregister-Nummer", "Ansprechpartner"],
    ]
    values = [
        [
            _db_cell_text(client.last_name or ""),
            _db_cell_text(client.first_name or ""),
            _fmt_ddmmyyyy_no_sep(getattr(client, "birth_date", None)),
        ],
        [_db_cell_text(getattr(client, "company", "") or "")],
        [
            _db_cell_text(getattr(client, "street", "") or ""),
            f"{_db_cell_text(getattr(client, 'zip_code', '') or '')} {_db_cell_text(getattr(client, 'city', '') or '')}".strip(),
        ],
        [
            _db_cell_text(getattr(client, "phone", "") or ""),
            _db_cell_text(getattr(client, "fax", "") or ""),
            _db_cell_text(getattr(client, "email", "") or ""),
        ],
        [
            _db_cell_text(getattr(client, "handelsregister", "") or ""),
            _db_cell_text(getattr(client, "handelsregister_number", "") or ""),
            _db_cell_text(getattr(client, "contact_person", "") or ""),
        ],
    ]
    return _draw_type1_table(
        c,
        x=x,
        y_top=y_top,
        w=w,
        row_h=row_h,
        row_splits=row_splits,
        labels=labels,
        values=values,
        label_font=6.0,
        label_y_pad=7.2,
        value_font=10.0,
        value_y_pad=7.0,
    )


def draw_text_zwischen_1(c: Canvas, *, left: float, y_top: float, width: float, issue_contract: dict) -> float:
    return _draw_db_text(
        c,
        x=left,
        y_top=y_top,
        width=width,
        text=_t(issue_contract, "text_zwischen_1"),
        font_size=10,
        leading=12,
        para_mult=1.4,
    )


def draw_calc_and_banking_block(
    c: Canvas,
    *,
    left: float,
    y_top: float,
    width: float,
    contract: Contract,
    issue_contract: dict,
) -> float:
    cfg = CALC_BANKING_LAYOUT
    box_x = left

    def _fmt_6(v: Decimal | None) -> str:
        if v is None:
            return ""
        return f"{v.quantize(Decimal('0.000001'))}".replace(".", ",")

    def _fmt_2(v: Decimal | None) -> str:
        if v is None:
            return ""
        return f"{v.quantize(Decimal('0.01'))}".replace(".", ",")

    nominal = getattr(contract, "nominal_amount", None)
    total = getattr(contract, "nominal_amount_plus_percent", None)
    qty = getattr(contract, "bonds_quantity", None)

    nominal = Decimal(nominal) if nominal is not None else None
    total = Decimal(total) if total is not None else None

    st_total = (total - nominal) if (total is not None and nominal is not None) else None
    per_bond_st = (st_total / Decimal(qty)) if (st_total is not None and qty) else None
    per_bond_total = (Decimal("1.00") + per_bond_st) if per_bond_st is not None else None

    calc_top = y_top - cfg.calc_top_pad
    line_h = cfg.calc_line_h

    x_sign = box_x + cfg.x_sign
    x_val = box_x + cfg.x_val
    x_eur = box_x + cfg.x_eur
    x_text = box_x + cfg.x_text

    num_font = 10
    eur_font = 10

    def row(sign: str, value: str, text: str, *, y: float) -> None:
        c.setFont("Helvetica", 10)
        c.drawString(x_sign, y, sign)

        c.setFont("Helvetica-Bold", num_font)
        if value:
            c.drawString(x_val, y, value)

        c.setFont("Helvetica-Bold", eur_font)
        c.drawString(x_eur, y, "EUR")

        c.setFont("Helvetica", 10)
        c.drawString(x_text, y, text)

    y = calc_top
    row("", "1,00", "Ausgabebetrag (Ausgabekurs 100%)", y=y)

    y -= line_h
    row("+", _fmt_6(per_bond_st), "Stückzinsen gemäß Stückzinstabelle zum Tag der Zeichnung**", y=y)
    c.setLineWidth(0.7)
    c.line(x_val, y - 6, x_eur - 8, y - 6)

    y -= line_h
    row("=", _fmt_6(per_bond_total), "Ausgabepreis/Kaufpreis pro Inhaber-Teilschuldverschreibung**", y=y)

    y -= line_h
    c.setFont("Helvetica", 10)
    c.drawString(x_sign, y, "x")
    c.setFont("Helvetica-Bold", num_font)
    if qty:
        c.drawString(x_val, y, str(qty))
        c.setLineWidth(0.7)
        c.line(x_val, y - 6, x_eur - 8, y - 6)

    c.setFont("Helvetica", 10)
    c.drawString(x_text, y, "Stückzahl (mindestens fünftausend (5.000) Inhaber-Teil")
    c.drawString(x_text, y - 12, "schuldverschreibungen i.H.v.  EUR 1,00)")

    y -= (line_h + 8)
    c.setFont("Helvetica", 10)
    c.drawString(x_sign, y, "=")

    c.setFont("Helvetica-Bold", num_font)
    if total is not None:
        c.drawString(x_val, y, _fmt_2(total))

    c.setFont("Helvetica-Bold", eur_font)
    c.drawString(x_eur, y, "EUR")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x_text, y, "Gesamtbetrag (Kaufsumme)")

    calc_bottom_y = y - cfg.calc_bottom_pad

    # banking
    bank_text = _t(issue_contract, "banking")
    bank_text_bottom = _draw_db_text(
        c,
        x=box_x + cfg.banking_x_pad,
        y_top=calc_bottom_y - cfg.banking_top_gap,
        width=width - (cfg.banking_x_pad * 2),
        text=bank_text,
        font_size=10,
        leading=cfg.banking_leading,
        para_mult=cfg.banking_para_mult,
    )
    box_bottom_y = bank_text_bottom - cfg.banking_bottom_pad

    # Two stacked frames with shared border (calc bottom == banking top).
    _rect(c, box_x, calc_bottom_y, width, y_top - calc_bottom_y, lw=cfg.table_stroke)
    _rect(c, box_x, box_bottom_y, width, calc_bottom_y - box_bottom_y, lw=cfg.table_stroke)

    return box_bottom_y - cfg.after_block_gap


def draw_footnotes_after_calc(
    c: Canvas,
    *,
    left: float,
    y_top: float,
    width: float,
    issue,
) -> float:
    c.setFont("Helvetica", 7.0)

    d = getattr(issue, "interest_start_date", None) or getattr(issue, "issue_date", None) or getattr(issue, "start_date", None)
    date_str = d.strftime("%d. %B %Y") if d else ""

    text = (
        "* Es besteht kein Anspruch auf Zuteilung.\n"
        f"** Gerundet. Stückzinsen fallen bei einer Zeichnung ab dem {date_str} an.\n"
        "Die Emittentin ist berechtigt, sofern der angeforderte Einzahlungsbetrag nicht innerhalb der benannten Frist eingeht, "
        "weitere Stückzinsen bis zum Tag des vollständigen Zahlungseingangs zu berechnen."
    )

    return _draw_wrapped(
        c,
        x=left,
        y_top=y_top,
        width=width,
        text=text,
        font="Helvetica",
        font_size=7.0,
        leading=9.0,
    )


def draw_text_zwischen_2(
    c: Canvas,
    *,
    left: float,
    y_top: float,
    width: float,
    issue_contract: dict,
) -> float:
    return _draw_db_text(
        c,
        x=left,
        y_top=y_top,
        width=width,
        text=_t(issue_contract, "text_zwischen_2"),
        font_size=10.0,
        leading=12.0,
        para_mult=1.4,
    )


def draw_depot_intro(
    c: Canvas,
    *,
    left: float,
    y_top: float,
    width: float,
) -> float:
    text = "Die Inhaber-Teilschuldverschreibungen sollen in nachfolgendes Depot eingebucht werden:"
    return _draw_wrapped(
        c,
        x=left,
        y_top=y_top,
        width=width,
        text=text,
        font="Helvetica",
        font_size=10.0,
        leading=12.0,
    )


def draw_depot_block(
    c: Canvas,
    *,
    left: float,
    y_top: float,
    width: float,
    client,
) -> float:
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y_top, "Depot-Informationen des Käufers / Zeichners:")

    depot_holder = f"{_db_cell_text(client.first_name or '')} {_db_cell_text(client.last_name or '')}".strip()
    _, table_bottom = _draw_type1_table(
        c,
        x=left,
        y_top=y_top - 4,
        w=width,
        row_h=24,
        row_splits=[[0.5, 0.5], [0.5, 0.5]],
        labels=[
            ["Depotinhaber (Vorname, Name)", "Depot-IBAN"],
            ["Bank/Kreditinstitut", "BIC"],
        ],
        values=[
            [depot_holder, _db_cell_text(getattr(client, "bank_depo_iban", "") or "")],
            [_db_cell_text(getattr(client, "bank_depo_name", "") or ""), _db_cell_text(getattr(client, "bank_depo_bic", "") or "")],
        ],
        label_font=6.0,
        label_y_pad=7.0,
        value_font=10.0,
        value_y_pad=6.0,
    )
    return table_bottom - 8

def draw_page2_refund_intro(c: Canvas, *, left: float, y_top: float, width: float) -> float:
    text = (
        "Im Falle der Kürzung oder Ablehnung von Zeichnungen soll die zu viel gezahlte Kaufsumme "
        "durch Überweisung auf das nachfolgend benannte Konto erstattet werden:"
    )
    return _draw_wrapped(
        c,
        x=left,
        y_top=y_top,
        width=width,
        text=text,
        font="Helvetica",
        font_size=10.0,
        leading=12.0,
    )

# FILE: web/flexx/pdf_contract.py  (обновлено — 2026-02-16)
# PURPOSE: Page2: блок "Konto-Informationen des Käufers / Zeichners" (как depot, но bank_* клиента).

def draw_konto_block(
    c: Canvas,
    *,
    left: float,
    y_top: float,
    width: float,
    client,
) -> float:
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y_top, "Konto-Informationen des Käufers / Zeichners:")

    holder = f"{_db_cell_text(client.first_name or '')} {_db_cell_text(client.last_name or '')}".strip()
    _, table_bottom = _draw_type1_table(
        c,
        x=left,
        y_top=y_top - 4,
        w=width,
        row_h=24,
        row_splits=[[0.5, 0.5], [0.5, 0.5]],
        labels=[
            ["Kontoinhaber (Vorname, Name)", "IBAN"],
            ["Bank/Kreditinstitut", "BIC"],
        ],
        values=[
            [holder, _db_cell_text(getattr(client, "bank_iban", "") or "")],
            [_db_cell_text(getattr(client, "bank_name", "") or ""), _db_cell_text(getattr(client, "bank_bic", "") or "")],
        ],
        label_font=6.0,
        label_y_pad=7.0,
        value_font=10.0,
        value_y_pad=6.0,
    )
    return table_bottom - 8

def draw_text_zwischen_3(
    c: Canvas,
    *,
    left: float,
    y_top: float,
    width: float,
    issue_contract: dict,
) -> float:
    text = _t(issue_contract, "text_zwischen_3")

    return _draw_db_text(
        c,
        x=left,
        y_top=y_top,
        width=width,
        text=text,
        font_size=9.0,
        leading=12.0,
        para_mult=1.3,
    )


def draw_page2_signature_block(
    c: Canvas,
    *,
    left: float,
    y_top: float,
    width: float,
) -> float:
    # геометрия
    col_gap = 30
    col_w = (width - col_gap) / 2
    x_l = left
    x_r = left + col_w + col_gap

    # 1) верхние линии
    y = y_top
    c.setLineWidth(0.8)
    c.line(x_l, y, x_l + col_w, y)
    c.line(x_r, y, x_r + col_w, y)

    # labels
    c.setFont("Helvetica", 8.0)
    c.drawString(x_l, y - 12, "Ort, Datum")
    c.drawString(x_r, y - 12, "Unterschrift des Käufers / Zeichners")

    # 2) второй “ряд” (служебный)
    y2 = y - 32
    c.setLineWidth(0.8)
    c.line(x_r, y2, x_r + col_w, y2)

    c.setFont("Helvetica", 8.0)
    c.drawString(x_l, y2 - 12, "(nur von der FleXXLager GmbH & Co. KG auszufüllen)")

    # 3) строка про Zeichnung in Höhe von ...
    y3 = y2 - 26
    c.setFont("Helvetica", 9.0)
    c.drawString(x_l, y3, "Zeichnung in Höhe von")
    c.setLineWidth(0.7)
    c.line(x_l + 92, y3 - 2, x_l + 92 + 150, y3 - 2)
    c.drawString(x_l + 92 + 155, y3, "Inhaber-Teilschuldverschreibungen angenommen.")

    # 4) Siegen, den ...  и линия справа + подпись компании
    y4 = y3 - 22
    c.setFont("Helvetica", 9.0)
    c.drawString(x_l, y4, "Siegen, den")
    c.setLineWidth(0.7)
    c.line(x_l + 58, y4 - 2, x_l + 58 + 90, y4 - 2)

    c.setLineWidth(0.7)
    c.line(x_r, y4 + 6, x_r + col_w * 0.55, y4 + 6)

    c.setFont("Helvetica", 9.0)
    c.drawString(x_r, y4 - 6, "FleXXLager GmbH & Co. KG")

    return y4 - 10


def _split_rows_by_year(rows: list) -> list[dict]:
    if not rows:
        return []

    start = rows[0].pay_date
    end = rows[-1].pay_date

    if (end - start).days < 365:
        return [{"label": "", "rows": rows}]

    groups = []
    cur = start
    idx = 0

    while cur <= end:
        seg_start = cur
        seg_end = min(end, (cur + relativedelta(years=1)) - timedelta(days=1))

        seg_rows = []
        while idx < len(rows):
            d = rows[idx].pay_date
            if d < seg_start:
                idx += 1
                continue
            if d > seg_end:
                break
            seg_rows.append(rows[idx])
            idx += 1

        groups.append({"label": f"{seg_start:%d.%m.%Y} - {seg_end:%d.%m.%Y}", "rows": seg_rows})
        cur = seg_end + timedelta(days=1)

    return groups


def _draw_interest_header(c: Canvas, *, left: float, y_top: float, width: float, issue) -> float:
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, y_top, "Stückzinstabelle")

    c.setFont("Helvetica", 9)
    sub = f"{issue.title} · EUR {issue.bond_price} · {issue.issue_date:%d.%m.%Y}"
    c.drawString(left, y_top - 14, sub)
    return y_top - 26


def _fmt_date_short(d: date) -> str:
    return d.strftime("%d.%m.%y")


def _draw_one_interest_table(
    c: Canvas,
    *,
    x: float,
    y_top: float,
    w: float,
    rows: list,
    bond_price,
    today: date,
) -> float:
    header_h = 28
    row_h = 12
    col1 = w * 0.52
    col2 = w - col1

    h = header_h + (len(rows) * row_h)
    y_bottom = y_top - h

    _rect(c, x, y_bottom, w, h, lw=0.7)

    c.setLineWidth(0.7)
    c.line(x + col1, y_top - header_h, x + col1, y_top)
    c.line(x, y_top - header_h, x + w, y_top - header_h)

    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(
        x + col1 / 2,
        y_top - 10,
        f"Stückzinsen je Teilschuld- verschreibung zu EUR {bond_price} in EUR",
    )
    c.drawCentredString(x + col1 + col2 / 2, y_top - 14, "Datum der Einzahlung")

    c.setFont("Helvetica", 7.5)
    y = y_top - header_h
    for r in rows:
        y -= row_h

        if r.pay_date < today:
            c.setFillColor(colors.Color(0.95, 0.95, 0.95))
            c.rect(x, y, w, row_h, stroke=0, fill=1)
        elif r.is_holiday:
            c.setFillColor(colors.Color(1.0, 0.90, 0.90))
            c.rect(x, y, w, row_h, stroke=0, fill=1)
        elif r.is_weekend:
            c.setFillColor(colors.Color(1.0, 0.97, 0.85))
            c.rect(x, y, w, row_h, stroke=0, fill=1)

        c.setFillColor(colors.black)

        c.setLineWidth(0.7)
        c.line(x + col1, y, x + col1, y + row_h)
        c.line(x, y, x + w, y)

        c.drawCentredString(x + col1 / 2, y + 3, r.stueckzins_de)
        c.drawCentredString(x + col1 + col2 / 2, y + 3, _fmt_date_short(r.pay_date))

    return y_bottom - 10


def draw_interest_table_pages(c: Canvas, *, issue, left: float, content_w: float) -> None:
    rows = build_stueckzinsen_rows_for_issue(
        issue_date=issue.issue_date,
        term_months=issue.term_months,
        interest_rate_percent=issue.interest_rate,
        nominal_value=issue.bond_price,
        decimals=6,
        holiday_country="DE",
        holiday_subdiv=None,
    )
    rows = sorted(rows, key=lambda r: r.pay_date)

    raw_groups = _split_rows_by_year(rows)
    today = timezone.localdate()

    _, page_h = A4
    y = page_h - 70
    y = _draw_interest_header(c, left=left, y_top=y, width=content_w, issue=issue)

    gap = 12
    table_w = (content_w - (gap * 2)) / 3

    for g in raw_groups:
        rws = g["rows"]
        n = len(rws)
        per_col = (n + 2) // 3 if n else 0
        cols = [rws[i * per_col:(i + 1) * per_col] for i in range(3)] if per_col else [[], [], []]

        label_h = 16 if g["label"] else 0

        header_h = 28
        row_h = 12
        max_rows = max(len(cols[0]), len(cols[1]), len(cols[2]))
        need_h = label_h + header_h + (max_rows * row_h) + 16

        if y - need_h < 70:
            c.showPage()
            y = page_h - 70
            y = _draw_interest_header(c, left=left, y_top=y, width=content_w, issue=issue)

        if g["label"]:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(left, y, g["label"])
            y -= 14

        x1 = left
        x2 = left + table_w + gap
        x3 = left + (table_w + gap) * 2

        y_bottoms = [
            _draw_one_interest_table(c, x=x1, y_top=y, w=table_w, rows=cols[0], bond_price=issue.bond_price, today=today),
            _draw_one_interest_table(c, x=x2, y_top=y, w=table_w, rows=cols[1], bond_price=issue.bond_price, today=today),
            _draw_one_interest_table(c, x=x3, y_top=y, w=table_w, rows=cols[2], bond_price=issue.bond_price, today=today),
        ]

        y = min(y_bottoms) - 10


def build_contract_pdf(contract: Contract) -> ContractPdfBuildResult:
    issue = contract.issue
    client = contract.client
    issue_contract = issue.contract or {}

    buf = BytesIO()
    c = Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # --- PAGE 1 ---

    _, top_box_y, _, _ = draw_top_box(c, page_h=page_h, issue_contract=issue_contract)

    left = 55 * 0.65
    content_w = page_w - (left * 2)

    y = top_box_y - 40

    y = draw_title_block(c, left=left, y_top=y)
    y = draw_emission_block(c, left=left, y_top=y, width=content_w, issue_contract=issue_contract)

    y = draw_kaufer_label(c, left=left, y_top=y)
    _, table_bottom_y = draw_kaufer_table(c, x=left, y_top=y, w=content_w, client=client)

    y = table_bottom_y - 16
    y = draw_text_zwischen_1(c, left=left, y_top=y, width=content_w, issue_contract=issue_contract)

    y = draw_calc_and_banking_block(
        c,
        left=left,
        y_top=y + 5,
        width=content_w,
        contract=contract,
        issue_contract=issue_contract,
    )

    y = draw_footnotes_after_calc(c, left=left, y_top=y, width=content_w, issue=issue)

    y = draw_text_zwischen_2(
        c,
        left=left,
        y_top=y - 8,
        width=content_w,
        issue_contract=issue_contract,
    )

    y = draw_depot_intro(
        c,
        left=left,
        y_top=y - 6,
        width=content_w,
    )

    y = draw_depot_block(
        c,
        left=left,
        y_top=y - 8,
        width=content_w,
        client=client,
    )

    c.showPage()

    # --- PAGE 2 ---
    y = page_h - 90
    y = draw_page2_refund_intro(c, left=left, y_top=y, width=content_w)
    y = draw_konto_block(c, left=left, y_top=y - 10, width=content_w, client=client)
    y = draw_text_zwischen_3(c, left=left, y_top=y - 12, width=content_w, issue_contract=issue_contract)
    draw_page2_signature_block(c, left=left, y_top=120, width=content_w)

    c.showPage()

    # --- PAGE 3+ (Stückzinstabelle) ---
    draw_interest_table_pages(c, issue=issue, left=left, content_w=content_w)

    c.save()

    buf.seek(0)
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"zeichnungschein_contract_{contract.id}_{ts}.pdf"
    return ContractPdfBuildResult(pdf_bytes=buf.read(), filename=filename)
