import dataclasses
import datetime

from . import markets
from . import utils


@dataclasses.dataclass
class Changeover:
    date: datetime.date
    old_secid: str
    new_secid: str


def get_changeovers(market: markets.Markets) -> list[Changeover]:
    result = []
    response = utils.json_api_call(f"https://iss.moex.com/iss/history{market.path}/securities/changeover.json")
    changeover = response["changeover"]
    columns = changeover["columns"]
    data = changeover["data"]
    for line in data:
        result.append(
            Changeover(
                date=line[columns.index("action_date")],
                old_secid=line[columns.index("old_secid")],
                new_secid=line[columns.index("new_secid")],
            )
        )
    return result


def get_prev_names(secid: str, market: markets.Markets) -> list[str]:
    changeovers = sorted(get_changeovers(market), key=lambda x: x.date, reverse=True)
    names = [secid]
    for line in changeovers:
        if line.new_secid == names[-1]:
            names.append(line.old_secid)
    return names
            

def get_ticker_current_name(secid: str) -> str:
    changeovers = sorted(get_changeovers(markets.Markets.SHARES), key=lambda x: x.date)
    for line in changeovers:
        if secid == line.old_secid:
            secid = line.new_secid
    if secid in ["RSTI", "RSTIP"]:
        return "FEES"
    if secid == "SFTL":
        return "SOFL"
    return secid
