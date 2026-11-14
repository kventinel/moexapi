import dataclasses
import datetime

from . import changeover
from . import smartlab
from . import tickers


@dataclasses.dataclass
class Dividend:
    date: datetime.date
    value: float


Dividends = list[Dividend]


def get_dividends(ticker: tickers.Ticker) -> Dividends:
    """Get public Smart-Lab dividends in current-share units.

    Dates are shareholder record dates and amounts are already restated after
    splits. Missing or malformed source pages raise errors.
    """
    ticker = changeover.get_current_ticker(ticker)
    prev_tickers = changeover.get_prev_tickers(ticker)
    secids = {ticker.secid, *(previous.secid for previous in prev_tickers)}
    return [Dividend(date=payment.date, value=payment.value)
            for payment in smartlab.get_dividends(secids)]
