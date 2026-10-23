import re
from typing import Any, Iterable

from scrapy.http import TextResponse
from scrapy.spiders import SitemapSpider

from locations.categories import Categories, apply_category
from locations.items import Feature
from locations.structured_data_spider import StructuredDataSpider

ASAHIYA = {"brand": "旭屋書店", "brand_wikidata": "Q11511670", "name": "旭屋書店"}


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
        # Closed stores keep their page, with the status "9月30日をもって閉店いたしました" in place of today's hours.
        # A notice of a future closure ("閉店いたします") is kept.
        status = response.xpath('string(//div[@class="openDate"]/p[contains(@class, "status")])').get("")
        if re.search(r"閉店(?:いた)?しました", status):
            return

        name = item.pop("name", None) or ""
        if name.startswith("旭屋書店"):
            item.update(ASAHIYA)
            apply_category(Categories.SHOP_BOOKS, item)
            item["branch"] = name.removeprefix("旭屋書店").strip()
        elif name.startswith("紀伊國屋書店"):
            item["branch"] = name.removeprefix("紀伊國屋書店").strip()
        elif name.startswith("紀伊國屋"):
            # 紀伊國屋ホール and 紀伊國屋サザンシアター are theatres
            return
        elif name:
            item["branch"] = name

        address = ld_data.get("address") or {}
        locality, street = address.get("addressLocality") or "", address.get("streetAddress") or ""
        if addr_full := "".join((address.get("addressRegion") or "", locality, street)):
            item["addr_full"] = addr_full
        # Some stores put the town and block number in addressLocality
        if re.search(r"\d", locality) or re.match(r"\d", street):
            item.pop("city", None)
            item.pop("street_address", None)
        yield item
