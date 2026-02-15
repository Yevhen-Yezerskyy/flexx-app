# FILE: web/flexx/contract_helpers.py  (обновлено — 2026-02-16)
# PURPOSE: Helpers для контрактов: генерация таблицы Stückzinsen по day-count 30/360 (US/Bond Basis) + пометки выходных/праздников (holidays).

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
    """
    30/360 US (Bond Basis):
      - If d1 is 31 -> set d1=30
      - If d2 is 31 and d1 is 30 or 31 -> set d2=30
      - If d1 is last day of Feb -> set d1=30
      - If d2 is last day of Feb and d1 is 30 or last day of Feb -> set d2=30
    """
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


def build_stueckzinsen_rows(
    *,
    start_date: date,
    end_date: date,
    interest_rate_percent: Decimal,
    decimals: int = 6,
    holiday_country: str = "DE",
    holiday_subdiv: str | None = None,
) -> list[StueckzinsRow]:
    """
    Stückzinsen по 30/360 US:
      stueckzins = day_count_30_360_us(start, d) * (rate/100) / 360
    Период: start_date <= d < end_date   (end_date ИСКЛЮЧЕН)
    """
    if end_date <= start_date:
        return []

    de_holidays = holidays.country_holidays(holiday_country, subdiv=holiday_subdiv)
    rate = interest_rate_percent / Decimal("100")
    denom = Decimal("360")

    rows: list[StueckzinsRow] = []
    d = start_date
    while d < end_date:  # ← было <=, теперь исключаем последний день
        dc = _day_count_30_360_us(start_date, d)
        st = (Decimal(dc) * rate) / denom

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


def build_stueckzinsen_rows_for_issue(
    *,
    issue_date: date,
    term_months: int,
    interest_rate_percent: Decimal,
    decimals: int = 6,
    holiday_country: str = "DE",
    holiday_subdiv: str | None = None,
) -> list[StueckzinsRow]:
    end_date = _add_months(issue_date, int(term_months))
    return build_stueckzinsen_rows(
        start_date=issue_date,
        end_date=end_date,
        interest_rate_percent=interest_rate_percent,
        decimals=decimals,
        holiday_country=holiday_country,
        holiday_subdiv=holiday_subdiv,
    )
