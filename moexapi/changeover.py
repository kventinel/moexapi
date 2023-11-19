import dataclasses
import datetime

from . import utils


@dataclasses.dataclass
class Changeover:
    date: datetime.date
    old_secid: str
    new_secid: str

    def __lt__(self, other: "Changeover"):
        return self.date < other.date


def get_changeovers() -> list[Changeover]:
    """Return changeovers in sorted by date order"""
    result = []
    response = utils.json_api_call(
        "https://iss.moex.com/iss/history/engines/stock/markets/shares/securities/changeover.json"
    )
    changeover = utils.prepare_dict(response, "changeover")
    for line in changeover:
        result.append(
            Changeover(
                date=datetime.date.fromisoformat(line["action_date"]),
                old_secid=line["old_secid"],
                new_secid=line["new_secid"],
            )
        )
    result.append(
        Changeover(date=datetime.date(2023, 9, 20), old_secid="SFTL", new_secid="SOFL"),
    )
    return sorted(result)


def get_prev_names(secid: str) -> list[str]:
    changeovers = get_changeovers()[::-1]
    names = [secid]
    for line in changeovers:
        if line.new_secid == names[-1]:
            names.append(line.old_secid)
    return names


def get_ticker_current_name(secid: str) -> str:
    changeovers = get_changeovers()
    for line in changeovers:
        if secid == line.old_secid:
            secid = line.new_secid
    if secid in ["RSTI", "RSTIP"]:
        return "FEES"
    return secid
