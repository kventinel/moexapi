import unittest
from types import SimpleNamespace
from unittest.mock import patch

from moexapi.dividends import _get_dividends_for_one_ticker


class DividendResponseTest(unittest.TestCase):
    def test_security_description_is_not_an_empty_dividend_history(self):
        response = {'description': {'data': []}, 'boards': {'data': []}}
        with patch('moexapi.dividends.utils.json_api_call', return_value=response):
            with self.assertRaisesRegex(ValueError, 'Missing dividends table for SFIN'):
                _get_dividends_for_one_ticker(SimpleNamespace(secid='SFIN'))

    def test_explicit_empty_dividend_table_is_valid(self):
        response = {'dividends': {'columns': ['registryclosedate', 'value'], 'data': []}}
        with patch('moexapi.dividends.utils.json_api_call', return_value=response):
            self.assertEqual(_get_dividends_for_one_ticker(SimpleNamespace(secid='SFIN')), [])

    def test_documented_cash_distribution_is_preserved(self):
        response = {'dividends': {'columns': ['value', 'registryclosedate'],
                                  'data': [[902.0, '2025-12-25']]}}
        with patch('moexapi.dividends.utils.json_api_call', return_value=response):
            result = _get_dividends_for_one_ticker(SimpleNamespace(secid='SFIN'))
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result[0].date), '2025-12-25')
        self.assertEqual(result[0].value, 902.0)


if __name__ == '__main__':
    unittest.main()
