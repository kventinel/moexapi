import dataclasses
import datetime
import unittest
from unittest import mock

from moexapi import History, Markets
from moexapi import history


class HistoryAccruedInterest(unittest.TestCase):
    day = datetime.date(2024, 1, 1)

    def row(self, accrued, board="TQOB", currency="SUR", day=None):
        return dict(TRADEDATE=(day or self.day).isoformat(), BOARDID=board,
                    CURRENCYID=currency, ACCINT=accrued,
                    OPEN=100, LOW=99, HIGH=101, CLOSE=100, WAPRICE=100,
                    NUMTRADES=1, VOLUME=1, VALUE=1000)

    def response(self, rows):
        columns = list(rows[0]) if rows else []
        return {"history": {"columns": columns,
                            "data": [[row[key] for key in columns] for row in rows]}}

    def parse(self, rows, preferred="RUB", boards=None):
        ticker = mock.Mock(secid="BOND", market=Markets.FEDERAL_BONDS,
                           currency=preferred, boards=boards or [])
        with mock.patch.object(history.utils, "json_api_call", return_value=self.response(rows)):
            return history._parse_history(ticker, self.day, self.day)

    def test_parse_preserves_zero_and_missing_values(self):
        for amount in (5.25, 0, None):
            with self.subTest(amount=amount):
                [candle] = self.parse([self.row(amount)])
                self.assertEqual(candle.accrued_interest, amount)
                self.assertEqual(candle.currency, "RUB")
                self.assertEqual(candle.close, 100)
        row = self.row(0)
        del row["ACCINT"]
        self.assertIsNone(self.parse([row])[0].accrued_interest)

    def test_reported_rus27_history_through_get_history(self):
        day = datetime.date(2017, 7, 19)
        ticker = mock.Mock(secid="RU000A0JXTS9", market=Markets.FEDERAL_BONDS,
                           currency="USD", boards=["EQOB", "TQOD"])
        # Relevant columns from the real ISS response. The RUB board has no
        # OHLC prices; the USD board has ACCINT even without trade counters.
        rub = self.row(36446.8903, board="EQOB", day=day)
        rub.update(OPEN=None, LOW=None, HIGH=None, CLOSE=None, NUMTRADES=0)
        usd = self.row(613.8889, board="TQOD", currency="USD", day=day)
        usd.update(OPEN=101, LOW=101, HIGH=101, CLOSE=101, WAPRICE=101,
                   NUMTRADES=None, VOLUME=None, VALUE=None)
        with (
            mock.patch.object(history.utils, "json_api_call",
                              return_value=self.response([rub, usd])),
            mock.patch.object(history.changeover, "get_current_ticker", return_value=ticker),
            mock.patch.object(history.changeover, "get_prev_tickers", return_value=[ticker]),
            mock.patch.object(history.splits, "get_splits", return_value=[]),
        ):
            [candle] = history.get_history(ticker, day, day)
        self.assertEqual(candle.date, day)
        self.assertEqual(candle.currency, "USD")
        self.assertEqual(candle.accrued_interest, 613.8889)
        self.assertEqual(candle.close, 101)

    def test_board_and_currency_selection_also_select_accrued_interest(self):
        rub = self.row(5)
        usd = self.row(0.75, board="TQOD", currency="USD")
        ignored = self.row(999, board="IGNORED")
        for rows in ([rub, usd, ignored], [usd, rub, ignored]):
            [candle] = self.parse(rows, preferred="USD", boards=["TQOB", "TQOD"])
            self.assertEqual(candle.accrued_interest, 0.75)
            self.assertEqual(candle.currency, "USD")
        [candle] = self.parse([rub], preferred="USD")
        self.assertEqual(candle.accrued_interest, 5)
        self.assertEqual(candle.currency, "RUB")

    def test_merging_boards_preserves_cash_per_security_without_summing(self):
        [candle] = self.parse([self.row(5), self.row(5, board="TQCB")])
        self.assertEqual(candle.accrued_interest, 5)
        self.assertEqual(candle.volume, 2)
        self.assertEqual(candle.value, 2000)
        for amounts in ((None, 5), (5, None), (None, None)):
            [candle] = self.parse([self.row(amounts[0]), self.row(amounts[1], board="TQCB")])
            self.assertIsNone(candle.accrued_interest)

    def test_merging_conflicting_known_accrued_interest_fails(self):
        with self.assertRaisesRegex(ValueError, "Conflicting accrued interest"):
            self.parse([self.row(5), self.row(6, board="TQCB")])

    def test_repeated_pages_do_not_recount_accrued_interest(self):
        ticker = mock.Mock(secid="BOND", market=Markets.FEDERAL_BONDS,
                           currency="RUB", boards=[])
        next_day = self.day + datetime.timedelta(days=1)
        pages = [self.response([self.row(5)]),
                 self.response([self.row(0, day=next_day)]),
                 self.response([self.row(0, day=next_day)])]
        with mock.patch.object(history.utils, "json_api_call", side_effect=pages):
            candles = history._parse_history(ticker, self.day - datetime.timedelta(days=1), next_day)
        self.assertEqual([c.accrued_interest for c in candles], [5, 0])

    def test_history_merges_and_split_adjustments_preserve_per_security_units(self):
        [candle] = self.parse([self.row(5)])
        merged = history._merge_history([candle], [dataclasses.replace(candle)])[0]
        self.assertEqual(merged.accrued_interest, 5)
        merged.mult(0.5)
        self.assertEqual(merged.accrued_interest, 2.5)
        self.assertEqual(merged.close, 50)
        self.assertEqual(merged.value, 2000)

    def test_old_history_constructor_remains_supported(self):
        candle = History(self.day, 99, 101, 100, 100, 100, 1, 1, 1000)
        self.assertIsNone(candle.accrued_interest)


if __name__ == "__main__":
    unittest.main()
