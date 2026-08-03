#!/usr/bin/env python3
import datetime
import unittest
from unittest import mock

import moexapi


class Tickers(unittest.TestCase):
    def test_shares(self):
        for ticker in ["SBERP03", "SELG-003D", "MAGN-002D", "RU0008913751"]:
            moexapi.get_ticker(ticker)
        for ticker in ["GAZP", "SBERP", "OKEY"]:
            moexapi.get_ticker(ticker, market=moexapi.Markets.SHARES)
        with self.assertRaises(moexapi.NotFindTicker):
            moexapi.get_ticker("TMOS", market=moexapi.Markets.SHARES)

    def test_bonds(self):
        moexapi.get_ticker(secid='RU000A0JXYA7', market=moexapi.Markets.BONDS)

    def test_isin(self):
        moexapi.get_ticker("RU000A1039N1")
        lkoh1 = moexapi.get_ticker("LKOH")
        lkoh2 = moexapi.get_ticker("RU0009024277")
        self.assertEqual(lkoh1.isin, lkoh2.isin)

    def test_etfs(self):
        moexapi.get_ticker("CNYM", market=moexapi.Markets.ETFS)
        tmos = moexapi.get_ticker("TMOS", market=moexapi.Markets.ETFS)
        self.assertIn("TQTF", tmos.boards)
        tickers = moexapi.get_tickers(
            market=moexapi.Markets.ETFS,
            is_traded=True,
            limit=2,
        )
        self.assertEqual(len(tickers), 2)

    def test_gold(self):
        self.assertEqual(moexapi.get_ticker("GOLD").currency, "RUB")

    def test_old(self):
        self.assertEqual(moexapi.get_ticker("RU0009029540").secid, "SBER")

    def test_listing_trade_status_has_priority(self):
        listing = moexapi.Listing(
            secid="RU0009029540",
            market=moexapi.Markets.SHARES,
            shortname="Сбербанк",
            isin="RU0009029540",
            board="EQBR",
            is_traded=False,
        )
        info = moexapi.TickerInfo(
            is_traded=True,
            shortname="Сбербанк",
            isin="RU0009029540",
            subtype=None,
            listlevel=1,
        )
        with (
            mock.patch.object(moexapi.TickerInfo, "from_secid", return_value=info),
            mock.patch.object(moexapi.TickerBoardInfo, "from_secid", return_value=None),
        ):
            ticker = moexapi.Ticker.from_listing(listing)
        self.assertFalse(ticker.is_traded)

    def test_inactive_market_boards_are_saved(self):
        market_response = {
            "securities": {
                "columns": ["BOARDID", "PREVPRICE", "CURRENCYID", "LISTLEVEL"],
                "data": [["TQBR", 100, "SUR", 1]],
            },
            "marketdata": {
                "columns": ["LAST", "VALTODAY"],
                "data": [[101, 1000]],
            },
        }
        boards_response = {
            "boards": {
                "columns": ["secid", "boardid", "engine", "market", "is_traded"],
                "data": [
                    ["TMOS", "TQBR", "stock", "shares", 1],
                    ["TMOS", "TQTF", "stock", "shares", 0],
                    ["TMOS", "RPEU", "stock", "repo", 1],
                ],
            },
        }
        with mock.patch(
            "moexapi.tickers.utils.json_api_call",
            side_effect=[market_response, boards_response],
        ):
            info = moexapi.TickerBoardInfo.from_secid(
                "TMOS",
                moexapi.Markets.ETFS,
                "TQBR",
            )
        self.assertEqual(info.boards, ["TQBR", "TQTF"])


class Candles(unittest.TestCase):
    def test_batch(self):
        tickers = [mock.Mock(secid="AAA"), mock.Mock(secid="BBB")]
        with mock.patch(
            "moexapi.candles.get_candles",
            side_effect=lambda ticker, **_: [ticker.secid],
        ) as get_candles:
            result = moexapi.get_candles_batch(
                tickers,
                start_date=datetime.date(2024, 1, 1),
                end_date=datetime.date(2024, 1, 31),
                interval=24,
                max_workers=2,
            )
        self.assertEqual(result, [["AAA"], ["BBB"]])
        self.assertEqual(get_candles.call_count, 2)

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
        moexapi.Bond(moexapi.get_ticker(secid='SU52002RMFS1', market=moexapi.Markets.BONDS))
        moexapi.Bond(moexapi.get_ticker(secid='SU26218RMFS6', market=moexapi.Markets.BONDS))


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
