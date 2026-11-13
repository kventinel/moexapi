import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from moexapi import Markets, candles, history, splits


SPLIT_DATE = datetime.date(2020, 3, 24)


def split_response(rows=()):
    return {'splits': {'columns': ['tradedate', 'secid', 'before', 'after'],
                       'data': list(rows)}}


def daily(item, factor=1):
    return candles.Candle(
        datetime.datetime.combine(item.date, datetime.time()),
        datetime.datetime.combine(item.date, datetime.time(23, 59, 59)),
        item.low / factor, item.high / factor,
        item.open / factor, item.close / factor, item.volume, item.value, 'RUB',
    )


def test_no_hardcoded_fund_split():
    with patch.object(splits.utils, 'json_api_call', return_value=split_response()):
        actions = splits.get_splits()
    assert all(s.secid != 'VTBM' for s in actions)
    assert actions == [splits.Split(datetime.date(2014, 12, 30), 'IRAO', 0.01)]


@pytest.mark.parametrize('reported', [False, True])
@pytest.mark.parametrize('requested_secid', ['VTBM', 'LQDT'])
def test_history_uses_iss_adjusted_prices_without_duplicate_split(reported, requested_secid):
    old = SimpleNamespace(secid='VTBM', market=Markets.ETFS)
    current = SimpleNamespace(secid='LQDT', market=Markets.ETFS)
    requested = old if requested_secid == 'VTBM' else current
    before = history.History(datetime.date(2020, 3, 17), 1008.3, 1008.8,
                             1008.3, 1008.8, 1008.8, 66, 3585, 3615818.5, 'RUB')
    on_date = history.History(SPLIT_DATE, 1.0083, 1.0085, 1.0084,
                              1.0085, 1.0084, 19, 146, 147.22, 'RUB')
    after = history.History(datetime.date(2022, 7, 22), 1.16, 1.17, 1.16,
                            1.17, 1.165, 100, 1000, 1165, 'RUB')
    reference = [[daily(before, 1000), daily(on_date)], [daily(after)]]
    rows = [['2020-03-24', 'VTBM', 1, 1000]] if reported else []
    with (
        patch.object(history.changeover, 'get_current_ticker', return_value=current),
        patch.object(history.changeover, 'get_prev_tickers', return_value=[old, current]),
        patch.object(splits.utils, 'json_api_call', return_value=split_response(rows)),
        patch.object(history, '_parse_history', side_effect=[[before, on_date], [after]]),
        patch.object(history.candles_api, '_parse_candles', side_effect=reference),
    ):
        actual = history.get_history(requested)
    assert [c.date for c in actual] == [before.date, SPLIT_DATE, after.date]
    assert [getattr(actual[0], f) for f in ['low', 'high', 'open', 'close', 'mid_price']] == pytest.approx(
        [1.0083, 1.0088, 1.0083, 1.0088, 1.0088])
    assert actual[0].volume == 3585000
    assert actual[0].value == 3615818.5
    assert actual[0].numtrades == 66
    assert actual[1].mid_price == 1.0084
    assert actual[1].volume == 146
    assert actual[2].mid_price == 1.165
    assert actual[2].volume == 1000


@pytest.mark.parametrize('factor', [2, 1000, 0.01])
def test_generic_security_and_range_entirely_before_split(factor):
    ticker = SimpleNamespace(secid='OTHER', market=Markets.SHARES)
    item = history.History(datetime.date(2020, 1, 20), 90, 110, 100, 105,
                           102, 10, 20, 2040, 'RUB')
    with patch.object(history.candles_api, '_parse_candles', return_value=[daily(item, factor)]):
        history._adjust_unreported_splits(ticker, [item], [])
    assert item.close == pytest.approx(105 / factor)
    assert item.mid_price == pytest.approx(102 / factor)
    assert item.volume == pytest.approx(20 * factor)
    assert item.value == 2040


@pytest.mark.parametrize('case', ['no_data', 'different_ohlc', 'not_integer', 'raw_prices'])
def test_no_adjustment_without_matching_iss_evidence(case):
    ticker = SimpleNamespace(secid='OTHER', market=Markets.ETFS)
    item = history.History(datetime.date(2020, 1, 20), 90, 110, 100, 105,
                           102, 10, 20, 2040, 'RUB')
    reference = daily(item, 1 if case == 'raw_prices' else 2.3 if case == 'not_integer' else 1000)
    if case == 'different_ohlc':
        reference.high *= 1.01
    with patch.object(history.candles_api, '_parse_candles', return_value=[] if case == 'no_data' else [reference]):
        history._adjust_unreported_splits(ticker, [item], [])
    assert item.close == 105
    assert item.volume == 20


def test_known_and_unreported_split_factors_compose():
    ticker = SimpleNamespace(secid='OTHER', market=Markets.ETFS)
    item = history.History(datetime.date(2020, 1, 20), 90, 110, 100, 105,
                           102, 10, 20, 2040, 'RUB')
    reported = [splits.Split(SPLIT_DATE, 'OTHER', 10)]
    with patch.object(history.candles_api, '_parse_candles', return_value=[daily(item, 1000)]):
        history._adjust_unreported_splits(ticker, [item], reported)
    item.mult(1 / reported[0].mult)
    assert item.close == pytest.approx(105 / 1000)
    assert item.volume == 20000
