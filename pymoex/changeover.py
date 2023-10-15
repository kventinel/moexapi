import dataclasses
import datetime

from . import markets
from . import utils


@dataclasses.dataclass
class Changeover:
    date: datetime.date
    old_secid: str
    new_secid: str


class Changeovers(list[Changeover]):
    def __init__(self, market: markets.Markets):
        super().__init__()
        if market == markets.Markets.SHARES:
            response = utils.json_api_call(
                "https://iss.moex.com/iss/history/engines/stock/markets/shares/securities/changeover.json"
            )
            changeover = response["changeover"]
            columns = changeover["columns"]
            data = changeover["data"]
            for line in data:
                self.append(
                    Changeover(
                        date=line[columns.index("action_date")],
                        old_secid=line[columns.index("old_secid")],
                        new_secid=line[columns.index("new_secid")],
                    )
                )
            

class ChangesDict(dict[str, str]):
    def __init__(self):
        super().__init__()
        changeovers = Changeovers(markets.Markets.SHARES)
        self["RSTI"] = "FEES"
        self["RSTIP"] = "FEES"
        self["SFTL"] = "SOFL"
        for line in changeovers:
            new_secid = line.new_secid
            if new_secid in self:
                new_secid = self[new_secid]
            self[line.old_secid] = new_secid
