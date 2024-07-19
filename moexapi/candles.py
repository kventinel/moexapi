import typing as T

import copy
import dataclasses
import datetime

from . import changeover
from . import splits
from . import tickers
from . import utils


@dataclasses.dataclass
class Candle:
    """
    Candle for given ticker

    start -- datetime of candle start
    end -- datetime of candle end
    low -- lowest price of the day
    high -- highest price of the day
    open -- open price of the day
    close -- close price of the day
    volume -- number of shares/bonds/currencies sold on the day
    value -- sum of all transactions in RUB for the day
    """
    start: datetime.datetime
    end: datetime.datetime
    low: float
    high: float
    open: float
    close: float
    volume: T.Optional[int]
    value: T.Optional[float]

    @classmethod
    def merge(cls, first: 'Candle', second: 'Candle'):
        if second.start < first.start:
            start = second.start
            open = second.open
        else:
            start = first.start
            open = first.open
        if second.end < first.end:
            end = first.end
            close = first.close
        else:
            end = second.end
            close = second.close
        return cls(
            start=start,
            end=end,
            low=min(first.low, second.low),
            high=max(first.high, second.high),
            open=open,
            close=close,
            volume=first.volume + second.volume,
            value=first.value + second.value,
        )
    
    def mult(self, mult: float) -> None:
        self.low *= mult
        self.high *= mult
        self.open *= mult
        self.close *= mult
        self.value *= mult


def _merge_candles(first: list[Candle], second: list[Candle]) -> list[Candle]:
    i = 0
    j = 0
    result: list[Candle] = []
    while i < len(first) and j < len(second):
        if first.end <= second.start:
            result.append(first[i])
            i += 1
        elif second.end <= first.start:
            result.append(second[j])
            j += 1
        else:
            result.append(Candle.merge(first[i], second[j]))
            i += 1
            j += 1
    if i < len(first):
        result.extend(first[i:])
    if j < len(second):
        result.extend(second[j:])
    return result


def _merge_candles_list(candles: list[list[Candle]]) -> list[Candle]:
    result = candles[0]
    for idx in range(1, len(candles)):
        result = _merge_candles(result, candles[idx])
    return result


def _parse_candles_one_board(
    ticker: tickers.Ticker,
    board: str,
    start_date: T.Optional[datetime.datetime] = None,
    end_date: T.Optional[datetime.datetime] = None,
    interval: T.Optional[int] = None,
) -> list[Candle]:
    result = []
    while True:
        start_str = f"from={start_date.isoformat()}" if start_date else ""
        end_str = f"till={end_date.isoformat()}" if end_date else ""
        interval_str = f"interval={interval}" if interval else ""
        query = "?" + "&".join([item for item in [start_str, end_str, interval_str] if item])
        response = utils.json_api_call(
            f"https://iss.moex.com/iss{ticker.market.path}/boards/{board}/securities/{ticker.secid}/candles.json{query}"
        )
        candles = utils.prepare_dict(response, "candles")
        for line in candles:
            start = datetime.datetime.fromisoformat(line["begin"])
            end = datetime.datetime.fromisoformat(line["end"])
            start_date = end
            low = line["low"]
            high = line["high"]
            open = line["open"]
            close = line["close"]
            if low is None or high is None or open is None or close is None:
                continue
            if low == 0.0 or high == 0.0 or open == 0.0 or close == 0.0:
                continue
            result.append(
                Candle(
                    start=start,
                    end=end,
                    low=low,
                    high=high,
                    open=open,
                    close=close,
                    volume=line.get("volume"),
                    value=line.get("value"),
                )
            )
        if len(candles) == 0:
            break
    return result


def _parse_candles(
    ticker: tickers.Ticker,
    start_date: T.Optional[datetime.datetime] = None,
    end_date: T.Optional[datetime.datetime] = None,
    interval: T.Optional[int] = None,
):
    candles = []
    boards = ticker.market.candle_boards if ticker.market.candle_boards else ticker.boards
    for board in boards:
        candles.append(
            _parse_candles_one_board(ticker, board, start_date=start_date, end_date=end_date, interval=interval)
        )
    return _merge_candles_list(candles)


def get_candles(
    ticker: tickers.Ticker,
    start_date: T.Optional[datetime.datetime] = None,
    end_date: T.Optional[datetime.datetime] = None,
    interval: T.Optional[int] = None,
):
    ticker = copy.deepcopy(ticker)
    prev_names = changeover.get_prev_names(ticker.secid)
    ticker_splits = [split for split in splits.get_splits() if split.secid in prev_names]
    candles = []
    for name in prev_names:
        ticker.secid = name
        candles.append(_parse_candles(ticker, start_date=start_date, end_date=end_date, interval=interval))
    result = _merge_candles_list(candles)
    for split in ticker_splits:
        for candle in result:
            if candle.end < split.date:
                candle.mult(1 / split.mult)
    return result
