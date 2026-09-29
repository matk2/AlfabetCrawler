from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

BOT_NAME = "AlfabetCrawler"
SPIDER_MODULES = ["AlfabetCrawler.spiders"]
NEWSPIDER_MODULE = "AlfabetCrawler.spiders"

LOG_LEVEL = "INFO"
USER_AGENT = "Firefox (Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36)"

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 0.5

ITEM_PIPELINES = {
    "AlfabetCrawler.pipelines.UniqueTopicPipeline": 1,
    "AlfabetCrawler.pipelines.NamedFilesPipeline": 100,
    "AlfabetCrawler.pipelines.NamedImagesPipeline": 200,
    "AlfabetCrawler.pipelines.MarkdownPipeline": 300,
    "AlfabetCrawler.pipelines.PersistentJsonlPipeline": 400,
}

FILES_STORE = str(PROJECT_ROOT / "Output/downloaded_files")
IMAGES_STORE = str(PROJECT_ROOT / "Output/downloaded_images")
MARKDOWN_STORE = str(PROJECT_ROOT / "Output/Markdown")
JSONL_STORE = str(PROJECT_ROOT / "Output/alfabet_pages.jsonl")

HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 16000
HTTPCACHE_DIR = str(PROJECT_ROOT / "httpcache")
HTTPCACHE_IGNORE_HTTP_CODES = [404]
HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"
