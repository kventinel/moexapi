import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from moexapi import Markets, candles, dividends, history, splits


ACTION_DATE = datetime.date(2024, 8, 20)


def split_response(rows=()):
    return {'splits': {'columns': ['tradedate', 'secid', 'before', 'after'],
                       'data': list(rows)}}


@pytest.mark.parametrize('remote_factor', [None, 8, 7])
def test_belu_documented_bonus_is_unique_and_conflicts_fail(remote_factor):
    rows = [] if remote_factor is None else [['2024-08-20', 'BELU', 1, remote_factor]]
    with patch.object(splits.utils, 'json_api_call', return_value=split_response(rows)):
        if remote_factor == 7:
            with pytest.raises(ValueError, match='Conflicting documented split for BELU'):
                splits.get_splits()
        else:
            assert [s for s in splits.get_splits() if s.secid == 'BELU'] == [
                splits.Split(ACTION_DATE, 'BELU', 8),
            ]


@pytest.mark.parametrize('candle_factor', [1, 8])
def test_history_candles_and_dividends_share_belu_units(candle_factor):
    ticker = SimpleNamespace(secid='BELU', market=Markets.SHARES, currency='RUB')
    days = [ACTION_DATE - datetime.timedelta(days=1), ACTION_DATE,
            ACTION_DATE + datetime.timedelta(days=1)]

    def raw_history():
        return [history.History(day, price, price, price, price, price, 2, volume, 8000, 'RUB')
                for day, price, volume in zip(days, [8000, 1000, 1000], [1, 8, 8])]

    def raw_candles():
        result = []
        for row in raw_history():
            price = row.close / candle_factor if row.date < ACTION_DATE else row.close
            start = datetime.datetime.combine(row.date, datetime.time())
            result.append(candles.Candle(start, start.replace(hour=23, minute=59, second=59),
                                         price, price, price, price, row.volume, row.value, 'RUB'))
        return result

    with (
        patch.object(splits.utils, 'json_api_call', return_value=split_response()),
        patch.object(history.changeover, 'get_current_ticker', return_value=ticker),
        patch.object(history.changeover, 'get_prev_tickers', return_value=[ticker]),
        patch.object(history, '_parse_history', side_effect=lambda *a, **kw: raw_history()),
        patch.object(candles, '_parse_candles', side_effect=lambda *a, **kw: raw_candles()),
        patch.object(dividends, '_get_dividends_for_one_ticker',
                     return_value=[dividends.Dividend(days[0], 224),
                                   dividends.Dividend(days[1], 25),
                                   dividends.Dividend(days[2], 26)]),
    ):
        adjusted_history = history.get_history(ticker)
        adjusted_candles = candles.get_candles(ticker, interval=24)
        adjusted_dividends = dividends.get_dividends(ticker)

    for series in (adjusted_history, adjusted_candles):
        for field in ('open', 'low', 'high', 'close'):
            assert [getattr(row, field) for row in series] == [1000, 1000, 1000]
        assert [row.volume for row in series] == [8, 8, 8]
        assert [row.value for row in series] == [8000, 8000, 8000]
    assert [row.mid_price for row in adjusted_history] == [1000, 1000, 1000]
    assert [row.numtrades for row in adjusted_history] == [2, 2, 2]
    assert [payment.value for payment in adjusted_dividends] == [28, 25, 26]
