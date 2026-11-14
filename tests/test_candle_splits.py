import dataclasses
import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from moexapi import Markets, candles, history, splits


@pytest.mark.parametrize('interval', [24, 60, 7])
@pytest.mark.parametrize('factor,already_adjusted', [(1000, 1000), (3, 1), (0.01, 1), (10, 2)])
@pytest.mark.parametrize('volume', [3585, 0, None])
def test_candle_prices_and_volume_use_separate_split_factors(interval, factor, already_adjusted, volume):
    ticker = SimpleNamespace(secid='TEST', market=Markets.ETFS, currency='RUB')
    day = datetime.date(2020, 3, 17)
    start = datetime.datetime.combine(day, datetime.time())
    raw = history.History(day, 1008.3, 1008.8, 1008.3, 1008.8,
                          1008.8, 66, volume, 3615818.5, 'RUB')
    daily = candles.Candle(start, start.replace(hour=23, minute=59, second=59),
                           raw.low / already_adjusted, raw.high / already_adjusted,
                           raw.open / already_adjusted, raw.close / already_adjusted,
                           volume, raw.value, 'RUB')
    requested = dataclasses.replace(daily)
    if interval == 60:
        requested.start = start.replace(hour=10)
        requested.end = start.replace(hour=10, minute=59, second=59)
        # Intraday OHLC differs from the complete day's OHLC.
        requested.low = requested.open = requested.high = requested.close
    elif interval == 7:
        requested.end += datetime.timedelta(days=3)
    on_date = dataclasses.replace(daily, start=start + datetime.timedelta(days=7),
                                  end=daily.end + datetime.timedelta(days=7))
    expected_prices = [getattr(requested, f) * already_adjusted / factor
                       for f in ('open', 'low', 'high', 'close')]
    actions = [splits.Split(day + datetime.timedelta(days=6), 'TEST', factor)]
    if factor == 10:
        # A second known action with prices adjusted for only the first one.
        actions = [splits.Split(day + datetime.timedelta(days=5), 'TEST', 2),
                   splits.Split(day + datetime.timedelta(days=6), 'TEST', 5)]
    with (
        patch.object(candles.changeover, 'get_current_ticker', return_value=ticker),
        patch.object(candles.changeover, 'get_prev_tickers', return_value=[ticker]),
        patch.object(splits, 'get_splits', return_value=actions),
        patch.object(candles, '_parse_candles', side_effect=[[requested, on_date], [daily]]) as parse,
        patch.object(history, '_parse_history', return_value=[raw]),
    ):
        actual = candles.get_candles(ticker, interval=interval)
    assert [getattr(actual[0], f) for f in ('open', 'low', 'high', 'close')] == pytest.approx(expected_prices)
    assert actual[0].volume == (volume * factor if volume is not None else None)
    assert actual[0].value == raw.value
    assert actual[1] == on_date
    assert parse.call_count == (1 if interval == 24 else 2)


def test_vtbm_prices_stay_adjusted_when_requested_through_lqdt():
    old = SimpleNamespace(secid='VTBM', market=Markets.ETFS, currency='RUB')
    current = SimpleNamespace(secid='LQDT', market=Markets.ETFS, currency='RUB')
    day = datetime.date(2020, 3, 17)
    raw = history.History(day, 1008.3, 1008.8, 1008.3, 1008.8,
                          1008.8, 66, 3585, 3615818.5, 'RUB')
    daily = candles.Candle(datetime.datetime(2020, 3, 17), datetime.datetime(2020, 3, 17, 23, 59, 59),
                           1.0083, 1.0088, 1.0083, 1.0088, 3585, 3615818.5, 'RUB')
    with (
        patch.object(candles.changeover, 'get_current_ticker', return_value=current),
        patch.object(candles.changeover, 'get_prev_tickers', return_value=[old, current]),
        patch.object(splits.utils, 'json_api_call', return_value={'splits': {'columns': [], 'data': []}}),
        patch.object(candles, '_parse_candles', side_effect=[[daily], []]),
        patch.object(history, '_parse_history', return_value=[raw]),
    ):
        [actual] = candles.get_candles(current, interval=24)
    assert actual.close == 1.0088
    assert actual.volume == 3585000
    assert actual.value == 3615818.5


@pytest.mark.parametrize('remote_factor', [0.01, 0.1])
def test_documented_irao_uses_common_duplicate_and_conflict_checks(remote_factor):
    response = {'splits': {'columns': ['tradedate', 'secid', 'before', 'after'],
                            'data': [['2014-12-30', 'IRAO', 1, remote_factor]]}}
    with patch.object(splits.utils, 'json_api_call', return_value=response):
        if remote_factor == 0.01:
            actions = [s for s in splits.get_splits() if s.secid == 'IRAO']
            assert actions == [splits.Split(datetime.date(2014, 12, 30), 'IRAO', 0.01)]
        else:
            with pytest.raises(ValueError, match='Conflicting documented split for IRAO'):
                splits.get_splits()
