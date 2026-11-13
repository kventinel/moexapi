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
    # Retain the pre-existing consolidation missing from the ISS split feed.
    irao = Split(date=datetime.date(2014, 12, 30), secid="IRAO", mult=0.01)
    if not any((split.date, split.secid) == (irao.date, irao.secid) for split in result):
        result.insert(0, irao)
    return result


def get_ticker_splits(ticker: tickers.Ticker) -> list[Split]:
    """Return splits for given ticker"""
    ticker = changeover.get_current_ticker(ticker)
    prev_tickers = changeover.get_prev_tickers(ticker)
    return [split for split in get_splits() if split.secid in [t.secid for t in prev_tickers]]
