import re
from typing import Any

from scrapy import Request, Spider
from scrapy.http import Response

from locations.categories import Categories, apply_category
from locations.hours import DAYS_JP, OpeningHours
from locations.items import Feature


class KagonoyaJPSpider(Spider):
    name = "kagonoya_jp"
    item_attributes = {"brand": "かごの屋", "brand_wikidata": "Q122661918"}
    allowed_domains = ["kagonoya.food-kr.com"]
    start_urls = ["https://kagonoya.food-kr.com/robots.txt"]

    def parse(self, response: Response, **kwargs: Any) -> Any:
        # Each store is a WordPress subsite whose sitemap is listed in robots.txt
        for store_id in re.findall(
            r"^Sitemap: https://kagonoya\.food-kr\.com/(\d+)/sitemap_index\.xml$", response.text, re.M
        ):
            yield Request(
                f"https://kagonoya.food-kr.com/{store_id}/", callback=self.parse_store, cb_kwargs={"ref": store_id}
            )

    def parse_store(self, response: Response, ref: str) -> Any:
        # Some subsites are for the operator's other brands
        if not (
            title := re.search(r"かごの[屋や]\s*(.+)", response.xpath("normalize-space(//title)").get().split("|")[0])
        ):
            return

        item = Feature()
        item["ref"] = ref
        item["branch"] = title.group(1).strip()
        item["addr_full"] = "".join(
            line.strip()
            for line in response.xpath('//dt[text()="住所"]/following-sibling::dd[1]/text()').getall()
            if line.strip()
        )
        if phone := re.search(
            r"[\d-]{10,}", response.xpath('normalize-space(//dt[text()="電話番号"]/following-sibling::dd[1])').get("")
        ):
            item["phone"] = phone.group()
        item["website"] = response.url

        if coords := re.search(r"maps\.google\.com/maps\?[^\"']*q=([-\d.]+),([-\d.]+)", response.text):
            item["lat"], item["lon"] = coords.groups()

        item["opening_hours"] = OpeningHours()
        for day_hours in response.xpath('//div[@class="open_item"]'):
            if not (day := DAYS_JP.get(day_hours.xpath('normalize-space(div[@class="open_week"])').get().rstrip("："))):
                continue
            hours = day_hours.xpath('string(div[@class="open_hours"])').get()
            if "定休" in hours or "休業" in hours:
                item["opening_hours"].set_closed(day)
            for open_time, close_time in re.findall(r"(\d{1,2}:\d{2})\s*[〜～~-]\s*(\d{1,2}:\d{2})", hours):
                item["opening_hours"].add_range(day, open_time, close_time)

        # NSI lists this brand by region only, so its tags are not applied by the NSI pipeline
        apply_category(Categories.RESTAURANT, item)
        item["extras"]["cuisine"] = "japanese"

        yield item
