import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from moexapi import Markets, dividends, smartlab


HEADERS = ["Название", "Тикер", "Период", "Дивиденд,<br>руб", "Див.<br>Дох.",
           "СД", "Купить До", "Дата закрытия реестра", "Выплата До", "Цена акции", ""]


def row(secid="SBER", value="33,3", date="11.07.2024", period="2023год",
        status="dividend_approved", sd="", amount_class=""):
    cells = [f'<a href="/q/SBER/dividend/">{secid}</a>', secid, period,
             f'<strong class="{amount_class}">{value}</strong>', "10,5%", sd,
             "10.07.2024", date, "25.07.2024", "316,05", ""]
    return status, cells


def page(*rows, order=None):
    order = list(range(len(HEADERS))) if order is None else order
    html = '<table><thead><tr>' + ''.join(f'<th>{HEADERS[i]}</th>' for i in order)
    html += '</tr></thead><tbody>'
    for status, cells in rows:
        html += f'<tr class="{status}">' + ''.join(f'<td>{cells[i]}</td>' for i in order) + '</tr>'
    return html + '<tr><td colspan="11">+добавить дивиденды</td></tr></tbody></table>'


def test_named_columns_handle_sd_and_preferred_ticker_not_shared_company_link():
    html = page(row(secid="SBERP", value="1\u00a0234,5678", sd='<span title="Рекомендован СД">✓</span>'),
                order=[7, 5, 0, 2, 8, 9, 1, 4, 3, 6, 10])
    assert smartlab._parse_dividends(html) == (
        smartlab.Dividend("SBERP", datetime.date(2024, 7, 11), 1234.5678, "2023год"),
    )


def test_approved_rows_can_have_empty_sd_and_period_year_is_not_record_year():
    assert smartlab._parse_dividends(page(row())) == (
        smartlab.Dividend("SBER", datetime.date(2024, 7, 11), 33.3, "2023год"),
    )


def test_cancelled_and_forecast_rows_are_not_cash_payments_even_with_sd_marker():
    html = page(row(), row(secid="PHOR", value="126", status="dividend_canceled"),
                row(status="dividend_approved", amount_class="dividend_canceled"),
                row(status="", sd="✓"), row(status="dividend_forecast", sd="✓"))
    assert [d.secid for d in smartlab._parse_dividends(html)] == ["SBER"]


@pytest.mark.parametrize("value,date", [('', '11.07.2024'), ('nan', '11.07.2024'),
    ('inf', '11.07.2024'), ('-1', '11.07.2024'), ('33,3', ''), ('33,3', '31.02.2024')])
def test_invalid_approved_payment_does_not_become_empty_history(value, date):
    with pytest.raises(ValueError, match="Invalid Smart-Lab dividend"):
        smartlab._parse_dividends(page(row(value=value, date=date)))


@pytest.mark.parametrize("html", ['<html>Access denied</html>',
    page(row()).replace('Дата закрытия реестра', 'Changed header'),
    page(row()).replace('<td>316,05</td>', '')])
def test_missing_or_changed_table_fails(html):
    with pytest.raises(ValueError):
        smartlab._parse_dividends(html)


def test_explicit_empty_table_is_valid():
    assert smartlab._parse_dividends(page()) == ()


def test_all_periods_aliases_dates_and_distinct_same_day_payments():
    approved = smartlab.Dividend("ABIO", datetime.date(2024, 6, 17), 1.2, "2023год")
    old_alias = smartlab.Dividend("ISKJ", approved.date, approved.value, approved.period)
    second_period = smartlab.Dividend("ABIO", approved.date, 1.2, "Нераспределенная прибыль")
    future = smartlab.Dividend("ABIO", datetime.date.today() + datetime.timedelta(days=1), 50, "future")
    unrelated = smartlab.Dividend("OTHER", approved.date, 100, approved.period)

    def year_rows(year, as_of):
        # A very old reporting period can have a much later record date.
        return (approved, old_alias, second_period, future, unrelated) if year == 2003 else (approved,)

    with patch.object(smartlab, '_load_year', side_effect=year_rows) as load:
        result = smartlab.get_dividends({'ABIO', 'ISKJ'})
    assert [(d.date, d.value, d.period) for d in result] == [
        (approved.date, 1.2, approved.period), (approved.date, 1.2, second_period.period)]
    assert load.call_count == datetime.date.today().year - smartlab.FIRST_PERIOD_YEAR + 1
    assert load.call_args_list[0].args[0] == 2003


def test_public_api_resolves_renamed_ticker_and_does_not_split_adjust_again():
    old = SimpleNamespace(secid='ISKJ', market=Markets.SHARES)
    current = SimpleNamespace(secid='ABIO', market=Markets.SHARES)
    payment = smartlab.Dividend('ABIO', datetime.date(2024, 6, 17), 1.2)
    with (
        patch.object(dividends.changeover, 'get_current_ticker', return_value=current),
        patch.object(dividends.changeover, 'get_prev_tickers', return_value=[old, current]),
        patch.object(dividends.smartlab, 'get_dividends', return_value=[payment]) as load,
        patch('moexapi.splits.get_splits') as split_loader,
    ):
        assert dividends.get_dividends(old) == [dividends.Dividend(payment.date, 1.2)]
    load.assert_called_once_with({'ISKJ', 'ABIO'})
    split_loader.assert_not_called()


def test_year_pages_are_cached_across_stocks_and_as_of_date_refreshes():
    response = Mock(text=page(row(), row(secid='ABIO', value='1,2')))
    today = datetime.date.today()
    smartlab._load_year.cache_clear()
    try:
        with (patch.object(smartlab, 'FIRST_PERIOD_YEAR', today.year),
              patch.object(smartlab.requests, 'get', return_value=response) as get):
            assert smartlab.get_dividends({'SBER'})[0].value == 33.3
            assert smartlab.get_dividends({'ABIO'})[0].value == 1.2
            get.assert_called_once_with(smartlab.DIVIDENDS_URL,
                params={'is_approved': '1', 'year': str(today.year), 'quarter': ''}, timeout=30)
            smartlab._load_year(today.year, today + datetime.timedelta(days=1))
            assert get.call_count == 2
            assert response.raise_for_status.call_count == 2
    finally:
        smartlab._load_year.cache_clear()


@pytest.mark.parametrize('failure', [requests.HTTPError('503'), requests.Timeout('Timeout'),
                                     ValueError('Malformed page')])
def test_failures_are_not_cached_as_empty_histories(failure):
    smartlab._load_year.cache_clear()
    try:
        with patch.object(smartlab.requests, 'get', side_effect=[failure, Mock(text=page(row()))]) as get:
            with pytest.raises(type(failure)):
                smartlab._load_year(2023, datetime.date.today())
            assert len(smartlab._load_year(2023, datetime.date.today())) == 1
            assert get.call_count == 2
    finally:
        smartlab._load_year.cache_clear()
