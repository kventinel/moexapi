import typing as T

import collections
import dataclasses
import datetime

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
VALTODAY = "VALTODAY"
CURRENCY = "CURRENCYID"
IS_TRADED = "is_traded"
HISTORY_TILL = "history_till"


def _sur_to_rub(currency: T.Optional[str]) -> T.Optional[str]:
    if currency == "SUR":
        return "RUB"
    return currency


class NotFindTicker(RuntimeError):
    def __init__(self, ticker, candidates):
        self.ticker = ticker
        self.candidates = candidates

    def __repr__(self):
        return f"Can't find ticker {self.ticker}, because of {self.candidates} candidates"


@dataclasses.dataclass
class Listing:
    secid: str
    market: markets.Market
    shortname: str
    history_till: datetime.date

    def __hash__(self):
        return hash(self.secid) + hash(self.market)


@dataclasses.dataclass
class TickerBoardInfo:
    boards: list[str]
    currency: str
    raw_price: T.Optional[float]
    price: T.Optional[float]
    price_in_rub: T.Optional[float]
    accumulated_coupon: float
    listlevel: T.Optional[int]
    value: T.Optional[float]

    @classmethod
    def from_secid(cls, secid: str, market: markets.Market) -> T.Optional["TickerBoardInfo"]:
        response = utils.json_api_call(f"https://iss.moex.com/iss{market.path}/securities/{secid}.json")
        securities = utils.prepare_dict(response, "securities")
        marketdata = utils.prepare_dict(response, "marketdata")
        assert len(securities) == len(marketdata)
        boards = []
        result = None
        for sec_line, market_line in zip(securities, marketdata):
            board = sec_line[BOARDID]
            if market.boards and board not in market.boards:
                boards.append(board)
                continue
            else:
                assert result is None, f"Second accurance of ticker {secid}: {result.boards[0]} vs {board}"
            if market == markets.Markets.INDEX:
                raw_price = market_line[CURRENTVALUE]
            else:
                raw_price = market_line[LAST]
                if raw_price is None:
                    raw_price = sec_line[PREVPRICE]
            accumulated_coupon = 0
            if ACCRUEDINT in sec_line:
                accumulated_coupon = sec_line[ACCRUEDINT]
            lotvalue = sec_line.get(FACEVALUEONSETTLEDATE)
            if lotvalue is None:
                lotvalue = sec_line.get(LOTVALUE)
            if lotvalue is not None:
                currency = _sur_to_rub(sec_line.get(FACEUNIT, "RUB"))
            else:
                currency = _sur_to_rub(sec_line.get(CURRENCY, "RUB"))
            rate = 1
            price = raw_price
            if currency is not None and currency != "RUB" and market != markets.Markets.CURRENCY and price is not None:
                rate = exchange.get_rate(currency)
            if price is not None:
                if lotvalue is not None:
                    price *= lotvalue / 100
                if accumulated_coupon:
                    coupon_currency = _sur_to_rub(sec_line[CURRENCY])
                    if coupon_currency is not None and coupon_currency != currency:
                        assert coupon_currency == "RUB"
                        accumulated_coupon /= rate
                    price += accumulated_coupon
            price_in_rub = price * rate if price is not None else None
            result = cls(
                boards=[board],
                currency=currency,
                raw_price=raw_price,
                price=price,
                price_in_rub=price_in_rub,
                accumulated_coupon=accumulated_coupon,
                listlevel=sec_line.get(LISTLEVEL),
                value=market_line[VALTODAY],
            )
        if result:
            result.boards.extend(boards)
        return result


def get_ticker_info_dict(secid: str) -> dict[str, str]:
    response = utils.json_api_call(f"https://iss.moex.com/iss/securities/{secid}.json")
    description_columns, description_data = response["description"]["columns"], response["description"]["data"]
    return {
        line[description_columns.index("name")]: line[description_columns.index("value")]
        for line in description_data
    }


@dataclasses.dataclass
class TickerInfo:
    is_traded: bool
    shortname: T.Optional[str]
    isin: T.Optional[str]
    subtype: T.Optional[str]
    listlevel: T.Optional[int]

    @classmethod
    def from_secid(cls, secid: str, market: markets.Market) -> "TickerInfo":
        response = utils.json_api_call(f"https://iss.moex.com/iss/securities/{secid}.json")
        boards = utils.prepare_dict(response, "boards")
        is_traded = False
        for line in boards:
            if not market.boards or line[BOARDID.lower()] in market.boards and line[IS_TRADED] == 1:
                is_traded = True
        description = get_ticker_info_dict(secid)
        return cls(
            shortname=description.get(SHORTNAME),
            isin=description.get(ISIN),
            subtype=description.get(SECSUBTYPE),
            listlevel=int(description[LISTLEVEL]) if LISTLEVEL in description else None,
            is_traded=is_traded
        )


