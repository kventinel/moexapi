import enum

class Markets(enum.Enum):
    SHARES = "shares"
    BONDS = "bonds"
    INDEX = "index"

    def __str__(self) -> str:
        return str(self.value)
