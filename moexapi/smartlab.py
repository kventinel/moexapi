"""Public Smart-Lab dividend calendar (no account or API token required)."""

import dataclasses
import datetime
import functools
import math
import re

from bs4 import BeautifulSoup
import requests


DIVIDENDS_URL = "https://smart-lab.ru/dividends/index"
# Calendar years refer to the reporting period, not the payment/record year.
# Read older periods too: retained earnings may be distributed years later.
FIRST_PERIOD_YEAR = 2003


@dataclasses.dataclass(frozen=True)
class Dividend:
    secid: str
    date: datetime.date  # Shareholder record date, not "Купить До" or "Выплата До".
    value: float  # RUB per share, as restated by Smart-Lab after splits.
    period: str = ""


def _header(text: str) -> str:
    return re.sub(r"[\W_]", "", text.casefold())


def _parse_dividends(html: str) -> tuple[Dividend, ...]:
    soup = BeautifulSoup(html, "html.parser")
    required = {"тикер", "период", "дивидендруб", "сд", "датазакрытияреестра"}
    for table in soup.find_all("table"):
        headers = [_header(th.get_text(" ", strip=True)) for th in table.select("thead th")]
        if required.issubset(headers):
            break
    else:
        raise ValueError("Smart-Lab dividend table or required columns are missing")

    columns = {name: headers.index(name) for name in required}
    dividends = []
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        # The calendar ends with a single, spanning navigation/footer cell.
        if len(cells) == 1 and cells[0].has_attr("colspan"):
            continue
        if not cells:
            continue
        if len(cells) != len(headers):
            raise ValueError("Unexpected Smart-Lab dividend row layout")
        # СД is a recommendation marker, never an amount or a date. Its cell
        # can be empty even on approved rows; the row class carries the status.
        if row.select_one(".dividend_canceled") or "dividend_canceled" in row.get("class", []):
            continue
        if "dividend_approved" not in row.get("class", []):
            continue
        secid = cells[columns["тикер"]].get_text(strip=True)
        date_text = cells[columns["датазакрытияреестра"]].get_text(strip=True)
        amount_text = cells[columns["дивидендруб"]].get_text(strip=True)
        try:
            date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            value = float("".join(amount_text.split()).replace(",", "."))
        except ValueError as error:
            raise ValueError(f"Invalid Smart-Lab dividend for {secid}: {date_text}, {amount_text}") from error
        if not secid or not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid Smart-Lab dividend for {secid}: {amount_text}")
        period = cells[columns["период"]].get_text(" ", strip=True)
        dividends.append(Dividend(secid, date, value, period))
    return tuple(dividends)


@functools.lru_cache(maxsize=128)
def _load_year(year: int, as_of: datetime.date) -> tuple[Dividend, ...]:
    # Cache one page per reporting year for all stocks/configs in this process.
    # The date key refreshes the cache if a long-lived process crosses midnight.
    response = requests.get(
        DIVIDENDS_URL,
        params={"is_approved": "1", "year": str(year), "quarter": ""},
        timeout=30,
    )
    response.raise_for_status()
    return _parse_dividends(response.text)


def get_dividends(secids: set[str]) -> list[Dividend]:
    """Return approved, non-cancelled records through today for these tickers.

    Smart-Lab has incomplete coverage, particularly for early reporting years.
    Transport/parser errors propagate; an unavailable page is never cached as
    an empty history. Amounts are already restated; do not split-adjust again.
    """
    today = datetime.date.today()
    # Period pages can overlap. Preserve distinct periods paid on the same day,
    # but discard repeated rows and equivalent old/current ticker aliases.
    result = {}
    for year in range(FIRST_PERIOD_YEAR, today.year + 1):
        for dividend in _load_year(year, today):
            if dividend.secid in secids and dividend.date <= today:
                key = (dividend.date, dividend.period, dividend.value)
                result[key] = dividend
    return sorted(result.values(), key=lambda dividend: dividend.date)
