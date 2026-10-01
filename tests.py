#!/usr/bin/env python3
import datetime
import dataclasses
import unittest
from unittest import mock

import moexapi
from moexapi import history as history_module
from moexapi import candles as candles_module
from moexapi import exchange as exchange_module
from moexapi import tickers as tickers_module


class Tickers(unittest.TestCase):
    def test_empty_index_currency_is_not_resolved_as_currency_ticker(self):
        market_response = {
            "securities": {
                "columns": ["BOARDID", "CURRENCYID", "LISTLEVEL"],
                "data": [["RTSI", "", None]],
            },
            "marketdata": {
                "columns": ["CURRENTVALUE", "VALTODAY"],
                "data": [[1000, 1000000]],
            },
        }
        boards_response = {
            "boards": {
                "columns": ["secid", "boardid", "engine", "market", "currencyid"],
                "data": [["RVI", "RTSI", "stock", "index", ""]],
            },
        }
        with (
            mock.patch(
                "moexapi.tickers.utils.json_api_call",
                side_effect=[market_response, boards_response],
            ),
            mock.patch("moexapi.tickers.exchange.get_rate") as get_rate,
        ):
            info = moexapi.TickerBoardInfo.from_secid(
                "RVI", moexapi.Markets.INDEX, "RTSI"
            )

        self.assertIsNone(info.currency)
        self.assertEqual(info.price, 1000)
        self.assertEqual(info.price_in_rub, 1000)
        get_rate.assert_not_called()

    def test_delisted_ticker_uses_general_board_metadata(self):
        market_response = {
            "securities": {"columns": [], "data": []},
            "marketdata": {"columns": [], "data": []},
        }
        boards_response = {
            "boards": {
                "columns": [
                    "secid", "boardid", "engine", "market", "currencyid"
                ],
                "data": [
                    ["HHRU", "TQBR", "stock", "shares", "RUB"],
                    ["HHRU", "RPEU", "stock", "repo", "USD"],
                ],
            },
        }
        with mock.patch(
            "moexapi.tickers.utils.json_api_call",
            side_effect=[market_response, boards_response],
        ):
            info = moexapi.TickerBoardInfo.from_secid(
                "HHRU",
                moexapi.Markets.SHARES,
                "TQBR",
            )

        self.assertEqual(info.currency, "RUB")
        self.assertEqual(info.boards, ["TQBR"])
        self.assertIsNone(info.price)

    def test_shares(self):
        for ticker in ["SBERP03", "SELG-003D", "MAGN-002D", "RU0008913751"]:
            moexapi.get_ticker(ticker)
        for ticker in ["GAZP", "SBERP", "OKEY"]:
            moexapi.get_ticker(ticker, market=moexapi.Markets.SHARES)
        with self.assertRaises(moexapi.NotFindTicker):
            moexapi.get_ticker("TMOS", market=moexapi.Markets.SHARES)

    def test_bonds(self):
        moexapi.get_ticker(secid='RU000A0JXYA7', market=moexapi.Markets.BONDS)

    def test_bond_type_distinguishes_securities_on_same_board(self):
        tickers_module._parse_tickers.cache_clear()
        self.addCleanup(tickers_module._parse_tickers.cache_clear)
        securities_response = {
            "securities": {
                "columns": [
                    "secid", "shortname", "isin", "is_traded", "type", "primary_boardid",
                ],
                "data": [
                    ["RU000A10DQA8", "ОФЗ 33 CNY", "RU000A10DQA8", 1, "ofz_bond", "TQOY"],
                    ["RU000A1057S2", "Роснфт2P12", "RU000A1057S2", 1, "exchange_bond", "TQOY"],
                ],
            },
        }
        empty_response = {
            "securities": {
                "columns": [
                    "secid", "shortname", "isin", "is_traded", "type", "primary_boardid",
                ],
                "data": [],
            },
        }
        with mock.patch(
            "moexapi.tickers.utils.json_api_call",
            side_effect=[
                securities_response,
                empty_response,
                securities_response,
                empty_response,
            ],
        ):
            listings = tickers_module._parse_tickers(market=moexapi.Markets.BONDS)
            cached_listings = tickers_module._parse_tickers(market=moexapi.Markets.BONDS)

        self.assertIs(listings, cached_listings)

        listings_by_secid = {listing.secid: listing for listing in listings}
        self.assertEqual(
            listings_by_secid["RU000A10DQA8"].market,
            moexapi.Markets.FEDERAL_BONDS,
        )
        self.assertEqual(
            listings_by_secid["RU000A1057S2"].market,
            moexapi.Markets.COMPANY_BONDS,
        )

    def test_isin(self):
        moexapi.get_ticker("RU000A1039N1")
        lkoh1 = moexapi.get_ticker("LKOH")
        lkoh2 = moexapi.get_ticker("RU0009024277")
        self.assertEqual(lkoh1.isin, lkoh2.isin)

    def test_etf_listings_include_historical_open_and_closed_ended_funds(self):
        response = {
            "securities": {
                "columns": ["secid", "shortname", "isin", "primary_boardid",
                            "is_traded", "type"],
                "data": [
                    ["RSTR", "RTS Standard", "RU000A0JQYF0", "EQBR", 0, "public_ppif"],
                    ["FXRB", "FXRB ETF", "IE00B7L7CP77", "TQTF", 0, "etf_ppif"],
                    ["SBMX", "SBMX ETF", "RU000A0ZZH92", "TQTF", 1, "exchange_ppif"],
                    ["RU000A0JQVQ3", "Panoramic Investments", "RU000A0JQVQ3", "EQNE", 0, "private_ppif"],
                    ["INTERVAL", "Interval fund", "INTERVALISIN", "EQBR", 0, "interval_ppif"],
                    ["SHARE", "Ordinary share", "SHAREISIN", "TQBR", 1, "common_share"],
                ],
            },
        }
        empty = {"securities": {"columns": response["securities"]["columns"], "data": []}}
        tickers_module._parse_tickers.cache_clear()
        self.addCleanup(tickers_module._parse_tickers.cache_clear)
        with mock.patch("moexapi.tickers.utils.json_api_call", side_effect=[response, empty]):
            listings = tickers_module._parse_tickers(moexapi.Markets.ETFS)
        self.assertEqual([item.secid for item in listings], ["RSTR", "FXRB", "SBMX", "RU000A0JQVQ3"])
        self.assertEqual(listings[0].board, "EQBR")
        self.assertFalse(listings[0].is_traded)
        self.assertTrue(all(item.market == moexapi.Markets.ETFS for item in listings))

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

    def test_missing_board_listlevel_does_not_warn(self):
        listing = moexapi.Listing(
            secid="TEST",
            market=moexapi.Markets.SHARES,
            shortname="Test security",
            isin="RU0000000000",
            board="TQBR",
            is_traded=True,
        )
        info = moexapi.TickerInfo(
            is_traded=True,
            shortname="Test security",
            isin="RU0000000000",
            subtype=None,
            listlevel=3,
        )
        board_info = moexapi.TickerBoardInfo(
            boards=["TQBR"],
            currency="RUB",
            raw_price=None,
            price=None,
            price_in_rub=None,
            accumulated_coupon=0,
            listlevel=None,
            value=None,
        )
        with (
            mock.patch.object(moexapi.TickerInfo, "from_secid", return_value=info),
            mock.patch.object(moexapi.TickerBoardInfo, "from_secid", return_value=board_info),
            mock.patch.object(tickers_module.logger, "warning") as warning,
        ):
            ticker = moexapi.Ticker.from_listing(listing)

        self.assertEqual(ticker.listlevel, 3)
        warning.assert_not_called()

    def test_inactive_market_boards_are_saved(self):
        market_response = {
            "securities": {
                "columns": ["BOARDID", "PREVPRICE", "CURRENCYID", "LISTLEVEL"],
                "data": [
                    ["TQBR", 100, "SUR", 1],
                    ["TQTY", 10, "CNY", 1],
                ],
            },
            "marketdata": {
                "columns": ["LAST", "VALTODAY"],
                "data": [[101, 1000], [10, 100]],
            },
        }
        boards_response = {
            "boards": {
                "columns": ["secid", "boardid", "engine", "market", "is_traded", "currencyid"],
                "data": [
                    ["TMOS", "TQBR", "stock", "shares", 1, "RUB"],
                    ["TMOS", "TQTF", "stock", "shares", 0, "RUB"],
                    ["TMOS", "TQTY", "stock", "shares", 1, "CNY"],
                    ["TMOS", "RPEU", "stock", "repo", 1, "USD"],
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
    def test_candle_currency_selection(self):
        rub = candles_module.Candle(
            datetime.datetime(2026, 9, 24, 10), datetime.datetime(2026, 9, 24, 11),
            90, 94, 92, 93, 20, 160000, "RUB",
        )
        usd = dataclasses.replace(rub, volume=3, value=2700, currency="USD")
        for first, second in ((rub, usd), (usd, rub)):
            with self.subTest(first=first.currency):
                result = candles_module._merge_candles_list([[first], [second]], "USD")
                self.assertEqual(result, [usd])
                self.assertEqual(
                    candles_module._merge_candles_list([[first], [second]], "SUR"), [rub]
                )
                for preferred in ("EUR", None):
                    with self.assertRaisesRegex(ValueError, "preferred currency is"):
                        candles_module._merge_candles_list([[first], [second]], preferred)
        merged = candles_module._merge_candles_list([[usd], [usd]], "USD")
        self.assertEqual((merged[0].value, merged[0].volume), (5400, 6))
        later = dataclasses.replace(rub, start=rub.end, end=rub.end + datetime.timedelta(hours=1))
        self.assertEqual(candles_module._merge_candles_list([[usd], [later]], "EUR"),
                         [usd, later])

    def test_parse_candles_passes_preferred_currency(self):
        ticker = mock.Mock(boards=["TQCB", "TQOD"], currency="USD")
        rub = candles_module.Candle(
            datetime.datetime(2026, 9, 24, 10), datetime.datetime(2026, 9, 24, 11),
            90, 94, 92, 93, 20, 160000, "RUB",
        )
        usd = dataclasses.replace(rub, currency="USD", value=2700)
        with mock.patch("moexapi.candles._parse_candles_one_board", side_effect=[[rub], [usd]]):
            self.assertEqual(candles_module._parse_candles(ticker), [usd])

    def test_foreign_currency_turnover_keeps_source_currency(self):
        ticker = mock.Mock(secid="RU000A109Z01", market=moexapi.Markets.BONDS, currency="CNY")
        response = {"candles": {
            "columns": ["begin", "end", "low", "high", "open", "close", "volume", "value"],
            "data": [["2026-09-24 10:00:00", "2026-09-24 10:59:59", 62.86, 62.86,
                      62.86, 62.86, 6, 3771.6]],
        }}
        empty = {"candles": {"columns": [], "data": []}}
        with mock.patch("moexapi.candles.utils.json_api_call", side_effect=[response, empty]):
            result = candles_module._parse_candles_one_board(ticker, "TQOY")
        self.assertEqual(result[0].value, 3771.6)
        self.assertEqual(result[0].currency, "CNY")
        self.assertEqual(candles_module.Candle.merge(result[0], result[0]).currency, "CNY")
        other = dataclasses.replace(result[0], currency="RUB")
        with self.assertRaises(AssertionError):
            candles_module.Candle.merge(result[0], other)

    def test_split_adjusts_prices_and_volume_but_preserves_turnover(self):
        ticker = mock.Mock(secid="TEST")
        before = candles_module.Candle(
            datetime.datetime(2020, 1, 1), datetime.datetime(2020, 1, 1, 23),
            90, 110, 100, 100, 10, 1000,
        )
        after = candles_module.Candle(
            datetime.datetime(2020, 1, 3), datetime.datetime(2020, 1, 3, 23),
            9, 11, 10, 10, 100, 1000,
        )
        with (
            mock.patch("moexapi.candles.changeover.get_current_ticker", return_value=ticker),
            mock.patch("moexapi.candles.changeover.get_prev_tickers", return_value=[ticker]),
            mock.patch("moexapi.candles.splits.get_splits", return_value=[
                moexapi.Split(datetime.date(2020, 1, 2), "TEST", 10)
            ]),
            mock.patch("moexapi.candles._parse_candles", return_value=[before, after]),
        ):
            result = moexapi.get_candles(ticker)

        self.assertEqual((result[0].close, result[0].volume, result[0].value), (10, 100, 1000))
        self.assertEqual((result[1].close, result[1].volume, result[1].value), (10, 100, 1000))

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


class History(unittest.TestCase):
    def test_mixed_history_currencies_require_preferred_currency(self):
        date = datetime.date(2026, 9, 24)
        columns = ["TRADEDATE", "BOARDID", "LOW", "HIGH", "OPEN", "CLOSE",
                   "NUMTRADES", "VOLUME", "VALUE", "CURRENCYID"]
        rub = [date.isoformat(), "TQCB", 90, 94, 92, 93, 10, 20, 160000, "SUR"]
        usd = [date.isoformat(), "TQOD", 91, 95, 93, 94, 2, 3, 2700, "USD"]
        for preferred in ("EUR", None):
            ticker = mock.Mock(secid="TEST", market=moexapi.Markets.BONDS,
                               boards=["TQCB", "TQOD"], currency=preferred)
            for rows in ([rub, usd], [usd, rub]):
                with self.subTest(preferred=preferred, rows=rows), mock.patch(
                    "moexapi.history.utils.json_api_call",
                    return_value={"history": {"columns": columns, "data": rows}},
                ):
                    with self.assertRaisesRegex(
                        ValueError, f"TEST on {date}: .*preferred currency is {preferred}"
                    ):
                        history_module._parse_history(ticker, date, date)

    def test_bond_history_selects_one_turnover_currency_per_day(self):
        date = datetime.date(2026, 9, 24)
        columns = [
            "TRADEDATE", "BOARDID", "LOW", "HIGH", "OPEN", "CLOSE",
            "NUMTRADES", "VOLUME", "VALUE", "CURRENCYID",
        ]
        rub = [date.isoformat(), "TQCB", 90, 94, 92, 93, 10, 20, 160000, "SUR"]
        usd = [date.isoformat(), "TQOD", 91, 95, 93, 94, 2, 3, 2700, "USD"]
        usd_other = [date.isoformat(), "TQDU", 92, 96, 94, 95, 4, 5, 4600, "USD"]
        ticker = mock.Mock(
            secid="RU000A0JXTS9", market=moexapi.Markets.FEDERAL_BONDS,
            boards=["TQCB", "TQOD", "TQDU"], currency="USD",
        )
        for rows in ([rub, usd, usd_other], [usd, usd_other, rub]):
            with self.subTest(rows=rows), mock.patch(
                "moexapi.history.utils.json_api_call",
                return_value={"history": {"columns": columns, "data": rows}},
            ):
                result = history_module._parse_history(ticker, date, date)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].currency, "USD")
            self.assertEqual((result[0].value, result[0].volume, result[0].numtrades),
                             (7300, 8, 6))
            self.assertEqual((result[0].low, result[0].high), (91, 96))

        # Do not lose days on which only the RUB settlement board traded.
        with mock.patch(
            "moexapi.history.utils.json_api_call",
            return_value={"history": {"columns": columns, "data": [rub]}},
        ):
            result = history_module._parse_history(ticker, date, date)
        self.assertEqual((result[0].currency, result[0].value), ("RUB", 160000))

    def test_history_does_not_recount_boards_on_repeated_page(self):
        date = datetime.date(2026, 9, 24)
        response = {"history": {
            "columns": ["TRADEDATE", "BOARDID", "LOW", "HIGH", "OPEN", "CLOSE",
                        "NUMTRADES", "VOLUME", "VALUE", "CURRENCYID"],
            "data": [[date.isoformat(), "TQOD", 90, 94, 92, 93, 2, 3, 2700, "USD"]],
        }}
        ticker = mock.Mock(secid="RU000A0JXTS9", market=moexapi.Markets.BONDS,
                           boards=["TQOD"], currency="USD")
        with mock.patch("moexapi.history.utils.json_api_call", return_value=response):
            result = history_module._parse_history(ticker, date - datetime.timedelta(days=1), date)
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0].value, result[0].volume), (2700, 3))

    def test_foreign_currency_bond_turnover_keeps_source_currency(self):
        date = datetime.date(2026, 9, 24)
        response = {
            "history": {
                "columns": [
                    "TRADEDATE", "BOARDID", "LOW", "HIGH", "OPEN", "CLOSE",
                    "NUMTRADES", "VOLUME", "VALUE", "CURRENCYID",
                ],
                "data": [["2026-09-24", "TQOY", 62.86, 62.86, 62.86, 62.86,
                          2, 6, 3771.6, "CNY"]],
            },
        }
        ticker = mock.Mock(
            secid="RU000A109Z01", market=moexapi.Markets.BONDS, boards=["TQOY"]
        )
        with (
            mock.patch("moexapi.history.utils.json_api_call", return_value=response),
            mock.patch("moexapi.exchange.get_rate", return_value=12.6) as rate,
        ):
            candles = history_module._parse_history(ticker, start_date=date, end_date=date)

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].value, 3771.6)
        self.assertEqual(candles[0].currency, "CNY")
        rate.assert_not_called()

    def test_rub_bond_turnover_is_not_converted(self):
        date = datetime.date(2026, 9, 25)
        response = {
            "history": {
                "columns": [
                    "TRADEDATE", "BOARDID", "LOW", "HIGH", "OPEN", "CLOSE",
                    "NUMTRADES", "VOLUME", "VALUE", "CURRENCYID",
                ],
                "data": [["2026-09-25", "TQCB", 98.9, 100.292, 100.2899, 99.8299,
                          180, 1880, 16529780.6, "SUR"]],
            },
        }
        ticker = mock.Mock(
            secid="RU000A10B347", market=moexapi.Markets.BONDS, boards=["TQCB"]
        )
        with (
            mock.patch("moexapi.history.utils.json_api_call", return_value=response),
            mock.patch("moexapi.exchange.get_rate") as rate,
        ):
            candles = history_module._parse_history(ticker, start_date=date, end_date=date)

        self.assertEqual(candles[0].value, 16529780.6)
        self.assertEqual(candles[0].currency, "RUB")
        rate.assert_not_called()

    def test_split_adjusts_prices_and_volume_but_preserves_turnover(self):
        ticker = mock.Mock(secid="TEST")
        before = history_module.History(
            datetime.date(2020, 1, 1), 90, 110, 100, 100, 100, 1, 10, 1000
        )
        after = history_module.History(
            datetime.date(2020, 1, 3), 9, 11, 10, 10, 10, 1, 100, 1000
        )
        with (
            mock.patch("moexapi.history.changeover.get_current_ticker", return_value=ticker),
            mock.patch("moexapi.history.changeover.get_prev_tickers", return_value=[ticker]),
            mock.patch("moexapi.history.splits.get_splits", return_value=[
                moexapi.Split(datetime.date(2020, 1, 2), "TEST", 10)
            ]),
            mock.patch("moexapi.history._parse_history", return_value=[before, after]),
        ):
            result = moexapi.get_history(ticker)

        self.assertEqual((result[0].close, result[0].volume, result[0].value), (10, 100, 1000))
        self.assertEqual((result[1].close, result[1].volume, result[1].value), (10, 100, 1000))

    def test_history_ignores_boards_with_a_different_currency(self):
        response = {
            "history": {
                "columns": [
                    "TRADEDATE", "BOARDID", "LOW", "HIGH", "OPEN", "CLOSE",
                    "WAPRICE", "NUMTRADES", "VOLUME", "VALUE",
                ],
                "data": [
                    ["2026-09-08", "TQBR", 1348.68, 1370.34, 1356.82, 1352.76,
                     1357.23, 163, 2662, 3612898.51],
                    ["2026-09-08", "TQTY", 105.78, 105.78, 105.78, 105.78,
                     105.59, 1, 20, 2115.6],
                ],
            },
        }
        ticker = mock.Mock(
            secid="AKMC",
            market=moexapi.Markets.ETFS,
            boards=["TQBR", "TQTF"],
            currency="RUB",
        )
        with mock.patch("moexapi.history.utils.json_api_call", return_value=response):
            candles = history_module._parse_history(
                ticker,
                start_date=datetime.date(2026, 9, 8),
                end_date=datetime.date(2026, 9, 8),
            )

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].close, 1352.76)
        self.assertEqual(candles[0].currency, "RUB")


