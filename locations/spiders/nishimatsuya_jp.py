import re
from typing import Any

from scrapy.http import Response
from scrapy.spiders import SitemapSpider

from locations.hours import DAYS, OpeningHours
from locations.items import Feature


class NishimatsuyaJPSpider(SitemapSpider):
    name = "nishimatsuya_jp"
    item_attributes = {"brand": "西松屋", "brand_wikidata": "Q11628761"}
    allowed_domains = ["www.24028.jp"]
    sitemap_urls = ["https://www.24028.jp/sitemap.xml"]
    sitemap_rules = [(r"/tenpo/detail\.php\?cid=\d+&doc=\d+$", "parse")]

    def parse(self, response: Response, **kwargs: Any) -> Any:
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
        if times := re.fullmatch(r"(AM|PM)?(\d{1,2}:\d{2})\s*[〜～~-]\s*(AM|PM)?(\d{1,2}:\d{2})", hours):
            open_ampm, open_time, close_ampm, close_time = times.groups()
            item["opening_hours"] = OpeningHours()
            if open_ampm and close_ampm:
                item["opening_hours"].add_days_range(
                    DAYS, open_ampm + open_time, close_ampm + close_time, time_format="%p%I:%M"
                )
            else:
                item["opening_hours"].add_days_range(DAYS, open_time, close_time)

        yield item