@dataclasses.dataclass
class Ticker:
    secid: str
    alias: str
    is_traded: bool
    market: markets.Market
    shortname: T.Optional[str]
    isin: T.Optional[str]
    subtype: T.Optional[str]
    listlevel: T.Optional[int]
    boards: list[str] = dataclasses.field(default_factory=lambda: [])
    currency: T.Optional[str] = None
    raw_price: T.Optional[float] = None
    price: T.Optional[float] = None
    price_in_rub: T.Optional[float] = None
    accumulated_coupon: T.Optional[float] = None
    value: T.Optional[float] = None

    @classmethod
    def from_secid(cls, secid: str, market: markets.Market = markets.Markets.ALL) -> "Ticker":
        parsed_tickers = _parse_tickers(market=market)
        tickers = [ticker for ticker in parsed_tickers if ticker.secid == secid]
        if len(tickers) == 0:
            tickers = [ticker for ticker in parsed_tickers if ticker.shortname.replace(' ', '') == secid]
        if len(tickers) == 0 and len(secid) == 3 and market.has(markets.Markets.CURRENCY):
            cur_secid = f"{secid}RUB_TOM"
            tickers = [
                ticker for ticker in parsed_tickers if ticker.secid == cur_secid and market.has(markets.Markets.CURRENCY)
            ]
            if len(tickers) == 0:
                tickers = [
                    ticker for ticker in parsed_tickers
                    if ticker.shortname == cur_secid and market.has(markets.Markets.CURRENCY)
                ]
        if len(tickers) != 1:
            if len(tickers) > 1:
                logger.error(f'Find too many tickers for {secid}: {tickers}')
            raise NotFindTicker(secid, len(tickers))
        result = cls.from_listing(tickers[0])
        result.alias = secid
        return result

    @classmethod
    def from_listing(cls, listing: Listing) -> "Ticker":
        info = TickerInfo.from_secid(listing.secid, listing.market)
        assert info.shortname is None or listing.shortname == info.shortname
        result = cls(
            secid=listing.secid,
            alias=listing.secid,
            is_traded=info.is_traded,
            market=listing.market,
            shortname=listing.shortname,
            isin=info.isin,
            subtype=info.subtype,
            listlevel=info.listlevel,
        )
        board_info = TickerBoardInfo.from_secid(listing.secid, listing.market)
        if board_info is not None:
            for key, value in dataclasses.asdict(board_info).items():
                if getattr(result, key, None) is None or getattr(result, key, None) == []:
                    setattr(result, key, value)
                elif getattr(result, key) != value:
                    logger.warning(f"{getattr(result, key)} vs {value} for {key} (use first)")
        return result


def _parse_tickers(market: markets.Market = markets.Markets.ALL) -> list[Listing]:
    tickers: dict[str, list[Listing]] = collections.defaultdict(list)
    for child_market in market.childs():
        idx = 0
        while True:
            start = f"?start={idx}"
            response = utils.json_api_call(
                f"https://iss.moex.com/iss/history{child_market.path}/listing.json{start}"
            )
            securities = utils.prepare_dict(response, "securities")
            if len(securities) == 0:
                break
            for line in securities:
                if (len(child_market.boards) == 0 or line[BOARDID] in child_market.boards) and line[HISTORY_TILL]:
                    tickers[line[SECID]].append(
                        Listing(
                            secid=line[SECID],
                            market=child_market,
                            shortname=line[SHORTNAME],
                            history_till=datetime.date.fromisoformat(line[HISTORY_TILL]),
                        )
                    )
            idx += len(securities)
    result = []
    for _, securities in tickers.items():
        securities.sort(key=lambda x: x.history_till, reverse=True)
        for security in securities[1:]:
            assert security.history_till < securities[0].history_till or security.market == securities[0].market
        result.append(securities[0])
    return result


def get_ticker(secid: str, market: markets.Market = markets.Markets.ALL) -> Ticker:
    return Ticker.from_secid(secid, market=market)


def get_tickers(market: markets.Market = markets.Markets.ALL) -> list[Ticker]:
    tickers = _parse_tickers(market=market)
    return [Ticker.from_secid(secid=ticker.secid, market=ticker.market) for ticker in tickers]