class Exchange(unittest.TestCase):
    def test_current_rate_uses_existing_moex_path(self):
        with mock.patch("moexapi.exchange.get_moex_usd_eur_rate", return_value=92.5) as moex_rate:
            self.assertEqual(exchange_module.get_rate("USD"), 92.5)
        moex_rate.assert_called_once_with("USD")

class Dividends(unittest.TestCase):
    def test_dividends(self):
        ticker = mock.Mock(secid="CHMF")
        response = {
            "dividends": {
                "columns": ["secid", "registryclosedate", "value"],
                "data": [["CHMF", "2024-06-18", 191.51]],
            },
        }
        with (
            mock.patch("moexapi.dividends.changeover.get_current_ticker", return_value=ticker),
            mock.patch("moexapi.dividends.changeover.get_prev_tickers", return_value=[ticker]),
            mock.patch("moexapi.dividends.splits.get_splits", return_value=[]),
            mock.patch("moexapi.dividends.utils.json_api_call", return_value=response),
        ):
            dividends = moexapi.get_dividends(ticker)

        self.assertEqual(
            dividends,
            [moexapi.Dividend(date=datetime.date(2024, 6, 18), value=191.51)],
        )

    def test_missing_dividends_block(self):
        ticker = mock.Mock(secid="CHMF")
        with mock.patch(
            "moexapi.dividends.utils.json_api_call",
            return_value={"description": {}, "boards": {}},
        ):
            dividends = moexapi.dividends._get_dividends_for_one_ticker(ticker)

        self.assertEqual(dividends, [])


