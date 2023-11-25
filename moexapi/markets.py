import typing as T


class Market:
    def __init__(
        self,
        name: str,
        parent: T.Optional["Market"] = None,
        engines: set[str] = frozenset(),
        markets: set[str] = frozenset(),
        boards: set[str] = frozenset(),
        candle_boards: set[str] = frozenset(),
    ):
        self._name = name
        self._engines = engines
        self._markets = markets
        self._boards = boards
        self._candle_boards = candle_boards
        self._parent = parent
        self._childs: list["Market"] = []
        if parent:
            parent._childs.append(self)

    def _get_parent(self, attr) -> set[str]:
        cur = getattr(self, attr)
        parent = self._parent._get_parent(attr) if self._parent else set()
        assert len(cur) == 0 or len(parent) == 0
        return cur | parent

    def _get_childs(self, attr) -> set[str]:
        cur = getattr(self, attr)
        childs = set()
        for child in self._childs:
            childs = childs | child._get_childs(attr)
        assert len(cur) == 0 or len(childs) == 0
        return cur | childs

    def _join(self, attr) -> set[str]:
        parent = self._get_parent(attr)
        childs = self._get_childs(attr)
        cur = getattr(self, attr)
        assert len(parent - cur) == 0 or len(childs - cur) == 0, f"{parent} vs {childs}"
        return parent | childs

    @property
    def engines(self) -> set[str]:
        return self._join("_engines")

    @property
    def markets(self) -> set[str]:
        return self._join("_markets")

    @property
    def boards(self) -> set[str]:
        return self._join("_boards")

    @property
    def candle_boards(self) -> set[str]:
        return self._join("_boards") | self._join("_candle_boards")
    
    def childs(self) -> list["Market"]:
        if len(self._childs) == 0:
            return [self]
        result = []
        for child in self._childs:
            result.extend(child.childs())
        return result

    @property
    def path(self) -> str:
        assert len(self.engines) == 1 and len(self.markets) == 1
        return f"/engines/{list(self.engines)[0]}/markets/{list(self.markets)[0]}"

    @property
    def board_path(self) -> str:
        assert len(self.boards) <= 1
        if len(self.boards) == 0:
            return self.path
        return f"{self.path}/boards/{list(self.boards)[0]}"

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return self._name

    def has(self, market: 'Market') -> bool:
        if market._name == self._name:
            return True
        for child in self._childs:
            if child.has(market):
                return True
        return False

    def __eq__(self, other: 'Market') -> bool:
        return self._name == other._name

    def __hash__(self) -> int:
        return hash(self._name)

_ALL = Market("all")
_STOCK = Market("stock", parent=_ALL, engines={"stock"})
_EQUITY = Market("equity", parent=_STOCK, markets={"shares"})
_SHARES = Market("shares", parent=_EQUITY, boards={"TQBR"}, candle_boards={"EQBR"})
_ETFS = Market("etfs", parent=_EQUITY, boards={"TQTF"})
_BONDS = Market("bonds", parent=_STOCK, markets={"bonds"})
_FEDERAL_BONDS = Market("federal bonds", parent=_BONDS, boards={"TQOB"})
_COMPANY_BONDS = Market("company bonds", parent=_BONDS, boards={"TQCB"})
_INDEX = Market("index", parent=_STOCK, markets={"index"})
_CURRENCY = Market("currency", parent=_ALL, engines={"currency"}, markets={"selt"}, boards={"CETS"})


class Markets:
    ALL = _ALL
    STOCK = _STOCK
    EQUITY = _EQUITY
    SHARES = _SHARES
    ETFS = _ETFS
    BONDS = _BONDS
    FEDERAL_BONDS = _FEDERAL_BONDS
    COMPANY_BONDS = _COMPANY_BONDS
    INDEX = _INDEX
    CURRENCY = _CURRENCY
