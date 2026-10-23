from typing import Any, Iterable

from scrapy.http import TextResponse
from scrapy.spiders import SitemapSpider

from locations.items import Feature
from locations.structured_data_spider import StructuredDataSpider


class KinokuniyaJPSpider(SitemapSpider, StructuredDataSpider):
    name = "kinokuniya_jp"
    item_attributes = {"brand": "紀伊國屋書店", "brand_wikidata": "Q703227"}
    allowed_domains = ["store.kinokuniya.co.jp"]
    sitemap_urls = ["https://store.kinokuniya.co.jp/store-sitemap.xml"]
    sitemap_rules = [(r"/store/[^/]+/$", "parse_sd")]
    wanted_types = ["BookStore"]
    search_for_twitter = False

    def pre_process_data(self, ld_data: dict, **kwargs) -> None:
        for rule in ld_data.get("openingHoursSpecification", []):
            rule["dayOfWeek"] = [day.replace("Thuesday", "Tuesday") for day in rule.get("dayOfWeek", [])]

    def post_process_item(
        self, item: Feature, response: TextResponse, ld_data: dict, **kwargs: Any
    ) -> Iterable[Feature]:
        item["ref"] = response.url.rstrip("/").rsplit("/", 1)[-1]
        item["branch"] = item.pop("name").removeprefix("紀伊國屋書店").strip()
        # addressLocality holds the city and the street address together
        address = ld_data.get("address", {})
        item["addr_full"] = "".join(
            address.get(key, "") for key in ("addressRegion", "addressLocality", "streetAddress")
        )
        item["city"] = item["street_address"] = None
        yield item
