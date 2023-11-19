import typing as T

import bs4
import requests

from . import markets
from . import tickers


def get_moex_rate(currency: str) -> T.Optional[float]:
    return tickers.get_ticker(currency, market=markets.Markets.CURRENCY).price


def get_cbrf_rate(currency: str) -> float:
    if currency == "RUB":
        return 1.0
    resp = requests.get(
        "https://www.cbr.ru/currency_base/daily",
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/15.3 Safari/605.1.15"
        },
    )
    assert resp.status_code == 200, "Can't parse echange rate from cbrf"
    soup = bs4.BeautifulSoup(resp.text, features="lxml")
    tables = soup.find_all("table")
    assert len(tables) == 1
    rows = tables[0].find_all("tr")
    for row in rows[1:]:
        cols = [ch.text for ch in row.find_all("td")]
        if cols[1] == currency:
            result = float(cols[4].replace(",", ".")) / int(cols[2])
            return result
    raise RuntimeError(f"Unknown currency {currency}")


def get_rate(currency: str) -> float:
    moex_rate = get_moex_rate(currency)
    if moex_rate is not None:
        return moex_rate
    return get_cbrf_rate(currency)
