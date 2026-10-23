import re
import unicodedata
from typing import Any

from scrapy import Spider
from scrapy.http import Response

from locations.hours import DAYS, DAYS_JP, OpeningHours, day_range
from locations.items import Feature

TIME_RANGE = re.compile(r"(AM|PM)?\s*(\d{1,2}:\d{2})\s*[〜~-]\s*(AM|PM)?\s*(\d{1,2}:\d{2})")
CLOSING_TIME = re.compile(r"(AM|PM)?\s*(\d{1,2}:\d{2})まで")


def to_24h(ampm: str | None, hhmm: str) -> str:
    hour, minute = map(int, hhmm.split(":"))
    if ampm == "PM" and hour < 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def parse_days(text: str) -> list[str] | None:
    """Return the weekdays named in text, [] if it names none, or None if it contains anything else (e.g. a date)."""
    # Public holidays and the days before them cannot be expressed per weekday, so they are ignored
    text = re.sub(r"祝(?:祭)?日の前日|祝前日|祝(?:祭)?日|祝|曜日|曜|[はと・\s]", "", text)
    days = []
    for name, named_days in (("毎日", DAYS), ("平日", DAYS[:5])):
        if name in text:
            days += named_days
            text = text.replace(name, "")
    for start, end in re.findall(r"([月火水木金土日])[〜~-]([月火水木金土日])", text):
        days += day_range(DAYS_JP[start], DAYS_JP[end])
    text = re.sub(r"[月火水木金土日][〜~-][月火水木金土日]", "", text)
    if not re.fullmatch(r"[月火水木金土日]*", text):
        return None
    return days + [DAYS_JP[char] for char in text]


def parse_opening_hours(text: str) -> OpeningHours | None:
    """Parse e.g. "AM10:00〜PM8:00（金土日祝はPM9:00まで営業しております）"; return None if any part is not understood."""
    day_hours = {}
    for part in (p.strip() for p in re.split(r"[()、。]", unicodedata.normalize("NFKC", text))):
        if not part:
            continue
        if times := TIME_RANGE.search(part):
            days = parse_days(part[: times.start()])
            if days == [] and not day_hours:
                days = DAYS  # the first time range without days applies to every day
            if not days or re.search(r"\d", part[times.end() :]):
                return None
            open_ampm, open_time, close_ampm, close_time = times.groups()
            day_hours.update(dict.fromkeys(days, [to_24h(open_ampm, open_time), to_24h(close_ampm, close_time)]))
        elif (
            (closing := CLOSING_TIME.search(part))
            and (days := parse_days(part[: closing.start()]))
            and not re.search(r"\d", part[closing.end() :])
        ):
            for day in days:
                if day not in day_hours:
                    return None
                day_hours[day] = [day_hours[day][0], to_24h(*closing.groups())]
        else:
            return None
    if not day_hours:
        return None
    opening_hours = OpeningHours()
    for day, (open_time, close_time) in day_hours.items():
        opening_hours.add_range(day, open_time, close_time)
    return opening_hours


class NishimatsuyaJPSpider(Spider):
    name = "nishimatsuya_jp"
    item_attributes = {"brand": "西松屋", "brand_wikidata": "Q11628761"}
    allowed_domains = ["www.24028.jp"]
    # The sitemap omits recently opened stores, so start from the store list of each prefecture
    start_urls = [f"https://www.24028.jp/tenpo/shoplist.php?cid={prefecture}&add=" for prefecture in range(1, 48)]

    def parse(self, response: Response, **kwargs: Any) -> Any:
        for link in response.xpath('//a[contains(@href, "detail.php?")]'):
            # Closed stores stay listed with the link text "○○店は閉店致しました"
            if "閉店" in link.xpath("string()").get():
                continue
            yield response.follow(link.attrib["href"], callback=self.parse_store)

    def parse_store(self, response: Response) -> Any:
        if not (branch := response.xpath('normalize-space(//div[@id="shop-title"]/text())').get()):
            return  # page for a closed or not yet opened store

        item = Feature()
        item["ref"] = re.search(r"doc=(\d+)", response.url).group(1)
        item["branch"] = branch
        item["addr_full"] = response.xpath('normalize-space(//th[contains(., "住")]/following-sibling::td[1])').get()
        item["phone"] = response.xpath('normalize-space(//th[text()="TEL"]/following-sibling::td[1])').get()
        item["website"] = response.url

        if coords := re.search(r"google\.maps\.LatLng\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", response.text):
            item["lat"], item["lon"] = coords.group(1), coords.group(2)

        hours = response.xpath('normalize-space(//th[text()="営業時間"]/following-sibling::td[1]/text())').get("")
        item["opening_hours"] = parse_opening_hours(hours)

        yield item
