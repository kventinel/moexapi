import typing as T


def _check_tier(boards: T.Sequence[str], names: T.Sequence[str]) -> T.Optional[str]:
    boards = [board for board in boards if board in names]
    if len(boards) > 1:
        raise RuntimeError(f"Can't compare boards {boards}")
    if len(boards) == 1:
        return boards[0]
    return None


def get_main_board(boards: list[str]) -> str:
    if len(boards) == 1:
        return boards[0]
    NAMES = (
        ("TQCB", "TQBR", "TQTF", "CETS", "TQIF"),
        ("TQOB", "TQIR", "TQRD", "TQPI", "CNGD", "FIXS"),
    )
    for tier in NAMES:
        board = _check_tier(boards, tier)
        if board:
            return board
    raise RuntimeError(
        f"Can't compare boards {boards}, you can find some info about boards at "
        "https://iss.moex.com/iss/engines/stock/markets/bonds/boards"
    )
