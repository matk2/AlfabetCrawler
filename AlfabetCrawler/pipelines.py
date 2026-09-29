import logging
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urldefrag, unquote, urlparse

from scrapy.exceptions import DropItem
from scrapy.pipelines.files import FilesPipeline
from scrapy.pipelines.images import ImagesPipeline

from AlfabetCrawler.html_to_markdown import html_to_markdown


logger = logging.getLogger(__name__)


def _safe_path_component(value):
    decoded = unquote(value)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", decoded).strip(" ._")
    return safe or "topic"


def topic_markdown_path(source_url):
    parsed = urlparse(source_url)
    source_path = PurePosixPath(parsed.path)
    directories = [
        _safe_path_component(part)
        for part in source_path.parts
        if part not in {"/", ".", ".."}
    ]
    filename = directories.pop() if directories else "index"
    suffix = PurePosixPath(filename).suffix
    stem = filename[:-len(suffix)] if suffix else filename

    if parsed.query:
        query_hash = hashlib.sha256(parsed.query.encode("utf-8")).hexdigest()[:8]
        stem = f"{stem}-{query_hash}"

    return PurePosixPath("topics", *directories, f"{stem or 'topic'}.md")


class OriginalNameMixin:
    def file_path(self, request, response=None, info=None, item=None):
        parsed = urlparse(request.url)
        directories = [
            _safe_path_component(part)
            for part in PurePosixPath(parsed.path).parts
            if part not in {"/", ".", ".."}
        ]
        filename = directories.pop() if directories else "download"

        if parsed.query:
            suffix = PurePosixPath(filename).suffix
            stem = filename[:-len(suffix)] if suffix else filename
            query_hash = hashlib.sha256(parsed.query.encode("utf-8")).hexdigest()[:8]
            filename = f"{stem}-{query_hash}{suffix}"

        host = _safe_path_component(parsed.hostname or "media")
        return PurePosixPath(host, *directories, filename).as_posix()


class NamedFilesPipeline(OriginalNameMixin, FilesPipeline):
    def media_failed(self, failure, request, info):
        logger.debug("Skipping unavailable file: %s", request.url)
        return None


class NamedImagesPipeline(OriginalNameMixin, ImagesPipeline):
    def media_failed(self, failure, request, info):
        logger.debug("Skipping unavailable image: %s", request.url)
        return None


class MarkdownPipeline:
    def __init__(self, markdown_store, images_store, files_store, project_root):
        self.markdown_store = Path(markdown_store)
        self.images_store = Path(images_store)
        self.files_store = Path(files_store)
        self.project_root = Path(project_root)

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        return cls(
            markdown_store=settings.get("MARKDOWN_STORE"),
            images_store=settings.get("IMAGES_STORE"),
            files_store=settings.get("FILES_STORE"),
            project_root=settings.get("PROJECT_ROOT"),
        )

    def _local_media_paths(self, item, markdown_path):
        media_paths = {}
        media_results = (
            (item.get("images", []), self.images_store),
            (item.get("files", []), self.files_store),
        )

        for results, store in media_results:
            for result in results:
                if not isinstance(result, dict):
                    continue
                
                source_url = result.get("url")
                stored_path = result.get("path")
                if not source_url or not stored_path:
                    continue

                relative_parts = [
                    part
                    for part in PurePosixPath(stored_path).parts
                    if part not in {"/", ".", ".."}
                ]
                media_file = store.joinpath(*relative_parts)
                media_paths[source_url] = Path(
                    os.path.relpath(media_file, markdown_path.parent)
                ).as_posix()

        return media_paths

    def _topic_link(self, source_url, target_url, markdown_path):
        source = urlparse(source_url)
        target = urlparse(target_url)
        if (
            target.scheme not in {"http", "https"}
            or target.hostname != source.hostname
            or not target.path.lower().endswith(".html")
        ):
            return target_url

        target_markdown_path = self.markdown_store.joinpath(
            *topic_markdown_path(target_url).parts
        )
        relative_path = Path(
            os.path.relpath(target_markdown_path, markdown_path.parent)
        ).as_posix()
        fragment = f"#{target.fragment}" if target.fragment else ""

        if target_markdown_path == markdown_path and fragment:
            return fragment
        return f"{relative_path}{fragment}"

    def process_item(self, item):
        source_url = item["url"]
        relative_path = topic_markdown_path(source_url)
        markdown_path = self.markdown_store.joinpath(*relative_path.parts)
        media_paths = self._local_media_paths(item, markdown_path)
        content = html_to_markdown(
            item.pop("content_html", ""),
            source_url,
            media_paths,
            lambda target_url: self._topic_link(
                source_url,
                target_url,
                markdown_path,
            ),
        )

        title = json.dumps(item.get("title", ""), ensure_ascii=False)
        source = json.dumps(source_url, ensure_ascii=False)
        document = (
            f"---\ntitle: {title}\nsource_url: {source}\n---\n\n"
            f"{content}\n"
        )

        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(document, encoding="utf-8")
        item["content"] = content
        item["markdown_file"] = markdown_path.relative_to(
            self.project_root
        ).as_posix()
        return item


class UniqueTopicPipeline:
    def __init__(self):
        self.seen_urls = set()

    def process_item(self, item):
        topic_url = urldefrag(item["url"]).url
        if topic_url in self.seen_urls:
            raise DropItem(f"Duplicate topic URL: {topic_url}")

        self.seen_urls.add(topic_url)
        return item


class PersistentJsonlPipeline:
    def __init__(self, jsonl_store):
        self.jsonl_store = Path(jsonl_store)
        self.records = {}

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get("JSONL_STORE"))

    def open_spider(self, spider):
        if not self.jsonl_store.exists():
            return

        with self.jsonl_store.open(encoding="utf-8") as feed:
            for line_number, line in enumerate(feed, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    topic_url = urldefrag(record["url"]).url
                except (json.JSONDecodeError, KeyError, TypeError) as error:
                    raise ValueError(
                        f"Invalid JSONL record at {self.jsonl_store}:{line_number}"
                    ) from error

                self.records[topic_url] = record

    def process_item(self, item):
        topic_url = urldefrag(item["url"]).url
        self.records[topic_url] = dict(item)
        return item

    def close_spider(self, spider):
        self.jsonl_store.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.jsonl_store.parent,
                prefix=f".{self.jsonl_store.name}.",
                suffix=".tmp",
                delete=False,
            ) as feed:
                temporary_path = Path(feed.name)
                for record in self.records.values():
                    feed.write(json.dumps(record, ensure_ascii=False) + "\n")
                feed.flush()
                os.fsync(feed.fileno())

            os.replace(temporary_path, self.jsonl_store)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise