import dataclasses
import datetime

from . import changeover
from . import tickers
from . import utils


@dataclasses.dataclass
class Split:
    date: datetime.date
    secid: str
    mult: float


def get_splits() -> list[Split]:
    """Return all splits on moex"""
    response = utils.json_api_call("https://iss.moex.com/iss/statistics/engines/stock/splits.json")
    splits = utils.prepare_dict(response, "splits")
    result = []
    for line in splits:
        result.append(
            Split(
                date=datetime.date.fromisoformat(line["tradedate"]),
                secid=line["secid"],
                mult=line["after"] / line["before"],
            )
        )
    # Actions absent from the ISS split feed. Keep these for raw candle
    # prices, volume, dividends, and the public split directory.
    documented = [
        Split(date=datetime.date(2014, 12, 30), secid='IRAO', mult=0.01),
        # Issuer announcement and MOEX notice: 1:3 on 2022-10-12.
        # https://www.wimsavings.ru/ru/about/news/138196/
        # https://www.moex.com/n51350/?nt=111
        Split(date=datetime.date(2022, 10, 12), secid='RU000A102N77', mult=3),
        # https://www.moex.com/en/index/vtbmm: effective 2020-03-23,
        # first resumed exchange observation 2020-03-24. LQDT's old code.
        Split(date=datetime.date(2020, 3, 23), secid='VTBM', mult=1000),
    ]
    for documented_split in documented:
        existing = [s for s in result if s.secid == documented_split.secid and s.date == documented_split.date]
        if existing:
            if any(s.mult != documented_split.mult for s in existing):
                raise ValueError(f'Conflicting documented split for {documented_split.secid}')
        else:
            result.append(documented_split)
    return result


def get_ticker_splits(ticker: tickers.Ticker) -> list[Split]:
    """Return splits for given ticker"""
    ticker = changeover.get_current_ticker(ticker)
    prev_tickers = changeover.get_prev_tickers(ticker)
    return [split for split in get_splits() if split.secid in [t.secid for t in prev_tickers]]
