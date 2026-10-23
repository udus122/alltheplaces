import json
import re
from typing import Any

from scrapy import Spider
from scrapy.http import Response

from locations.categories import Categories, apply_category
from locations.hours import DAYS, DAYS_JP, OpeningHours
from locations.items import Feature


class ShichirinboJPSpider(Spider):
    name = "shichirinbo_jp"
    item_attributes = {"brand": "七輪房"}
    allowed_domains = ["www.anrakutei.co.jp"]
    start_urls = ["https://www.anrakutei.co.jp/7_rinbo/map/map_menu.php"]

    def parse(self, response: Response, **kwargs: Any) -> Any:
        for store_id in set(re.findall(r"open_map\('(\d+)'\)", response.text)):
            yield response.follow(f"map_main.php?tenpocd={store_id}", callback=self.parse_store)

    def parse_store(self, response: Response) -> Any:
        marker = json.loads(re.search(r"var markerData = (\[.*?\]);", response.text).group(1))[0]
        name, phone = re.fullmatch(r"<b>(.+?)</b><br>電話番号\s*(.+)", marker["name"]).groups()

        item = Feature()
        item["ref"] = marker["tenpocd"]
        item["branch"] = name.removeprefix("七輪房").strip()
        item["lat"] = marker["lat"]
        item["lon"] = marker["lng"]
        item["addr_full"] = response.xpath(
            'normalize-space(//td[contains(., "住　　所")]/following-sibling::td[1])'
        ).get()
        item["phone"] = phone
        item["website"] = response.url

        # The first line applies to every day, later lines such as "金・土 午前11:00〜24:00" override days
        day_hours = {}
        for line in response.xpath('//td[contains(text(), "　営業時間")]/following-sibling::td[1]/text()').getall():
            if times := re.search(r"(\d{1,2}:\d{2})\s*[〜～~-]\s*(?:深夜|翌)?(\d{1,2}:\d{2})", line):
                days = [DAYS_JP[char] for char in line[: times.start()] if char in "月火水木金土日"] or DAYS
                day_hours.update(dict.fromkeys(days, times.groups()))
        if day_hours:
            item["opening_hours"] = OpeningHours()
            for day, (open_time, close_time) in day_hours.items():
                item["opening_hours"].add_range(day, open_time, close_time)

        apply_category(Categories.RESTAURANT, item)
        item["extras"]["cuisine"] = "yakiniku"

        yield item
