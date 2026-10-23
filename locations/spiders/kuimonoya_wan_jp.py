import json
from typing import Any

from scrapy import Spider
from scrapy.http import Response

from locations.dict_parser import DictParser
from locations.hours import DAYS_EN, OpeningHours


class KuimonoyaWanJPSpider(Spider):
    name = "kuimonoya_wan_jp"
    item_attributes = {"brand": "くいもの屋わん", "brand_wikidata": "Q109653563"}
    allowed_domains = ["search.oizumifoods.co.jp"]
    start_urls = ["https://search.oizumifoods.co.jp/"]
    dataset_attributes = {"source": "api", "api": "can-ly.com"}

    def next_data(self, response: Response) -> dict:
        return json.loads(response.xpath('//script[@id="__NEXT_DATA__"]/text()').get())["props"]["pageProps"]

    def parse(self, response: Response, **kwargs: Any) -> Any:
        # The Can-ly store locator lists all of the operator's brands by prefecture
        for area in self.next_data(response)["areas"]["content"]["largeItems"]:
            for prefecture in area["middleItems"]:
                yield response.follow(f"/{prefecture['label']}/", callback=self.parse_prefecture)

    def parse_prefecture(self, response: Response, page: int = 1) -> Any:
        data = self.next_data(response)
        for shop in data["shops"]:
            if shop["brand"]["name"] != "くいもの屋わん" or shop["openStatus"] != "IS_ALREADY_OPEN":
                continue
            item = DictParser.parse(shop)
            item["ref"] = shop["storeCode"]
            item["branch"] = shop["nameKanji"].split("くいもの屋わん")[-1].strip()
            item["addr_full"] = shop["address"]
            item["postcode"] = shop["zipCode"]
            item["phone"] = shop["tel"]
            item["website"] = f"https://search.oizumifoods.co.jp/detail/{shop['storeCode']}/"

            item["opening_hours"] = OpeningHours()
            for day_hours in shop.get("businessHours") or []:
                if day_hours["name"].title() in DAYS_EN:
                    item["opening_hours"].add_range(
                        day_hours["name"], day_hours["openTime"], day_hours["closeTime"], "%H:%M:%S"
                    )

            yield item

        if page < data["maxPage"]:
            yield response.follow(
                f"{response.url.split('?')[0]}?page={page + 1}",
                callback=self.parse_prefecture,
                cb_kwargs={"page": page + 1},
            )
