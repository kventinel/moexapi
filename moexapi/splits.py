import dataclasses
import datetime

from . import utils


@dataclasses.dataclass
class Split:
    date: datetime.date
    secid: str
    mult: float


def get_splits() -> list[Split]:
    response = utils.json_api_call("https://iss.moex.com/iss/statistics/engines/stock/splits.json")
    splits = utils.prepare_dict(response, "splits")
    result = [Split(date=datetime.date(2014, 12, 30), secid="IRAO", mult=0.01)]
    for line in splits:
        result.append(
            Split(
                date=datetime.date.fromisoformat(line["tradedate"]),
                secid=line["secid"],
                mult=line["after"] / line["before"],
            )
        )
    return result
