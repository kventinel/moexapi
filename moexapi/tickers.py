import typing as T

import collections
import dataclasses

from . import changeover
from . import exchange
from . import markets
from . import utils


logger = utils.initialize_logging(__file__)


SECID = "SECID"
ISIN = "ISIN"
SHORTNAME = "SHORTNAME"
BOARDID = "BOARDID"
LAST = "LAST"
PREVPRICE = "PREVPRICE"
SECSUBTYPE = "SECSUBTYPE"
LISTLEVEL = "LISTLEVEL"
LOTVALUE = "LOTVALUE"
CURRENTVALUE = "CURRENTVALUE"
FACEVALUEONSETTLEDATE = "FACEVALUEONSETTLEDATE"
FACEUNIT = "FACEUNIT"
ACCRUEDINT = "ACCRUEDINT"


@dataclasses.dataclass
class TickerBoardInfo:
    secid: str
    market: markets.Markets
    boards: list[str]
    shortname: str
    raw_price: T.Optional[float]
    price: T.Optional[float]
    accumulated_coupon: float
    listlevel: T.Optional[int]


@dataclasses.dataclass
class TickerInfo:
    isin: T.Optional[str]
    subtype: T.Optional[str]
    listlevel: T.Optional[int]

    def __init__(self, secid: str):
        self.secid = secid
        response = utils.json_api_call(f"https://iss.moex.com/iss/securities/{secid}.json")
        description = response["description"]
        columns = description["columns"]
        data = description["data"]
        data_dict = {line[columns.index("name")]: line[columns.index("value")] for line in data}
        self.isin = data_dict.get(ISIN)
        self.subtype = data_dict.get(SECSUBTYPE)
        self.listlevel = int(data_dict[LISTLEVEL]) if LISTLEVEL in data_dict else None


@dataclasses.dataclass
class Ticker(TickerInfo, TickerBoardInfo):
    def __init__(self, secid: str, market: T.Optional[markets.Markets] = None):
        tickers = _parse_tickers(market=market, secid=secid)
        cur_secid = changeover.get_ticker_current_name(secid)
        if len(tickers) == 0 and secid != cur_secid:
            logger.info("change %s to %s", secid, cur_secid)
            tickers = _parse_tickers(market=market, secid=cur_secid)
        if len(tickers) == 0:
            tickers = [ticker for ticker in _parse_tickers(market=market) if ticker.shortname == secid]
        if len(tickers) == 0 and len(secid) == 3 and (market is None or market == markets.Markets.CURRENCY):
            cur_secid = f"{secid}RUB_TOM"
            tickers = _parse_tickers(market=markets.Markets.CURRENCY, secid=cur_secid)
            if len(tickers) == 0:
                tickers = [
                    ticker for ticker in _parse_tickers(market=markets.Markets.CURRENCY)
                    if ticker.shortname == cur_secid
                ]
        assert len(tickers) == 1, f"Can't find ticker {secid}"
        super().__init__(tickers[0].secid)
        for key, value in dataclasses.asdict(tickers[0]).items():
            if getattr(self, key, None) is None:
                setattr(self, key, value) 


def _parse_response(market: markets.Markets, response: T.Any) -> list[TickerBoardInfo]:
    securities = response["securities"]
    sec_columns: list = securities["columns"]
    sec_data: list = securities["data"]
    marketdata = response["marketdata"]
    market_columns: list = marketdata["columns"]
    market_data: list = marketdata["data"]
    assert len(sec_data) == len(market_data)
    boards = collections.defaultdict(list)
    result = {}
    for sec_line, market_line in zip(sec_data, market_data):
        sec_dict = {key: value for key, value in zip(sec_columns, sec_line)}
        market_dict = {key: value for key, value in zip(market_columns, market_line)}
        secid = sec_dict[SECID]
        board = sec_dict[BOARDID]
        if market.board is not None and board not in market.board:
            boards[secid].append(board)
            continue
        else:
            assert secid not in result, "Second accurance of ticker {secid}"
        if market == markets.Markets.INDEX or market == markets.Markets.INDEX:
            raw_price = market_dict[CURRENTVALUE]
        else:
            raw_price = market_dict[LAST]
            if raw_price is None:
                raw_price = sec_dict[PREVPRICE]
        accumulated_coupon = 0
        if ACCRUEDINT in sec_dict:
            accumulated_coupon = sec_dict[ACCRUEDINT]
        lotvalue = sec_dict.get(FACEVALUEONSETTLEDATE)
        if lotvalue is None:
            lotvalue = sec_dict.get(LOTVALUE)
        unit = sec_dict.get(FACEUNIT, "RUB")
        if lotvalue is not None and unit not in ["RUB", "SUR"]:
            lotvalue *= exchange.get_rate(unit)
        price = raw_price
        if price is not None:
            if lotvalue is not None:
                price *= lotvalue / 100
            price += accumulated_coupon
        result[secid] = TickerBoardInfo(
            secid=secid,
            boards=[board],
            market=market,
            shortname=sec_dict[SHORTNAME],
            raw_price=raw_price,
            price=price,
            accumulated_coupon=accumulated_coupon,
            listlevel=sec_dict.get(LISTLEVEL)
        )
    for secid, value in boards.items():
        if secid in result:
            result[secid].boards.extend(value)
    logger.debug("Bad boards for tickers: %s", str(boards.keys() - result.keys()))
    return list(result.values())


def _parse_tickers(
    market: T.Optional[markets.Markets] = None,
    secid: T.Optional[str] = None
) -> list[TickerBoardInfo]:
    secid_str = f"/securities/{secid}" if secid else "/securities"
    if market:
        url = f"https://iss.moex.com/iss{market.path}{secid_str}.json"
        return _parse_response(market, utils.json_api_call(url))
    tickers = []
    for market in markets.Markets:
        tickers.extend(_parse_tickers(market=market, secid=secid))
    return tickers


def get_tickers(market: T.Optional[markets.Markets] = None) -> list[Ticker]:
    tickers = _parse_tickers(market=market)
    market_secids = set((ticker.market, ticker.secid) for ticker in tickers)
    secids = set(ticker.secid for ticker in tickers)
    if len(secids) != len(market_secids):
        raise RuntimeError(f"One secid in different markets")
    return [Ticker(secid=secid, market=market) for market, secid in market_secids]
