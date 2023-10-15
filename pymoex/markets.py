import enum

class Markets(enum.Enum):
    SHARES = "shares"
    BONDS = "bonds"
    INDEX = "index"
    CURRENCY = "currency"

    def __str__(self) -> str:
        return str(self.value)

    @property
    def engine(self):
        ENGINE = {
            Markets.SHARES: "stock",
            Markets.BONDS: "stock",
            Markets.INDEX: "stock",
            Markets.CURRENCY: "currency",
        }
        return ENGINE[self]

    @property
    def market(self):
        MARKETS = {
            Markets.SHARES: "shares",
            Markets.BONDS: "bonds",
            Markets.INDEX: "index",
            Markets.CURRENCY: "selt",
        }
        return MARKETS[self]

    @property
    def path(self):
        return f"/engines/{self.engine}/markets/{self.market}"