class Bonds(unittest.TestCase):
    def test_offer_with_zero_date(self):
        ticker = mock.Mock(secid="RU000A0JXN05", shortname="РЖД Б01P1R")
        ticker_info = {
            "NAME": "РЖД БО-001P-01R",
            "ISSUEDATE": "2016-06-10",
            "MATDATE": "2031-06-06",
            "INITIALFACEVALUE": 1000,
            "STARTDATEMOEX": "2016-06-16",
            "ISSUESIZE": 15000000,
            "FACEVALUE": 1000,
            "ISQUALIFIEDINVESTORS": 0,
        }
        bondization = {
            "amortizations": {"columns": [], "data": []},
            "coupons": {"columns": [], "data": []},
            "offers": {
                "columns": ["offerdate", "value"],
                "data": [
                    ["0000-00-00", None],
                    ["2028-05-26", 1000],
                ],
            },
        }
        with (
            mock.patch(
                "moexapi.bonds.tickers.get_ticker_info_dict",
                return_value=ticker_info,
            ),
            mock.patch(
                "moexapi.bonds.utils.json_api_call",
                side_effect=[bondization, bondization],
            ),
        ):
            bond = moexapi.Bond(ticker)

        self.assertEqual(
            bond.offers,
            [moexapi.Offer(date=datetime.date(2028, 5, 26), value=1000)],
        )

    def test_offer_type_and_redemption_price_from_bondization(self):
        ticker = mock.Mock(secid="RU000A10EW44", shortname="ПолюсБ1P5")
        ticker_info = {
            "NAME": "Полюс ПБО-05",
            "ISSUEDATE": "2026-01-01",
            "MATDATE": "2031-03-22",
            "INITIALFACEVALUE": 1000,
            "ISSUESIZE": 1000000,
            "FACEVALUE": 1000,
            "ISQUALIFIEDINVESTORS": 0,
        }
        bondization = {
            "amortizations": {"columns": [], "data": []},
            "coupons": {"columns": [], "data": []},
            "offers": {
                "columns": ["offerdate", "value", "price", "facevalue", "offertype"],
                "data": [["2030-04-01", None, 100, 1000, "Оферта"]],
            },
        }
        with (
            mock.patch("moexapi.bonds.tickers.get_ticker_info_dict", return_value=ticker_info),
            mock.patch("moexapi.bonds.utils.json_api_call", side_effect=[bondization, bondization]),
        ):
            bond = moexapi.Bond(ticker)

        self.assertEqual(
            bond.offers,
            [moexapi.Offer(date=datetime.date(2030, 4, 1), value=1000, type="Оферта")],
        )

    def test_duplicate_coupon_on_pagination_boundary(self):
        ticker = mock.Mock(secid="BYM000001818", shortname="РесБел 331")
        ticker_info = {
            "NAME": "РесБел 331 29.06.2027",
            "ISSUEDATE": "2024-12-27",
            "MATDATE": "2027-06-29",
            "INITIALFACEVALUE": 1000,
            "STARTDATEMOEX": "2025-01-21",
            "ISSUESIZE": 240419,
            "FACEVALUE": 1000,
            "ISQUALIFIEDINVESTORS": 1,
        }
        coupon_columns = [
            "recorddate", "coupondate", "startdate", "value",
            "initialfacevalue",
        ]
        first_page = {
            "amortizations": {
                "columns": ["amortdate", "value", "initialfacevalue"],
                "data": [["2027-06-29", 1000, 1000]],
            },
            "coupons": {
                "columns": coupon_columns,
                "data": [["2027-06-28", "2027-06-29", "2026-12-29", 38.02, 1000]],
            },
            "offers": {"columns": [], "data": []},
        }
        boundary_page = {
            "amortizations": first_page["amortizations"],
            "coupons": first_page["coupons"],
            "offers": {"columns": [], "data": []},
        }
        with (
            mock.patch(
                "moexapi.bonds.tickers.get_ticker_info_dict",
                return_value=ticker_info,
            ),
            mock.patch(
                "moexapi.bonds.utils.json_api_call",
                side_effect=[first_page, boundary_page],
            ),
        ):
            bond = moexapi.Bond(ticker)

        self.assertEqual(len(bond.amortization), 1)
        self.assertEqual(len(bond.coupons), 1)
        self.assertEqual(bond.coupons[0].value, 38.02)

    def test_coupon_without_start_date(self):
        ticker = mock.Mock(secid="RU000A10B4J5", shortname="ПолиплП2Б3")
        ticker_info = {
            "NAME": "Полипласт П2 БО-03",
            "ISSUEDATE": "2026-08-01",
            "MATDATE": "2029-08-01",
            "INITIALFACEVALUE": 1000,
            "STARTDATEMOEX": "2026-08-01",
            "ISSUESIZE": 1000000,
            "FACEVALUE": 1000,
            "ISQUALIFIEDINVESTORS": 0,
        }
        bondization = {
            "amortizations": {
                "columns": [],
                "data": [],
            },
            "coupons": {
                "columns": [
                    "recorddate", "coupondate", "startdate", "value",
                    "initialfacevalue",
                ],
                "data": [[None, "2026-09-01", None, 10, 1000]],
            },
            "offers": {
                "columns": [],
                "data": [],
            },
        }
        with (
            mock.patch(
                "moexapi.bonds.tickers.get_ticker_info_dict",
                return_value=ticker_info,
            ),
            mock.patch(
                "moexapi.bonds.utils.json_api_call",
                side_effect=[bondization, bondization],
            ),
        ):
            bond = moexapi.Bond(ticker)

        self.assertEqual(len(bond.coupons), 1)
        self.assertIsNone(bond.coupons[0].start_date)

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
