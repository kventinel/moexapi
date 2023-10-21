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
        ('TQCB', 'TQBR', 'TQTF', 'CETS'),
        ('TQOB', 'TQIR', 'TQRD'),
    )
    for tier in NAMES:
        board = _check_tier(boards, tier)
        if board:
            return board
    raise RuntimeError(f"Can't compare boards {boards}")
