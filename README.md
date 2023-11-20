# MOEXAPI

Библиотека для парсинга данных MOEX

## Install

Установить можно одним из способов:
- `pip install moexapi`
- `git clone https://github.com/kventinel/moexapi.git`

## Examples

### Ticker

```
In [2]: moexapi.get_ticker('GAZP')
Out[2]: Ticker(secid='GAZP', alias='GAZP', is_traded=True, market=shares, shortname='ГАЗПРОМ ао', isin='RU0007661625', subtype=None, listlevel=1, boards=['TQBR', 'SMAL', 'SPEQ'], raw_price=166.15, price=166.15, accumulated_coupon=0, value=1198036323)
```

### Candles

```
In [4]: moexapi.get_candles(moexapi.get_ticker('GAZP'), start_date=datetime.date(2023, 10, 2), end_date=datetime.date(2023, 10, 2))
Out[4]: [Candle(date=datetime.date(2023, 10, 2), low=165.51, high=168.86, open=167.83, close=166.08, mid_price=167.16, numtrades=117852, volume=24391830, value=4077382279.5)]
```

### Bonds

```
In [5]: moexapi.Bond(moexapi.get_ticker('SU26238RMFS4'))
Out[5]: Bond(secid='SU26238RMFS4', shortname='ОФЗ 26238', amortization=[Amortization(date=datetime.date(2041, 5, 15), value=1000, initialfacevalue=1000)], coupons=[Coupon(date=2021-12-08, value=34.04), Coupon(date=2022-06-08, value=35.4), Coupon(date=2022-12-07, value=35.4), Coupon(date=2023-06-07, value=35.4), Coupon(date=2023-12-06, value=35.4), Coupon(date=2024-06-05, value=35.4), Coupon(date=2024-12-04, value=35.4), Coupon(date=2025-06-04, value=35.4), Coupon(date=2025-12-03, value=35.4), Coupon(date=2026-06-03, value=35.4), Coupon(date=2026-12-02, value=35.4), Coupon(date=2027-06-02, value=35.4), Coupon(date=2027-12-01, value=35.4), Coupon(date=2028-05-31, value=35.4), Coupon(date=2028-11-29, value=35.4), Coupon(date=2029-05-30, value=35.4), Coupon(date=2029-11-28, value=35.4), Coupon(date=2030-05-29, value=35.4), Coupon(date=2030-11-27, value=35.4), Coupon(date=2031-05-28, value=35.4), Coupon(date=2031-11-26, value=35.4), Coupon(date=2032-05-26, value=35.4), Coupon(date=2032-11-24, value=35.4), Coupon(date=2033-05-25, value=35.4), Coupon(date=2033-11-23, value=35.4), Coupon(date=2034-05-24, value=35.4), Coupon(date=2034-11-22, value=35.4), Coupon(date=2035-05-23, value=35.4), Coupon(date=2035-11-21, value=35.4), Coupon(date=2036-05-21, value=35.4), Coupon(date=2036-11-19, value=35.4), Coupon(date=2037-05-20, value=35.4), Coupon(date=2037-11-18, value=35.4), Coupon(date=2038-05-19, value=35.4), Coupon(date=2038-11-17, value=35.4), Coupon(date=2039-05-18, value=35.4), Coupon(date=2039-11-16, value=35.4), Coupon(date=2040-05-16, value=35.4), Coupon(date=2040-11-14, value=35.4), Coupon(date=2041-05-15, value=35.4)], offers=[])
```
