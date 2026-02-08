import typing as T

import dataclasses
import datetime

from . import tickers
from . import utils


logger = utils.initialize_logging(__file__)


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
    name: str
    shortname: str
    issue_date: datetime.date
    mat_date: T.Optional[datetime.date]
    initial_face_value: float
    start_date_moex: T.Optional[datetime.date]
    early_repayment: bool
    days_to_redemption: T.Optional[int]
    issue_size: int
    face_value: float
    is_qualified_investors: bool
    coupon_frequency: T.Optional[int]
    evening_session: bool
    coupon_percent: T.Optional[float]
    amortization: list[Amortization]
    coupons: list[Coupon]
    offers: list[Offer]

    def __init__(self, ticker: tickers.Ticker):
        try:
            self.secid = ticker.secid
            self.shortname = ticker.shortname
            ticker_info = tickers.get_ticker_info_dict(ticker.secid)
            self.name = ticker_info["NAME"]
            self.issue_date = datetime.date.fromisoformat(ticker_info["ISSUEDATE"])
            self.mat_date = datetime.date.fromisoformat(ticker_info["MATDATE"]) if "MATDATE" in ticker_info else None
            self.initial_face_value = float(ticker_info["INITIALFACEVALUE"])
            self.start_date_moex = datetime.date.fromisoformat(ticker_info["STARTDATEMOEX"]) \
                if "STARTDATEMOEX" in ticker_info else None
            self.early_repayment = bool(ticker_info.get("EARLYREPAYMENT", False))
            self.days_to_redemption = int(ticker_info["DAYSTOREDEMPTION"]) if "DAYSTOREDEMPTION" in ticker_info else None
            self.issue_size = int(ticker_info["ISSUESIZE"])
            self.face_value = float(ticker_info["FACEVALUE"])
            self.is_qualified_investors = bool(ticker_info["ISQUALIFIEDINVESTORS"])
            self.coupon_frequency = int(ticker_info["COUPONFREQUENCY"]) if "COUPONFREQUENCY" in ticker_info else None
            self.evening_session = bool(ticker_info.get("EVENINGSESSION", False))
            self.coupon_percent = float(ticker_info["COUPONPERCENT"]) if "COUPONPERCENT" in ticker_info else None
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
            original_values = [item.value for item in self.amortization]
            amortization_sum = sum(original_values)
            if abs(amortization_sum - self.initial_face_value) > 1e-9 and len(original_values) > 1:
                values = [value / amortization_sum * self.initial_face_value for value in original_values]
                rounded_values = [round(value + 1e-9, 2) for value in values]
                for original_value, rounded_value in zip(original_values, rounded_values):
                    if abs(original_value - rounded_value) > 1e-9:
                        logger.error(f"Original value {original_value} is not equal to rounded value {rounded_value}")
                        raise ValueError(f"Amortization sum {amortization_sum} is greater than initial face value {self.initial_face_value}")
                for amortization_item, value in zip(self.amortization, values):
                    amortization_item.value = value
        except Exception as e:
            logger.error(f"{ticker.secid} ({ticker.shortname}): {e}")
            raise e

    @property
    def expiration_date(self) -> datetime.date:
        return max(item.date for item in self.amortization + self.coupons + self.offers)

    def __repr__(self) -> str:
        lines = [
            f"Bond({self.secid})",
            f"  name:                  {self.name}",
            f"  shortname:             {self.shortname}",
            f"  issue_date:            {self.issue_date}",
            f"  mat_date:              {self.mat_date}",
            f"  initial_face_value:    {self.initial_face_value}",
            f"  face_value:            {self.face_value}",
            f"  start_date_moex:       {self.start_date_moex}",
            f"  early_repayment:       {self.early_repayment}",
            f"  days_to_redemption:    {self.days_to_redemption}",
            f"  issue_size:            {self.issue_size:,}",
            f"  is_qualified_investors:{' ' if not self.is_qualified_investors else ''}{self.is_qualified_investors}",
            f"  coupon_frequency:      {self.coupon_frequency}",
            f"  evening_session:       {self.evening_session}",
            f"  coupon_percent:        {self.coupon_percent}",
        ]
        if self.amortization:
            lines.append(f"  amortization ({len(self.amortization)}):")
            for a in self.amortization:
                lines.append(f"    {a.date}  value={a.value}  face={a.initialfacevalue}")
        if self.coupons:
            lines.append(f"  coupons ({len(self.coupons)}):")
            for c in self.coupons:
                lines.append(f"    {c.date}  value={c.value}")
        if self.offers:
            lines.append(f"  offers ({len(self.offers)}):")
            for o in self.offers:
                lines.append(f"    {o.date}  value={o.value}")
        return "\n".join(lines)

    def next_offer(self, date_from: T.Optional[datetime.date] = None) -> T.Optional[Offer]:
        date_from = date_from or datetime.date.today()
        result = [offer for offer in self.offers if offer.date >= date_from]
        return result[0] if len(result) > 0 else None
    
    def has_next_offer(self, date_from: T.Optional[datetime.date] = None) -> bool:
        return self.next_offer(date_from=date_from) is not None

    def next_offer_date(self, date_from: T.Optional[datetime.date] = None) -> T.Optional[datetime.date]:
        offer = self.next_offer(date_from=date_from)
        return offer.date if offer is not None else None
