import re
from typing import Any, Iterable

from scrapy.http import TextResponse
from scrapy.spiders import SitemapSpider

from locations.categories import Categories, apply_category
from locations.items import Feature
from locations.structured_data_spider import StructuredDataSpider

ASAHIYA = {"brand": "旭屋書店", "brand_wikidata": "Q11511670"}


class KinokuniyaJPSpider(SitemapSpider, StructuredDataSpider):
    name = "kinokuniya_jp"
    item_attributes = {"brand": "紀伊國屋書店", "brand_wikidata": "Q703227"}
    allowed_domains = ["store.kinokuniya.co.jp"]
    sitemap_urls = ["https://store.kinokuniya.co.jp/store-sitemap.xml"]
    sitemap_rules = [(r"/store/([^/]+)/$", "parse_sd")]
    wanted_types = ["BookStore"]
    search_for_twitter = False

    def pre_process_data(self, ld_data: dict, **kwargs) -> None:
        rules = ld_data.get("openingHoursSpecification") or []
        if isinstance(rules, dict):
            rules = ld_data["openingHoursSpecification"] = [rules]
        for rule in rules:
            days = rule.get("dayOfWeek") or []
            if isinstance(days, str):
                days = [days]
            rule["dayOfWeek"] = [day.replace("Thuesday", "Tuesday") for day in days]
        if isinstance(payment := ld_data.get("paymentAccepted"), str):
            ld_data["paymentAccepted"] = payment.split("、")

    def post_process_item(
        self, item: Feature, response: TextResponse, ld_data: dict, **kwargs: Any
    ) -> Iterable[Feature]:
        name = item.pop("name")
        if name.startswith("旭屋書店"):
            item.update(ASAHIYA)
            apply_category(Categories.SHOP_BOOKS, item)
            item["branch"] = name.removeprefix("旭屋書店").strip()
        elif name.startswith("紀伊國屋書店"):
            item["branch"] = name.removeprefix("紀伊國屋書店").strip()
        elif name.startswith("紀伊國屋"):
            # 紀伊國屋ホール and 紀伊國屋サザンシアター are theatres
            return
        else:
            item["branch"] = name

        address = ld_data.get("address", {})
        item["addr_full"] = "".join(
            address.get(key, "") for key in ("addressRegion", "addressLocality", "streetAddress")
        )
        # Some stores put the town and block number in addressLocality
        if re.search(r"\d", address.get("addressLocality", "")) or re.match(r"\d", address.get("streetAddress", "")):
            item.pop("city", None)
            item.pop("street_address", None)
        yield item
