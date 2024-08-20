import dataclasses
import datetime

from . import changeover
from . import splits
from . import tickers
from . import utils


@dataclasses.dataclass
class Dividend:
    date: datetime.date
    value: float


Dividends = list[Dividend]


def _get_dividends_for_one_ticker(ticker: tickers.Ticker):
    resp = utils.json_api_call(f"https://iss.moex.com/iss/securities/{ticker.secid}/dividends.json")['dividends']
    columns = resp['columns']
    data = resp['data']
    dividends: Dividends = []
    for line in data:
        date = datetime.date.fromisoformat(line[columns.index('registryclosedate')])
        if date > datetime.date.today():
            continue
        dividends.append(Dividend(date=date, value=line[columns.index('value')]))
    return dividends


def get_dividends(ticker: tickers.Ticker) -> Dividends:
    ticker = changeover.get_current_ticker(ticker)
    prev_tickers = changeover.get_prev_tickers(ticker)
    dividends = []
    for ticker in prev_tickers:
        dividends.extend(_get_dividends_for_one_ticker(ticker))
    ticker_splits = [split for split in splits.get_splits() if split.secid in [t.secid for t in prev_tickers]]
    for split in ticker_splits:
        for dividend in dividends:
            if dividend.date < split.date:
                dividend.value /= split.mult
    return dividends
