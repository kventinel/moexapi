import typing as T

import enum

class Markets(enum.Enum):
    SHARES = "shares"
    BONDS = "bonds"
    ETF = "etf"
    INDEX = "index"
    CURRENCY = "currency"

    def __str__(self) -> str:
        return str(self.value)

    @property
    def engine(self) -> str:
        ENGINE = {
            Markets.SHARES: "stock",
            Markets.BONDS: "stock",
            Markets.ETF: "stock",
            Markets.INDEX: "stock",
            Markets.CURRENCY: "currency",
        }
        return ENGINE[self]

    @property
    def market(self) -> str:
        MARKETS = {
            Markets.SHARES: "shares",
            Markets.BONDS: "bonds",
            Markets.ETF: "shares",
            Markets.INDEX: "index",
            Markets.CURRENCY: "selt",
        }
        return MARKETS[self]
    
    @property
    def board(self) -> T.Optional[T.Sequence[str]]:
        BOARDS = {
            Markets.SHARES: ("TQBR",),
            Markets.BONDS: ("TQCB", "TQOB"),
            Markets.ETF: ("TQTF",),
            Markets.INDEX: None,
            Markets.CURRENCY: ("CETS",),
        }
        return BOARDS[self]
    
    @property
    def candle_boards(self) -> T.Optional[T.Sequence[str]]:
        BOARDS = {
            Markets.SHARES: ("TQBR", "EQBR"),
            Markets.BONDS: ("TQCB", "TQOB"),
            Markets.ETF: ("TQTF",),
            Markets.INDEX: None,
            Markets.CURRENCY: ("CETS",),
        }
        return BOARDS[self]

    @property
    def path(self):
        return f"/engines/{self.engine}/markets/{self.market}"
