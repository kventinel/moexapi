import dataclasses
import datetime

from . import tickers
from . import utils


logger = utils.initialize_logging(__file__)


@dataclasses.dataclass
class Changeover:
    date: datetime.date
    old_secid: str
    new_secid: str

    def __lt__(self, other: "Changeover"):
        return self.date < other.date


def get_changeovers() -> list[Changeover]:
    """Return changeovers in sorted by date order"""
    result = []
    response = utils.json_api_call(
        "https://iss.moex.com/iss/history/engines/stock/markets/shares/securities/changeover.json"
    )
    changeover = utils.prepare_dict(response, "changeover")
    for line in changeover:
        result.append(
            Changeover(
                date=datetime.date.fromisoformat(line["action_date"]),
                old_secid=line["old_secid"],
                new_secid=line["new_secid"],
            )
        )
    result.append(
        Changeover(date=datetime.date(2023, 9, 20), old_secid="SFTL", new_secid="SOFL"),
    )
    return sorted(result)


def get_prev_tickers(ticker: tickers.Ticker) -> list[tickers.Ticker]:
    changeovers = get_changeovers()[::-1]
    result = [ticker]
    for line in changeovers:
        if line.new_secid == result[-1].secid:
            try:
                result.insert(0, tickers.get_ticker(line.old_secid, market=ticker.market))
            except tickers.NotFindTicker as ex:
                logger.warning(f"Can't find old version {ex.ticker} for {ticker}")
    return result


def get_current_ticker(ticker: tickers.Ticker) -> tickers.Ticker:
    changeovers = get_changeovers()
    for line in changeovers:
        if ticker.secid == line.old_secid:
            ticker = tickers.get_ticker(line.new_secid, market=ticker.market)
    if ticker.secid in ["RSTI", "RSTIP"]:
        ticker.get_ticker("FEES", market=ticker.market)
    return ticker
