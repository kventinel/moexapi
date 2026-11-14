import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from moexapi import Markets, history


DAY = datetime.date(2026, 11, 6)


def row(**overrides):
    data = dict(BOARDID='CETS', TRADEDATE=DAY.isoformat(),
                OPEN=10, LOW=9, HIGH=11, CLOSE=10, WAPRICE=10,
                NUMTRADES=7, VOLRUR=1234, VALUE=1234, CURRENCYID='SUR')
    data.update(overrides)
    return data


def parse(rows, market=Markets.CURRENCY):
    columns = sorted(set().union(*(r.keys() for r in rows)))
    response = {'history': {'columns': columns,
                           'data': [[r.get(c) for c in columns] for r in rows]}}
    ticker = SimpleNamespace(secid='TEST', market=market, currency='RUB', boards=[])
    with patch.object(history.utils, 'json_api_call', side_effect=[
            response, {'history': {'columns': [], 'data': []}}]):
        return history._parse_history(ticker, DAY, DAY)


@pytest.mark.parametrize('market', [Markets.CURRENCY, Markets.SHARES, Markets.ETFS])
@pytest.mark.parametrize('volume', ['absent', None, 0, 55])
def test_missing_volume_recovery_preserves_explicit_values(market, volume):
    data = row()
    if volume != 'absent':
        data['VOLUME'] = volume
    [candle] = parse([data], market)
    assert candle.volume == pytest.approx(123.4 if volume in ('absent', None) else volume)
    assert candle.numtrades == 7


@pytest.mark.parametrize('value', [None, -1, float('nan'), float('inf')])
def test_unavailable_or_invalid_turnover_cannot_recover_volume(value):
    assert parse([row(VOLRUR=value)])[0].volume is None


def test_zero_turnover_recovers_zero_volume():
    assert parse([row(VOLRUR=0)])[0].volume == 0


@pytest.mark.parametrize('price', [-10, float('nan'), float('inf')])
def test_invalid_price_cannot_recover_volume(price):
    assert parse([row(WAPRICE=price)])[0].volume is None


def test_recovery_uses_same_historical_day_before_merging_boards():
    next_day = DAY + datetime.timedelta(days=1)
    candles = parse([row(), row(BOARDID='OTHER', WAPRICE=20, VOLRUR=1000),
                     row(TRADEDATE=next_day.isoformat(), WAPRICE=5, VOLRUR=500)])
    assert [c.date for c in candles] == [DAY, next_day]
    assert [c.volume for c in candles] == [173.4, 100]
    candles[0].mult(0.5)
    assert candles[0].volume == 346.8
    assert candles[0].value == 2234


def test_bond_percent_price_is_not_used_as_cash_price():
    assert parse([row()], Markets.FEDERAL_BONDS)[0].volume is None
