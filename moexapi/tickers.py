import typing as T

import collections
import dataclasses

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
IS_TRADED = "is_traded"


@dataclasses.dataclass
class Listing:
    secid: str
    market: markets.Market
    shortname: str

    def __hash__(self):
        return hash(self.secid) + hash(self.market)


@dataclasses.dataclass
class TickerBoardInfo:
    boards: list[str]
    raw_price: T.Optional[float]
    price: T.Optional[float]
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
            unit = sec_line.get(FACEUNIT, "RUB")
            if lotvalue is not None and unit not in ["RUB", "SUR"]:
                lotvalue *= exchange.get_rate(unit)
            price = raw_price
            if price is not None:
                if lotvalue is not None:
                    price *= lotvalue / 100
                price += accumulated_coupon
            result = cls(
                boards=[board],
                raw_price=raw_price,
                price=price,
                accumulated_coupon=accumulated_coupon,
                listlevel=sec_line.get(LISTLEVEL),
                value=market_line[VALTODAY],
            )
        if result:
            result.boards.extend(boards)
        return result


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
        description_columns, description_data = response["description"]["columns"], response["description"]["data"]
        description = {
            line[description_columns.index("name")]: line[description_columns.index("value")]
            for line in description_data
        }
        boards = utils.prepare_dict(response, "boards")
        is_traded = False
        for line in boards:
            if not market.boards or line[BOARDID.lower()] in market.boards and line[IS_TRADED] == 1:
                is_traded = True
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
    raw_price: T.Optional[float] = None
    price: T.Optional[float] = None
    accumulated_coupon: T.Optional[float] = None
    listlevel: T.Optional[int] = None
    value: T.Optional[float] = None

    @classmethod
    def from_secid(cls, secid: str, market: markets.Market = markets.Markets.ALL) -> "Ticker":
        parsed_tickers = _parse_tickers(market=market)
        tickers = [ticker for ticker in parsed_tickers if ticker.secid == secid]
        if len(tickers) == 0:
            tickers = [ticker for ticker in parsed_tickers if ticker.shortname == secid]
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
        assert len(tickers) == 1, f"Can't find ticker {secid}"
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
    tickers = set()
    for child_market in market.childs():
        idx = 0
        while True:
            start = f"?start={idx}"
            response = utils.json_api_call(
                f"https://iss.moex.com/iss/history{child_market.board_path}/listing.json{start}"
            )
            securities = utils.prepare_dict(response, "securities")
            if len(securities) == 0:
                break
            for line in securities:
                tickers.add(Listing(secid=line[SECID], market=child_market, shortname=line[SHORTNAME]))
            idx += len(securities)
    return list(tickers)


def get_ticker(secid: str, market: markets.Market = markets.Markets.ALL) -> Ticker:
    return Ticker.from_secid(secid, market=market)


def get_tickers(market: markets.Market = markets.Markets.ALL) -> list[Ticker]:
    tickers = _parse_tickers(market=market)
    return [Ticker.from_secid(secid=ticker.secid, market=ticker.market) for ticker in tickers]
