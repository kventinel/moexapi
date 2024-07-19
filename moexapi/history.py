import typing as T

import copy
import dataclasses
import datetime

from . import changeover
from . import markets
from . import splits
from . import tickers
from . import utils


@dataclasses.dataclass
class History:
    """
    Candle for given ticker and date

    date -- date of candle
    low -- lowest price of the day
    high -- highest price of the day
    open -- open price of the day
    close -- close price of the day
    mid_price -- weighted average price of the day
    numtrades -- number of trades for the day
    volume -- number of shares/bonds/currencies sold on the day
    value -- sum of all transactions in RUB for the day
    """
    date: datetime.date
    low: float
    high: float
    open: float
    close: float
    mid_price: T.Optional[float]
    numtrades: T.Optional[int]
    volume: T.Optional[int]
    value: T.Optional[float]

    @classmethod
    def merge(cls, first: 'History', second: 'History'):
        assert first.date == second.date
        return cls(
            date=first.date,
            low=min(first.low, second.low),
            high=max(first.high, second.high),
            open=(first.open + second.open) / 2,
            close=(first.close + second.close) / 2,
            mid_price=(first.mid_price + second.mid_price) / 2,
            numtrades=first.numtrades + second.numtrades,
            volume=first.volume + second.volume,
            value=first.value + second.value,
        )
    
    def mult(self, mult: float) -> None:
        self.low *= mult
        self.high *= mult
        self.open *= mult
        self.close *= mult
        self.mid_price *= mult
        self.value *= mult


def _merge_history(first: list[History], second: list[History]) -> list[History]:
    i = 0
    j = 0
    result: list[History] = []
    while i < len(first) and j < len(second):
        if first[i].date == second[j].date:
            result.append(History.merge(first[i], second[j]))
            i += 1
            j += 1
        elif first[i].date < second[j].date:
            result.append(first[i])
            i += 1
        else:
            result.append(second[j])
            j += 1
    if i < len(first):
        result.extend(first[i:])
    if j < len(second):
        result.extend(second[j:])
    return result


def _merge_history_list(candles: list[list[History]]) -> list[History]:
    result = candles[0]
    for idx in range(1, len(candles)):
        result = _merge_history(result, candles[idx])
    return result


def _parse_history_one_board(
    ticker: tickers.Ticker,
    board: str,
    start_date: T.Optional[datetime.date] = None,
    end_date: T.Optional[datetime.date] = None,
) -> list[History]:
    result = []
    while True:
        start_str = f"from={start_date.isoformat()}" if start_date else ""
        end_str = f"from={end_date.isoformat()}" if end_date else ""
        query = f"?{start_str}&{end_str}"
        response = utils.json_api_call(
            f"https://iss.moex.com/iss/history{ticker.market.path}/boards/{board}/"
            f"securities/{ticker.secid}.json{query}"
        )
        history = utils.prepare_dict(response, "history")
        for line in history:
            date = datetime.date.fromisoformat(line["TRADEDATE"])
            start_date = date + datetime.timedelta(days=1)
            low = line["LOW"]
            high = line["HIGH"]
            open = line["OPEN"]
            close = line["CLOSE"]
            if low is None or high is None or open is None or close is None:
                continue
            if low == 0.0 or high == 0.0 or open == 0.0 or close == 0.0:
                continue
            value = line.get("VALUE")
            if ticker.market == markets.Markets.CURRENCY:
                value = line.get("VOLRUR")
            result.append(
                History(
                    date=date,
                    low=low,
                    high=high,
                    open=open,
                    close=close,
                    mid_price=line.get("WAPRICE"),
                    numtrades=line.get("NUMTRADES"),
                    volume=line.get("VOLUME"),
                    value=value,
                )
            )
        if len(history) == 0:
            break
    return result


def _parse_history(
    ticker: tickers.Ticker,
    start_date: T.Optional[datetime.date] = None,
    end_date: T.Optional[datetime.date] = None,
):
    candles = []
    boards = ticker.market.candle_boards if ticker.market.candle_boards else ticker.boards
    for board in boards:
        candles.append(_parse_history_one_board(ticker, board, start_date=start_date, end_date=end_date))
    return _merge_history_list(candles)


def get_history(
    ticker: tickers.Ticker,
    start_date: T.Optional[datetime.date] = None,
    end_date: T.Optional[datetime.date] = None,
):
    ticker = copy.deepcopy(ticker)
    prev_names = changeover.get_prev_names(ticker.secid)
    ticker_splits = [split for split in splits.get_splits() if split.secid in prev_names]
    candles = []
    for name in prev_names:
        ticker.secid = name
        candles.append(_parse_history(ticker, start_date=start_date, end_date=end_date))
    result = _merge_history_list(candles)
    for split in ticker_splits:
        for candle in result:
            if candle.date < split.date:
                candle.mult(1 / split.mult)
    return result
