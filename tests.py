#!/usr/bin/env python3
import datetime
import unittest

import moexapi


class Tickers(unittest.TestCase):
    def test_shares(self):
        for ticker in ["SBERP03", "SELG-003D", "MAGN-002D"]:
            moexapi.get_ticker(ticker)

    def test_bonds(self):
        moexapi.get_ticker(secid='RU000A0JXYA7', market=moexapi.Markets.BONDS)

    def test_isin(self):
        moexapi.get_ticker("RU000A1039N1")
        lkoh1 = moexapi.get_ticker("LKOH")
        lkoh2 = moexapi.get_ticker("RU0009024277")
        self.assertEqual(lkoh1.isin, lkoh2.isin)

    def test_etfs(self):
        for ticker in ["CNYM"]:
            moexapi.get_ticker(ticker)

    def test_gold(self):
        self.assertEqual(moexapi.get_ticker("GOLD").currency, "RUB")

    def test_old(self):
        self.assertEqual(moexapi.get_ticker("RU0009029540").secid, "SBER")


class Candles(unittest.TestCase):
    def test_index(self):
        ticker = moexapi.get_ticker("IMOEX")
        candles = moexapi.get_candles(
            ticker,
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 1, 31),
        )
        history = moexapi.get_history(
            ticker,
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 1, 31),
        )
        self.assertGreater(len(candles), 0)
        self.assertGreater(len(history), 0)
        moexapi.get_ticker("RVI")

    def test_share(self):
        for ticker in ["GAZP", "SBERP", "MSRS"]:
            ticker = moexapi.get_ticker(ticker)
            candles = moexapi.get_candles(
                ticker,
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 31),
            )
            history = moexapi.get_history(
                ticker,
                start_date=datetime.date(2023, 1, 1),
                end_date=datetime.date(2023, 1, 31),
            )
            self.assertGreater(len(candles), 0)
            self.assertGreater(len(history), 0)

    def test_currency(self):
        ticker = moexapi.get_ticker("CNY")
        candles = moexapi.get_candles(
            ticker,
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 1, 31),
        )
        history = moexapi.get_history(
            ticker,
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 1, 31),
        )
        self.assertGreater(len(candles), 0)
        self.assertGreater(len(history), 0)

    def test_midprice(self):
        ticker = moexapi.get_ticker('SU26229RMFS3')
        history = moexapi.get_history(ticker, start_date=datetime.date(2019, 6, 5), end_date=datetime.date(2019, 6, 5))
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0].mid_price, 97.865)


class Dividends(unittest.TestCase):
    def test_dividends(self):
        for ticker in ["CHMF", "MOEX", "SFIN"]:
            ticker = moexapi.get_ticker(ticker, market=moexapi.Markets.SHARES)
            dividends = moexapi.get_dividends(ticker)
            self.assertGreater(len(dividends), 0)


class Bonds(unittest.TestCase):
    def test_bonds(self):
        bond = moexapi.Bond(moexapi.get_ticker("ОФЗ26238", market=moexapi.Markets.BONDS))
        self.assertEqual(bond.issue_date, datetime.date(2021, 6, 16))
        self.assertEqual(bond.mat_date, datetime.date(2041, 5, 15))
        self.assertEqual(bond.early_repayment, False)
        self.assertEqual(bond.evening_session, True)
        self.assertAlmostEqual(bond.coupon_percent, 7.1)
        self.assertEqual(bond.coupon_frequency, 2)
        moexapi.Bond(moexapi.get_ticker(secid='BYM000002402', market=moexapi.Markets.BONDS))
        bond = moexapi.Bond(moexapi.get_ticker(secid='RU000A10A8E8', market=moexapi.Markets.BONDS))
        self.assertEqual(bond.amortization[0].value, 0.005)


class Splits(unittest.TestCase):
    def test_splits(self):
        ticker = moexapi.get_ticker("RSHU")
        splits = moexapi.get_ticker_splits(ticker)
        self.assertEqual(len(splits), 1)
        split = splits[0]
        self.assertEqual(split.date, datetime.date(2021, 4, 12))
        self.assertEqual(split.secid, "VTBU")
        self.assertAlmostEqual(split.mult, 40.0)


if __name__ == '__main__':
    unittest.main()
