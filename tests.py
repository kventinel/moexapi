#!/usr/bin/env python3
import unittest

import moexapi


class GetCandles(unittest.TestCase):
    def test_index(self):
        ticker = moexapi.get_ticker("IMOEX")
        candles = moexapi.get_candles(ticker)
        history = moexapi.get_history(ticker)
        self.assertGreater(len(candles), 0)
        self.assertGreater(len(history), 0)

    def test_share(self):
        ticker = moexapi.get_ticker("GAZP")
        candles = moexapi.get_candles(ticker)
        history = moexapi.get_history(ticker)
        self.assertGreater(len(candles), 0)
        self.assertGreater(len(history), 0)

    def test_currency(self):
        ticker = moexapi.get_ticker("CNY")
        candles = moexapi.get_candles(ticker)
        history = moexapi.get_history(ticker)
        self.assertGreater(len(candles), 0)
        self.assertGreater(len(history), 0)


if __name__ == '__main__':
    unittest.main()
