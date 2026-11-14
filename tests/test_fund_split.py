import unittest
import datetime
from types import SimpleNamespace
from unittest.mock import patch

from moexapi.splits import get_splits
from moexapi import history


class FundSplitTest(unittest.TestCase):
    def response(self, data):
        return {'splits': {'columns': ['tradedate', 'secid', 'before', 'after'], 'data': data}}

    def test_missing_documented_fund_split_is_supplied(self):
        with patch('moexapi.splits.utils.json_api_call', return_value=self.response([])):
            splits = [s for s in get_splits() if s.secid == 'RU000A102N77']
        self.assertEqual([(str(s.date), s.mult) for s in splits], [('2022-10-12', 3)])

    def test_remote_split_is_not_applied_twice(self):
        response = self.response([['2022-10-12', 'RU000A102N77', 1, 3]])
        with patch('moexapi.splits.utils.json_api_call', return_value=response):
            self.assertEqual(len([s for s in get_splits() if s.secid == 'RU000A102N77']), 1)

    def test_conflicting_split_is_rejected(self):
        response = self.response([['2022-10-12', 'RU000A102N77', 1, 2]])
        with patch('moexapi.splits.utils.json_api_call', return_value=response):
            with self.assertRaisesRegex(ValueError, 'Conflicting documented split'):
                get_splits()

    def test_history_keeps_value_continuous_across_fund_split(self):
        ticker = SimpleNamespace(secid='RU000A102N77')
        before = history.History(datetime.date(2022, 10, 11), 300, 300, 300, 300, 300, 1, 1, 300)
        after = history.History(datetime.date(2022, 10, 13), 100, 100, 100, 100, 100, 1, 3, 300)
        with patch('moexapi.history.changeover.get_current_ticker', return_value=ticker), \
             patch('moexapi.history.changeover.get_prev_tickers', return_value=[ticker]), \
             patch('moexapi.history._adjust_unreported_splits'), \
             patch('moexapi.history._parse_history', return_value=[before, after]), \
             patch('moexapi.splits.utils.json_api_call', return_value=self.response([])):
            result = history.get_history(ticker)
        self.assertEqual([r.mid_price for r in result], [100, 100])
        self.assertEqual([r.volume for r in result], [3, 3])
        self.assertEqual([r.value for r in result], [300, 300])


if __name__ == '__main__':
    unittest.main()

class LiquiditySplitTest(FundSplitTest):
    def test_liquidity_old_alias_split_is_present_once(self):
        response=self.response([['2020-03-23','VTBM',1,1000]])
        with patch('moexapi.splits.utils.json_api_call',return_value=response):
            found=[s for s in get_splits() if s.secid=='VTBM']
        self.assertEqual([(str(s.date),s.mult) for s in found],[('2020-03-23',1000)])

class LiquidityAliasHistoryTest(unittest.TestCase):
    def test_current_lqdt_inherits_vtbm_split_without_turnover_scaling(self):
        current = SimpleNamespace(secid='LQDT')
        previous = SimpleNamespace(secid='VTBM')
        before = history.History(datetime.date(2020,3,17),1000,1000,1000,1000,1000,20,2,2000)
        after = history.History(datetime.date(2020,3,24),1,1,1,1,1,20,2000,2000)
        empty = {'splits':{'columns':['tradedate','secid','before','after'],'data':[]}}
        def rows(ticker, **kwargs):
            return [before,after] if ticker.secid=='VTBM' else []
        with patch('moexapi.history.changeover.get_current_ticker',return_value=current), \
             patch('moexapi.history.changeover.get_prev_tickers',return_value=[previous,current]), \
             patch('moexapi.history._adjust_unreported_splits'), \
             patch('moexapi.history._parse_history',side_effect=rows), \
             patch('moexapi.splits.utils.json_api_call',return_value=empty):
            result=history.get_history(current)
        self.assertEqual([r.mid_price for r in result],[1,1])
        self.assertEqual([r.volume for r in result],[2000,2000])
        self.assertEqual([r.value for r in result],[2000,2000])
