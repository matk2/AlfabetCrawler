from pathlib import PurePosixPath
from urllib.parse import urldefrag, urljoin, urlparse

import scrapy
from scrapy.linkextractors import LinkExtractor


class AlfabetSpider(scrapy.Spider):
    name = "alfabet"
    allowed_domains = ["documentation.alfabet.com"]
    start_urls = ["https://documentation.alfabet.com/"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.link_extractor = LinkExtractor(
            allow_domains=self.allowed_domains,
            deny_extensions=[
                "zip", "webp", "gif", "jpg", "jpeg", "png",
                "svg", "pdf", "css", "js", "ico",
                "woff", "woff2", "ttf", "mp4",
            ],
        )

    @staticmethod
    def _resolve_media_url(base_url, candidate):
        if not candidate:
            return None

        absolute_url = urljoin(base_url, candidate.strip())
        parsed_url = urlparse(absolute_url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.path
            or parsed_url.path.endswith("/")
            or PurePosixPath(parsed_url.path).name in {"", ".", ".."}
        ):
            return None

        return absolute_url, parsed_url

    def parse(self, response):
        base_href = response.css("base::attr(href)").get()
        media_base_url = response.urljoin(base_href) if base_href else response.url

        main_area = response.css("#Main-Area")
        if not main_area:
            self.logger.warning("Skipping topic without #Main-Area: %s", response.url)
        else:
            image_urls = []
            file_urls = []

            for image in main_area.css("img"):
                candidates = (image.attrib.get("src"), image.attrib.get("data-src"))
                resolved = None
                for candidate in candidates:
                    resolved = self._resolve_media_url(media_base_url, candidate)
                    if resolved is not None:
                        break

                if resolved is None:
                    continue

                absolute_url, parsed_url = resolved
                if parsed_url.path.lower().endswith(".svg"):
                    file_urls.append(absolute_url)
                else:
                    image_urls.append(absolute_url)

            for url in main_area.css("a::attr(href)").getall():
                resolved = self._resolve_media_url(media_base_url, url)
                if resolved is None:
                    continue

                absolute_url, parsed_url = resolved
                if parsed_url.path.lower().endswith((".pdf", ".svg", ".gif")):
                    file_urls.append(absolute_url)

            title = main_area.css("h1").xpath("string(.)").get(default="").strip()
            if not title:
                title = response.css("title::text").get(default="").strip()

            yield {
                "url": response.url,
                "title": title,
                "content_html": main_area.get(),
                "image_urls": list(dict.fromkeys(image_urls)),
                "file_urls": list(dict.fromkeys(file_urls)),
            }

        for link in self.link_extractor.extract_links(response):
            clean_url, _ = urldefrag(link.url)
            yield response.follow(clean_url, callback=self.parse)