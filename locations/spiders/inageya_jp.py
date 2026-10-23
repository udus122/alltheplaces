import re
from typing import Any

from scrapy import Spider
from scrapy.http import Response

from locations.categories import Categories, apply_category
from locations.hours import DAYS, OpeningHours
from locations.items import Feature


class InageyaJPSpider(Spider):
    name = "inageya_jp"
    item_attributes = {"brand": "いなげや", "brand_wikidata": "Q17193392"}
    allowed_domains = ["stores.inageya.co.jp"]
    start_urls = ["https://stores.inageya.co.jp/"]
    store_formats = {"ina21": "いなげやina21", "bloomingbloomy": "blooming bloomy"}

    def parse(self, response: Response, **kwargs: Any) -> Any:
        for url in set(response.xpath('//a[contains(@href, "store/?s=")]/@href').getall()):
            yield response.follow(url, callback=self.parse_store)

    def parse_store(self, response: Response) -> Any:
        store = response.xpath("//comment[@store_name]")
        item = Feature()
        item["ref"] = store.xpath("@local_store_code").get()
        branch = store.xpath("@store_name").get().removeprefix("いなげや")
        item["name"] = "いなげや"
        for prefix, name in self.store_formats.items():
            if branch.startswith(prefix):
                item["name"] = name
                branch = branch.removeprefix(prefix)
        item["branch"] = branch
        item["lat"] = store.xpath("@store_lat").get()
        item["lon"] = store.xpath("@store_lng").get()
        address = response.xpath('//dt[text()="住所"]/following-sibling::dd[1]/text()').getall()
        if address and (postcode := re.fullmatch(r"〒\s*(\d{3}-\d{4})", address[0].strip())):
            item["postcode"] = postcode.group(1)
            address = address[1:]
        item["addr_full"] = "".join(line.strip() for line in address if line.strip())
        item["phone"] = response.xpath('normalize-space(//dt[text()="TEL"]/following-sibling::dd[1])').get()
        item["website"] = response.url

        hours = response.xpath('normalize-space(//dt[text()="営業時間"]/following-sibling::dd[1]//text())').get("")
        if times := re.fullmatch(r"(\d{1,2}:\d{2})\s*[～〜~-]\s*(\d{1,2}:\d{2})", hours):
            item["opening_hours"] = OpeningHours()
            item["opening_hours"].add_days_range(DAYS, *times.groups())

        apply_category(Categories.SHOP_SUPERMARKET, item)

        yield item
