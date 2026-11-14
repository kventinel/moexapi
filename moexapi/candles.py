import typing as T

import concurrent.futures
import dataclasses
import datetime

import numpy as np

from . import changeover
from . import markets
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
    value -- sum of all transactions in currency for the day
    currency -- currency of transaction value
    """
    start: datetime.datetime
    end: datetime.datetime
    low: float
    high: float
    open: float
    close: float
    volume: T.Optional[int]
    value: T.Optional[float]
    currency: T.Optional[str] = None

    @classmethod
    def merge(cls, first: 'Candle', second: 'Candle'):
        assert first.currency == second.currency, "Can't merge candles in different currencies"
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
            currency=first.currency,
        )

    def mult(self, mult: float) -> None:
        self.low *= mult
        self.high *= mult
        self.open *= mult
        self.close *= mult
        if self.volume is not None:
            self.volume /= mult


def _merge_candles(
    first: list[Candle], second: list[Candle], preferred_currency: T.Optional[str] = None,
) -> list[Candle]:
    preferred_currency = tickers._sur_to_rub(preferred_currency)
    i = 0
    j = 0
    result: list[Candle] = []
    while i < len(first) and j < len(second):
        if first[i].end <= second[j].start:
            result.append(first[i])
            i += 1
        elif second[j].end <= first[i].start:
            result.append(second[j])
            j += 1
        else:
            if first[i].currency == second[j].currency:
                result.append(Candle.merge(first[i], second[j]))
            elif second[j].currency == preferred_currency:
                result.append(second[j])
            elif first[i].currency == preferred_currency:
                result.append(first[i])
            else:
                raise ValueError(
                    f"Can't select candle currency at {first[i].start}: "
                    f"{first[i].currency} and {second[j].currency}; "
                    f"preferred currency is {preferred_currency}"
                )
            i += 1
            j += 1
    if i < len(first):
        result.extend(first[i:])
    if j < len(second):
        result.extend(second[j:])
    return result


def _merge_candles_list(
    candles: list[list[Candle]], preferred_currency: T.Optional[str] = None,
) -> list[Candle]:
    if len(candles) == 0:
        return []
    result = candles[0]
    for idx in range(1, len(candles)):
        result = _merge_candles(result, candles[idx], preferred_currency)
    return result


def _parse_candles_one_board(
    ticker: tickers.Ticker,
    board: str,
    start_date: T.Optional[T.Union[datetime.datetime, str]] = None,
    end_date: T.Optional[T.Union[datetime.datetime, str]] = None,
    interval: T.Optional[int] = None,
) -> list[Candle]:
    result = []
    if isinstance(start_date, str):
        start_date = datetime.datetime.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = datetime.datetime.fromisoformat(end_date)
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
                    currency=tickers._sur_to_rub(ticker.currency),
                )
            )
        if len(candles) == 0:
            break
    return result


def _parse_candles(
    ticker: tickers.Ticker,
    start_date: T.Optional[T.Union[datetime.datetime, str]] = None,
    end_date: T.Optional[T.Union[datetime.datetime, str]] = None,
    interval: T.Optional[int] = None,
):
    candles = []
    for board in ticker.boards:
        candles.append(
            _parse_candles_one_board(ticker, board, start_date=start_date, end_date=end_date, interval=interval)
        )
    return _merge_candles_list(candles, ticker.currency)


def _split_price_factor(original, adjusted):
    """Return a whole-number OHLC adjustment confirmed by all four prices."""
    original = np.array([original.open, original.low, original.high, original.close], dtype=float)
    adjusted = np.array([adjusted.open, adjusted.low, adjusted.high, adjusted.close], dtype=float)
    if (not np.isfinite(original).all() or not np.isfinite(adjusted).all()
            or np.any(original <= 0) or np.any(adjusted <= 0)):
        return 1.0
    ratios = original / adjusted
    factor = float(ratios[0])
    if not np.allclose(ratios, factor, rtol=1e-8, atol=0):
        return 1.0
    magnitude = factor if factor >= 1 else 1 / factor
    if magnitude < 2 or not np.isclose(magnitude, round(magnitude), rtol=1e-8, atol=0):
        return 1.0
    return float(round(magnitude)) if factor >= 1 else 1 / round(magnitude)


def _adjust_candle_splits(ticker, candles, actions, interval):
    affected = [c for c in candles if any(c.end.date() < s.date for s in actions)]
    if not affected:
        return
    price_factors = {}
    if markets.Markets.EQUITY.has(ticker.market):
        # Import here because history also uses the raw candle parser.
        from . import history

        start = min(c.start.date() for c in affected)
        end = max(c.end.date() for c in affected)
        original = history._parse_history(ticker, start_date=start, end_date=end)
        daily = candles if interval == 24 else _parse_candles(
            ticker, start_date=start.isoformat(), end_date=end.isoformat(), interval=24,
        )
        by_date = {c.start.date(): c for c in daily}
        for row in original:
            reference = by_date.get(row.date)
            if reference is not None and row.currency == reference.currency:
                price_factors[row.date] = _split_price_factor(row, reference)
    for candle in affected:
        known = 1.0
        for action in actions:
            if candle.end.date() < action.date:
                known *= action.mult
        dates = (candle.start.date() + datetime.timedelta(days=offset)
                 for offset in range((candle.end.date() - candle.start.date()).days + 1))
        factors = [price_factors[date] for date in dates if date in price_factors]
        applied = factors[0] if factors and all(f == factors[0] for f in factors) else 1.0
        # ISS can adjust candle prices while leaving volume in original units.
        # Undo the price adjustment already present before applying known splits.
        volume = candle.volume
        candle.mult(applied / known)
        candle.volume = volume * known if volume is not None else None


def get_candles(
    ticker: tickers.Ticker,
    start_date: T.Optional[T.Union[datetime.datetime, datetime.date, str]] = None,
    end_date: T.Optional[T.Union[datetime.datetime, datetime.date, str]] = None,
    interval: T.Optional[int] = None,
):
    ticker = changeover.get_current_ticker(ticker)
    prev_tickers = changeover.get_prev_tickers(ticker)
    ticker_splits = [split for split in splits.get_splits() if split.secid in [t.secid for t in prev_tickers]]
    candles = []
    for t in prev_tickers:
        series = _parse_candles(t, start_date=start_date, end_date=end_date, interval=interval)
        _adjust_candle_splits(t, series, ticker_splits, interval)
        candles.append(series)
    return _merge_candles_list(candles, ticker.currency)


def get_candles_batch(
    ticker_list: list[tickers.Ticker],
    start_date: T.Optional[T.Union[datetime.datetime, datetime.date, str]] = None,
    end_date: T.Optional[T.Union[datetime.datetime, datetime.date, str]] = None,
    interval: T.Optional[int] = None,
    max_workers: T.Optional[int] = None,
) -> list[list[Candle]]:
    """Load candles for multiple tickers concurrently, keyed by SECID."""
    def load(ticker: tickers.Ticker) -> tuple[str, list[Candle]]:
        return get_candles(
            ticker,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(load, ticker_list))
