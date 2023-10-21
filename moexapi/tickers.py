import typing as T

import dataclasses

from . import boards as boards_lib
from . import changeover
from . import markets
from . import utils


logger = utils.initialize_logging(__file__)


@dataclasses.dataclass
class OneBoardTicker:
    secid: str
    market: markets.Markets
    board: str
    shortname: str
    price: float


@dataclasses.dataclass
class TickerInfo:
    secid: str
    isin: str
    subtype: T.Optional[str]
    listlevel: int

    def __init__(self, secid: str):
        self.secid = secid
        response = utils.json_api_call(f"https://iss.moex.com/iss/securities/{secid}.json")
        description = response["description"]
        columns = description["columns"]
        data = description["data"]
        for line in data:
            if line[columns.index("name")] == "SECSUBTYPE":
                self.subtype = line[columns.index("value")]
            if line[columns.index("name")] == "LISTLEVEL":
                self.listlevel = line[columns.index("value")]
            if line[columns.index("name")] == "ISIN":
                self.isin = line[columns.index("value")]


@dataclasses.dataclass
class Ticker(TickerInfo):
    boards: list[str]
    market: markets.Markets
    shortname: str
    price: float

    def __init__(self, secid: str, market: T.Optional[markets.Markets] = None, board: T.Optional[str] = None):
        if len(secid) == 3:
            secid = f"{secid}RUB_TOM"
        tickers = _parse_tickers(market=market, board=board, secid=secid)
        if len(tickers) == 0 and market is None:
            tickers = [
                ticker
                for ticker in _parse_tickers(market=markets.Markets.CURRENCY, board=board) if ticker.shortname == secid
            ]
        if len(tickers) == 0 and secid in changeover.ChangesDict():
            logger.info(f"change {secid} to FEES")
            tickers = _parse_tickers(market=market, board=board, secid="FEES")
        assert len(tickers) > 0, f"Can't find ticker {secid}"
        if any(ticker.secid != tickers[0].secid for ticker in tickers):
            raise RuntimeError(f"Different secids for ticker {secid}")
        if any(ticker.market != tickers[0].market for ticker in tickers):
            raise RuntimeError(f"Different markets for ticker {secid}")
        if any(ticker.shortname != tickers[0].shortname for ticker in tickers):
            raise RuntimeError(f"Different shortnames for ticker {secid}")
        ticker_boards = [ticker.board for ticker in tickers]
        main_tickers = [ticker for ticker in tickers if ticker.board == boards_lib.get_main_board(ticker_boards)]
        if len(main_tickers) != 1:
            raise RuntimeError(f"Can't find main ticker {main_tickers}")
        super().__init__(tickers[0].secid)
        self.boards = list(set(ticker.board for ticker in tickers))
        self.market = tickers[0].market
        self.shortname = tickers[0].shortname
        self.price = main_tickers[0].price


def _parse_response(market: markets.Markets, response: T.Any) -> list[OneBoardTicker]:
    securities = response["securities"]
    sec_columns: list = securities["columns"]
    sec_data: list = securities["data"]
    marketdata = response["marketdata"]
    market_columns: list = marketdata["columns"]
    market_data: list = marketdata["data"]
    assert len(sec_data) == len(market_data)
    result = []
    for sec_line, market_line in zip(sec_data, market_data):
        sec_dict = {key: value for key, value in zip(sec_columns, sec_line)}
        market_dict = {key: value for key, value in zip(market_columns, market_line)}
        secid = sec_dict["SECID"]
        if market == markets.Markets.INDEX or market == markets.Markets.INDEX:
            price = market_dict["CURRENTVALUE"]
        else:
            price = market_dict["LAST"]
            if price is None:
                price = sec_dict["PREVWAPRICE"]
        if price is not None and "LOTVALUE" in sec_dict:
            price *= sec_dict["LOTVALUE"] / 100
        result.append(OneBoardTicker(
            secid=secid,
            board=sec_dict["BOARDID"],
            market=market,
            shortname=sec_dict["SHORTNAME"],
            price=price,
        ))
    return result


def _parse_tickers(
    market: T.Optional[markets.Markets] = None,
    board: T.Optional[str] = None,
    secid: T.Optional[str] = None
) -> list[OneBoardTicker]:
    secid_str = f"/securities/{secid}" if secid else "/securities"
    board_str = f"/boards/{board}" if board else ""
    if market:
        url = f"https://iss.moex.com/iss{market.path}{board_str}{secid_str}.json"
        return _parse_response(market, utils.json_api_call(url))
    tickers = []
    for market in markets.Markets:
        tickers.extend(_parse_tickers(secid=secid, board=board, market=market))
    return tickers


def get_tickers(market: T.Optional[markets.Markets] = None, board: T.Optional[str] = None) -> list[Ticker]:
    tickers = _parse_tickers(market=market, board=board)
    market_secids = set((ticker.market, ticker.secid) for ticker in tickers)
    secids = set(ticker.secid for ticker in tickers)
    if len(secids) != len(market_secids):
        raise RuntimeError(f"One secid in different markets")
    return [Ticker(secid=secid, market=market) for market, secid in market_secids]
