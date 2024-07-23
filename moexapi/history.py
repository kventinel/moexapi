import typing as T

import copy
import dataclasses
import datetime

import numpy as np

from . import changeover
from . import markets
from . import splits
from . import tickers
from . import utils


def _maybe_sum(first, second):
    if first is None and second is None:
        return None
    return sum([item for item in [first, second] if item is not None])


def _maybe_mean(first, second):
    if first is None and second is None:
        return None
    return np.mean([item for item in [first, second] if item is not None])


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
    mid_price: float
    numtrades: int
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
            mid_price=_maybe_mean(first.mid_price, second.mid_price),
            numtrades=first.numtrades + second.numtrades,
            volume=_maybe_sum(first.volume, second.volume),
            value=_maybe_sum(first.value, second.value),
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


def _parse_history(
    ticker: tickers.Ticker,
    start_date: T.Optional[datetime.date] = None,
    end_date: T.Optional[datetime.date] = None,
) -> list[History]:
    result: list[History] = []
    prev_date = start_date
    while True:
        start_str = f"from={start_date.isoformat()}" if start_date else ""
        end_str = f"till={end_date.isoformat()}" if end_date else ""
        query = f"?{start_str}&{end_str}"
        url = f"https://iss.moex.com/iss/history{ticker.market.path}/securities/{ticker.secid}.json{query}"
        response = utils.json_api_call(url)
        history = utils.prepare_dict(response, "history")
        boards = []
        for line in history:
            date = datetime.date.fromisoformat(line["TRADEDATE"])
            start_date = date
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
            item = History(
                date=date,
                low=low,
                high=high,
                open=open,
                close=close,
                mid_price=line.get('WAPRICE') or np.mean([low, high, open, close]),
                numtrades=line.get("NUMTRADES") or 0,
                volume=line.get("VOLUME"),
                value=value,
            )
            board = line["BOARDID"]
            if len(result) > 0 and result[-1].date == date:
                if board in boards:
                    continue
                boards.append(board)
                result[-1] = History.merge(result[-1], item)
            else:
                boards = [board]
                result.append(item)
        if prev_date == start_date:
            break
        prev_date = start_date
    return result


def get_history(
    ticker: tickers.Ticker,
    start_date: T.Optional[datetime.date] = None,
    end_date: T.Optional[datetime.date] = None,
):
    ticker = changeover.get_current_ticker(ticker)
    prev_tickers = changeover.get_prev_tickers(ticker)
    ticker_splits = [split for split in splits.get_splits() if split.secid in [t.secid for t in prev_tickers]]
    candles = []
    for t in prev_tickers:
        candles.append(_parse_history(t, start_date=start_date, end_date=end_date))
    result = _merge_history_list(candles)
    for split in ticker_splits:
        for candle in result:
            if candle.date < split.date:
                candle.mult(1 / split.mult)
    return result
