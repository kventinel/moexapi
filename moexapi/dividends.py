import dataclasses
import datetime

from . import history
from . import tickers
from . import utils


@dataclasses.dataclass
class Dividend:
    date: datetime.date
    value: float
    part: float


Dividends = list[Dividend]


def get_dividends(ticker: tickers.Ticker) -> Dividends:
    resp = utils.json_api_call(f"https://iss.moex.com/iss/securities/{ticker.secid}/dividends.json")['dividends']
    columns = resp['columns']
    data = resp['data']
    dividends: Dividends = []
    for line in data:
        date = datetime.date.fromisoformat(line[columns.index('registryclosedate')])
        if date > datetime.date.today() + datetime.timedelta(days=365):
            continue
        value = line[columns.index('value')]
        price = history.get_history(ticker, start_date=date, end_date=date + datetime.timedelta(days=5))
        assert len(price) >= 1
        dividends.append(Dividend(date=date, value=value, part=value / price[0].close))
    return dividends
