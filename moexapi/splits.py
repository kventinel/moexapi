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
    splits = response["splits"]
    columns = splits["columns"]
    data = splits["data"]
    result = [Split(date=datetime.date(2014, 12, 30), secid="IRAO", mult=0.01)]
    for line in data:
        result.append(
            Split(
                date=line[columns.index("tradedate")],
                secid=line[columns.index("secid")],
                mult=line[columns.index("after")] / line[columns.index("before")],
            )
        )
    return result
