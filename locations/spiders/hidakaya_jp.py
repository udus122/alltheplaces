import re
from typing import Any

from scrapy import Spider
from scrapy.http import Response

from locations.hours import DAYS_JP, OpeningHours
from locations.items import Feature


class HidakayaJPSpider(Spider):
    name = "hidakaya_jp"
    item_attributes = {"brand": "日高屋", "brand_wikidata": "Q11326050"}
    allowed_domains = ["hidakaya.hiday.co.jp"]
    start_urls = ["https://hidakaya.hiday.co.jp/hits/ja/shop/1/list.html"]

    def parse(self, response: Response, **kwargs: Any) -> Any:
        for url in response.xpath('//a[contains(@href, "/detail/")]/@href').getall():
            yield response.follow(url.split("?")[0], callback=self.parse_store)

    def parse_store(self, response: Response) -> Any:
        item = Feature()
        item["ref"] = re.search(r"/detail/(\d+)\.html", response.url).group(1)
        item["branch"] = (
            response.xpath('normalize-space(//nav[@class="breadcrumb"]//li[last()])').get().removeprefix("日高屋 ")
        )
        address = response.xpath('normalize-space(//th[text()="所在地"]/following-sibling::td[1])').get("")
        if postcode := re.match(r"〒\s*(\d{3}-\d{4})\s*", address):
            item["postcode"] = postcode.group(1)
            address = address[postcode.end() :]
        item["addr_full"] = address
        item["phone"] = response.xpath('normalize-space(//td[@class="tel"])').get()
        item["website"] = response.url

        if lat := re.search(r"var gIdo = ([-\d.]+);", response.text):
            item["lat"] = lat.group(1)
        if lon := re.search(r"var gKeido = ([-\d.]+);", response.text):
            item["lon"] = lon.group(1)

        item["opening_hours"] = OpeningHours()
        for row in response.xpath('//th[text()="営業時間"]/ancestor::table[1]//td/text()').getall():
            if hours := re.search(r"(\S+曜日)\s+(\d{1,2}:\d{2})-翌?(\d{1,2}:\d{2})", row.replace("\xa0", " ")):
                day, open_time, close_time = hours.groups()
                if day in DAYS_JP:
                    item["opening_hours"].add_range(DAYS_JP[day], open_time, close_time)

        yield item
