import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from moexapi import Dividend, Markets, get_dividends


@pytest.mark.parametrize("market", [Markets.SHARES, Markets.ETFS])
def test_equity_dividends_use_smartlab(market):
    ticker = SimpleNamespace(secid="TEST", market=market)
    payment = SimpleNamespace(date=datetime.date(2024, 7, 11), value=33.3)
    with (
        patch('moexapi.dividends.changeover.get_current_ticker', return_value=ticker),
        patch('moexapi.dividends.changeover.get_prev_tickers', return_value=[ticker]),
        patch('moexapi.dividends.smartlab.get_dividends', return_value=[payment]) as load,
        patch('moexapi.utils.json_api_call') as iss,
    ):
        assert get_dividends(ticker) == [Dividend(payment.date, 33.3)]
    load.assert_called_once_with({'TEST'})
    iss.assert_not_called()
