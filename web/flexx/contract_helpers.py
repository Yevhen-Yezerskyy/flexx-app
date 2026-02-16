# FILE: web/flexx/contract_helpers.py  (обновлено — 2026-02-16)
# PURPOSE: Stückzinsen 30/360 + учёт номинала облигации; банковские дни (выходные+праздники DE) и расчёт суммы договора.

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import calendar

import holidays


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)


def _is_last_day_of_feb(d: date) -> bool:
    return d.month == 2 and d.day == calendar.monthrange(d.year, 2)[1]


def _day_count_30_360_us(d1: date, d2: date) -> int:
    y1, m1, dd1 = d1.year, d1.month, d1.day
    y2, m2, dd2 = d2.year, d2.month, d2.day

    if dd1 == 31:
        dd1 = 30
    if _is_last_day_of_feb(d1):
        dd1 = 30

    if dd2 == 31 and dd1 in (30, 31):
        dd2 = 30
    if _is_last_day_of_feb(d2) and (dd1 == 30 or _is_last_day_of_feb(d1)):
        dd2 = 30

    return 360 * (y2 - y1) + 30 * (m2 - m1) + (dd2 - dd1)


def _fmt_decimal_de(x: Decimal, places: int = 6) -> str:
    q = Decimal("1").scaleb(-places)
    v = x.quantize(q, rounding=ROUND_HALF_UP)
    s = f"{v:.{places}f}"
    return s.replace(".", ",")


@dataclass(frozen=True)
class StueckzinsRow:
    pay_date: date
    stueckzins: Decimal
    stueckzins_de: str
    is_weekend: bool
    is_holiday: bool
    holiday_name: str | None


def build_stueckzinsen_rows_for_issue(
    *,
    issue_date: date,
    term_months: int,
    interest_rate_percent: Decimal,
    nominal_value: Decimal,  # ← НОМИНАЛ ОДНОЙ ОБЛИГАЦИИ
    decimals: int = 6,
    holiday_country: str = "DE",
    holiday_subdiv: str | None = None,
) -> list[StueckzinsRow]:
    """
    Stückzinsen по 30/360 US.
    Расчёт:
        day_count * (rate/100) / 360 * nominal_value
    Период: issue_date <= d < end_date
    """
    end_date = _add_months(issue_date, int(term_months))
    if end_date <= issue_date:
        return []

    de_holidays = holidays.country_holidays(holiday_country, subdiv=holiday_subdiv)
    rate = interest_rate_percent / Decimal("100")
    denom = Decimal("360")

    rows: list[StueckzinsRow] = []
    d = issue_date
    while d < end_date:
        dc = _day_count_30_360_us(issue_date, d)
        st = (Decimal(dc) * rate / denom) * nominal_value

        is_weekend = d.weekday() >= 5
        h_name = de_holidays.get(d)
        is_holiday = h_name is not None

        rows.append(
            StueckzinsRow(
                pay_date=d,
                stueckzins=st,
                stueckzins_de=_fmt_decimal_de(st, places=decimals),
                is_weekend=is_weekend,
                is_holiday=is_holiday,
                holiday_name=str(h_name) if h_name else None,
            )
        )
        d += timedelta(days=1)

    return rows


def is_banking_day(
    d: date,
    *,
    holiday_country: str = "DE",
    holiday_subdiv: str | None = None,
) -> bool:
    if d.weekday() >= 5:
        return False
    de_holidays = holidays.country_holidays(holiday_country, subdiv=holiday_subdiv)
    return de_holidays.get(d) is None


def add_banking_days(
    start: date,
    days: int,
    *,
    holiday_country: str = "DE",
    holiday_subdiv: str | None = None,
) -> date:
    """Добавляет N банковских дней (не считая start)."""
    if days <= 0:
        return start

    de_holidays = holidays.country_holidays(holiday_country, subdiv=holiday_subdiv)
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() >= 5:
            continue
        if de_holidays.get(d) is not None:
            continue
        added += 1
    return d


def calc_contract_amounts_from_stueckzins_table(
    *,
    issue_date: date,
    term_months: int,
    interest_rate_percent: Decimal,
    nominal_value: Decimal,
    sign_date: date,
    quantity: int,
    banking_days_plus: int = 10,
    holiday_country: str = "DE",
    holiday_subdiv: str | None = None,
) -> tuple[date, Decimal, Decimal, Decimal]:
    """
    Возвращает:
      (settlement_date, nominal_amount, accrued_interest, total_amount)
    accrued_interest берётся из Stückzins-Tabelle по settlement_date * quantity.
    """
    settlement_date = add_banking_days(
        sign_date,
        banking_days_plus,
        holiday_country=holiday_country,
        holiday_subdiv=holiday_subdiv,
    )

    qty = Decimal(int(quantity))
    nominal_amount = (nominal_value * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    rows = build_stueckzinsen_rows_for_issue(
        issue_date=issue_date,
        term_months=term_months,
        interest_rate_percent=interest_rate_percent,
        nominal_value=nominal_value,
        decimals=6,
        holiday_country=holiday_country,
        holiday_subdiv=holiday_subdiv,
    )
    st_map = {r.pay_date: r.stueckzins for r in rows}
    st_one = st_map.get(settlement_date, Decimal("0"))

    accrued_interest = (st_one * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_amount = (nominal_amount + accrued_interest).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return settlement_date, nominal_amount, accrued_interest, total_amount
