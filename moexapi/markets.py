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
        self.name = name
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

    def split(self) -> list["Market"]:
        result = []
        if len(self.engines) == 1 and len(self.markets) == 1:
            result.append(self)
        else:
            for child in self._childs:
                result.extend(child.split())
        assert len(result) > 0
        return result

    @property
    def path(self) -> str:
        assert len(self.engines) == 1 and len(self.markets) == 1
        return f"/engines/{list(self.engines)[0]}/markets/{list(self.markets)[0]}"

    def specify(self, board: str) -> "Market":
        candidates: list["Market"] = []
        for child in self._childs:
            if board in child.boards:
                candidates.append(child)
        if len(candidates) == 0:
            return self
        assert len(candidates) == 1
        return candidates[0].specify(board)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


ALL = Market("all")
STOCK = Market("stock", parent=ALL, engines={"stock"})
EQUITY = Market("equity", parent=STOCK, markets={"shares"})
SHARES = Market("shares", parent=EQUITY, boards={"TQBR"}, candle_boards={"EQBR"})
ETFS = Market("etfs", parent=EQUITY, boards={"TQTF"})
BONDS = Market("bonds", parent=STOCK, markets={"bonds"})
FEDERAL_BONDS = Market("federal bonds", parent=BONDS, boards={"TQOB"})
COMPANY_BONDS = Market("company bonds", parent=BONDS, boards={"TQCB"})
INDEX = Market("index", parent=STOCK, markets={"index"})
CURRENCY = Market("currency", parent=ALL, engines={"currency"}, markets={"selt"}, boards={"CETS"})
