import typing as T

import dataclasses
import datetime

from . import tickers
from . import utils


def _max(first, second):
    if first is not None and second is not None:
        return max(first, second)
    if first is not None:
        return first
    return second


@dataclasses.dataclass
class Amortization:
    date: datetime.date
    value: float
    initialfacevalue: float


@dataclasses.dataclass
class Coupon:
    date: datetime.date
    start_date: datetime.date
    value: float
    initialfacevalue: float

    def __repr__(self) -> str:
        return f'Coupon(date={self.date.isoformat()}, value={self.value})'


@dataclasses.dataclass
class Offer:
    date: datetime.date
    value: float


@dataclasses.dataclass(init=True)
class Bond:
    secid: str
    shortname: str
    amortization: list[Amortization]
    coupons: list[Coupon]
    offers: list[Offer]

    def __init__(self, ticker: tickers.Ticker):
        self.secid = ticker.secid
        self.shortname = ticker.shortname
        self.amortization = []
        self.coupons = []
        self.offers = []
        limit = 100
        start_date: T.Optional[datetime.date] = None
        while True:
            start_str = f"&from={start_date.isoformat()}" if start_date else ""
            response = utils.json_api_call(
                f"https://iss.moex.com/iss/securities/{ticker.secid}/bondization.json?limit={limit}{start_str}"
            )
            amortization = utils.prepare_dict(response, "amortizations")
            coupons = utils.prepare_dict(response, "coupons")
            offers = utils.prepare_dict(response, "offers")
            end_date = None
            for line in amortization:
                date = datetime.date.fromisoformat(line["amortdate"])
                end_date = _max(end_date, date)
                self.amortization.append(
                    Amortization(date=date, value=line["value"], initialfacevalue=line["initialfacevalue"])
                )
            for line in coupons:
                date = datetime.date.fromisoformat(line["coupondate"])
                end_date = _max(end_date, date)
                self.coupons.append(
                    Coupon(
                        date=date,
                        start_date=datetime.date.fromisoformat(line["startdate"]),
                        value=line["value"],
                        initialfacevalue=line["initialfacevalue"],
                    )
                )
            for line in offers:
                date = datetime.date.fromisoformat(line["offerdate"])
                end_date = _max(end_date, date)
                self.offers.append(Offer(date=date, value=line["value"]))
            if end_date == start_date:
                break
            start_date = end_date
            self.amortization = [item for item in self.amortization if item.date != start_date]
            self.coupons = [item for item in self.coupons if item.date != start_date]
            self.offers = [item for item in self.offers if item.date != start_date]

    @property
    def expiration_date(self) -> datetime.date:
        return max(item.date for item in self.amortization + self.coupons + self.offers)

    def next_offer(self, date_from: T.Optional[datetime.date] = None) -> T.Optional[Offer]:
        date_from = date_from or datetime.date.today()
        result = [offer for offer in self.offers if offer.date >= date_from]
        return result[0] if len(result) > 0 else None
    
    def has_next_offer(self, date_from: T.Optional[datetime.date] = None) -> bool:
        return self.next_offer(date_from=date_from) is not None

    def next_offer_date(self, date_from: T.Optional[datetime.date] = None) -> T.Optional[datetime.date]:
        offer = self.next_offer(date_from=date_from)
        return offer.date if offer is not None else None
