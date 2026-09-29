import os
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from scrapy.http import HtmlResponse, Request
from scrapy.exceptions import DropItem

from AlfabetCrawler.html_to_markdown import html_to_markdown
from AlfabetCrawler.pipelines import (
    MarkdownPipeline,
    OriginalNameMixin,
    PersistentJsonlPipeline,
    UniqueTopicPipeline,
    topic_markdown_path,
)
from AlfabetCrawler.spiders.Alfabet import AlfabetSpider


SOURCE_URL = "https://documentation.alfabet.com/11-13/en/topic.html"
IMAGE_URL = "https://documentation.alfabet.com/11-13/en/Images/diagram.png"
GIF_URL = "https://documentation.alfabet.com/11-13/en/Images/DefineRoles.gif"

TOPIC_HTML = """
<header><p>Site navigation</p><img src="/chrome.png"></header>
<main id="Main-Area" aria-label="Documentation topic">
  <h1>Topic title</h1>
  <p>Use <strong>bold text</strong>, <span class="Code">ObjectEvaluation</span>,
      and <span class="Code">ALFA_GLOBAL_CLASS_SETTINGS</span>.
     Read the <a href="next.html">next topic</a>.</p>
    <p><a href="#GS_Workflows_Preconf">Out-of-the-box workflow</a></p>
    <p><a href="https://support.example.com/help.html">External help</a></p>
  <ul><li>Parent item<ul><li>Nested item</li></ul></li></ul>
  <img src="Images/diagram.png" alt="Architecture diagram">
    <a href="Images/DefineRoles.gif"><img src="Images/Animation.png" alt="Roles animation"> Click here to see how.</a>
  <table><tr><th>Setting</th><th>Value</th></tr><tr><td>Mode</td><td>Access</td></tr></table>
  <ul class="dlt-accordion">
    <li class="dlt-accordion-item">
      <button class="dlt-accordion-title" aria-expanded="false">More details</button>
      <div class="dlt-accordion-content"><ol><li>First step
        <div class="orientationtext"><h4>Icon help</h4><p>Select an icon.</p></div>
      </li></ol></div>
    </li>
  </ul>
</main>
<footer>Site footer</footer>
"""


class MarkdownExportTests(unittest.TestCase):
    def test_jsonl_merge_retains_old_topics_and_replaces_recrawled_url(self):
        original_url = "https://documentation.alfabet.com/en/topic.html#old"
        other_url = "https://documentation.alfabet.com/en/other.html"
        updated_url = "https://documentation.alfabet.com/en/topic.html#new"

        with tempfile.TemporaryDirectory() as directory:
            feed_path = Path(directory) / "alfabet_pages.jsonl"
            feed_path.write_text(
                "".join(
                    json.dumps(record) + "\n"
                    for record in (
                        {"url": original_url, "title": "Old title"},
                        {"url": other_url, "title": "Unchanged topic"},
                    )
                ),
                encoding="utf-8",
            )

            pipeline = PersistentJsonlPipeline(feed_path)
            pipeline.open_spider(spider=None)
            updated_item = {"url": updated_url, "title": "Updated title"}
            pipeline.process_item(updated_item)
            pipeline.close_spider(spider=None)

            records = [
                json.loads(line)
                for line in feed_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(len(records), 2)
        records_by_url = {record["url"].split("#")[0]: record for record in records}
        self.assertEqual(records_by_url[original_url.split("#")[0]]["title"], "Updated title")
        self.assertEqual(records_by_url[other_url]["title"], "Unchanged topic")

    def test_jsonl_merge_deduplicates_existing_rows_and_keeps_query_urls_distinct(self):
        base_url = "https://documentation.alfabet.com/en/topic.html"
        queried_url = base_url + "?variant=two"

        with tempfile.TemporaryDirectory() as directory:
            feed_path = Path(directory) / "alfabet_pages.jsonl"
            feed_path.write_text(
                "".join(
                    json.dumps(record) + "\n"
                    for record in (
                        {"url": base_url + "#first", "title": "Old"},
                        {"url": base_url + "#second", "title": "Duplicate old row"},
                    )
                ),
                encoding="utf-8",
            )

            pipeline = PersistentJsonlPipeline(feed_path)
            pipeline.open_spider(spider=None)
            pipeline.process_item({"url": queried_url, "title": "Query variant"})
            pipeline.close_spider(spider=None)
            records = [
                json.loads(line)
                for line in feed_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["title"], "Duplicate old row")
        self.assertEqual(records[1]["url"], queried_url)

    def test_unique_pipeline_drops_duplicate_urls_with_different_fragments(self):
        pipeline = UniqueTopicPipeline()
        first_item = {"url": "https://documentation.alfabet.com/en/topic.html#section-a"}
        duplicate_item = {"url": "https://documentation.alfabet.com/en/topic.html#section-b"}

        self.assertIs(pipeline.process_item(first_item), first_item)
        with self.assertRaises(DropItem):
            pipeline.process_item(duplicate_item)

    def test_spider_limits_topic_and_media_to_main_area(self):
        html = """
        <header><img src="/chrome.png"><a href="/nav.html">Nav</a></header>
        <main id="Main-Area"><h1>Topic</h1><img src="/topic.png">
                    <a href="guide.pdf">PDF</a><a href="animation.gif">Animation</a>
                    <a href="next.html">Next</a></main>
        """
        response = HtmlResponse(
            url=SOURCE_URL,
            request=Request(SOURCE_URL),
            body=html.encode("utf-8"),
            encoding="utf-8",
        )
        results = list(AlfabetSpider().parse(response))
        item = next(result for result in results if isinstance(result, dict))

        self.assertIn('id="Main-Area"', item["content_html"])
        self.assertEqual(
            item["image_urls"],
            ["https://documentation.alfabet.com/topic.png"],
        )
        self.assertEqual(
            item["file_urls"],
            [
                "https://documentation.alfabet.com/11-13/en/guide.pdf",
                "https://documentation.alfabet.com/11-13/en/animation.gif",
            ],
        )
        self.assertTrue(any(result.url.endswith("/nav.html") for result in results if isinstance(result, Request)))

    def test_spider_resolves_media_against_base_and_skips_directory_images(self):
        url = "https://documentation.alfabet.com/AlfabetAIAssistant.html"
        html = """
        <html><head><base href="/en/"></head><body>
          <main id="Main-Area"><h1>AI Assistant</h1>
            <img src="Images/assistant.png">
                        <img src="javascript:alert('bad')" data-src="Images/lazy.png">
            <img src="Images/">
            <a href="Images/guide.pdf">Guide</a>
                        <a href="javascript:alert('bad').pdf">Invalid guide</a>
          </main>
        </body></html>
        """
        response = HtmlResponse(
            url=url,
            request=Request(url),
            body=html.encode("utf-8"),
            encoding="utf-8",
        )

        item = next(
            result
            for result in AlfabetSpider().parse(response)
            if isinstance(result, dict)
        )

        self.assertEqual(
            item["image_urls"],
            [
                "https://documentation.alfabet.com/en/Images/assistant.png",
                "https://documentation.alfabet.com/en/Images/lazy.png",
            ],
        )
        self.assertEqual(
            item["file_urls"],
            ["https://documentation.alfabet.com/en/Images/guide.pdf"],
        )

    def test_converter_preserves_topic_structure_and_accordion_guidance(self):
        local_image = "../../../../downloaded_images/diagram.png"
        markdown = html_to_markdown(
            TOPIC_HTML,
            SOURCE_URL,
            {IMAGE_URL: local_image},
        )

        self.assertIn("# Topic title", markdown)
        self.assertIn("**bold text**", markdown)
        self.assertIn("`ObjectEvaluation`", markdown)
        self.assertIn("`ALFA_GLOBAL_CLASS_SETTINGS`", markdown)
        self.assertIn("- Parent item", markdown)
        self.assertIn("Nested item", markdown)
        self.assertIn(
            "[next topic](https://documentation.alfabet.com/11-13/en/next.html)",
            markdown,
        )
        self.assertIn(f"![Architecture diagram]({local_image})", markdown)
        self.assertIn("| Setting | Value |", markdown)
        self.assertIn("## More details", markdown)
        self.assertIn("First step", markdown)
        self.assertIn("Select an icon.", markdown)
        self.assertNotIn("Site navigation", markdown)
        self.assertNotIn("Site footer", markdown)

    def test_pipeline_writes_topic_with_local_media_references(self):
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            markdown_store = project_root / "Markdown"
            images_store = project_root / "downloaded_images"
            files_store = project_root / "downloaded_files"
            image_path = PurePosixPath(
                "documentation.alfabet.com/11-13/en/Images/diagram.png"
            )
            gif_path = PurePosixPath(
                "documentation.alfabet.com/11-13/en/Images/DefineRoles.gif"
            )
            stored_image = images_store / Path(*image_path.parts)
            stored_image.parent.mkdir(parents=True)
            stored_image.write_bytes(b"image fixture")
            gif_store = files_store / Path(*gif_path.parts)
            gif_store.parent.mkdir(parents=True)
            gif_store.write_bytes(b"gif fixture")

            pipeline = MarkdownPipeline(
                markdown_store,
                images_store,
                files_store,
                project_root,
            )
            item = {
                "url": SOURCE_URL,
                "title": "Topic title",
                "content_html": TOPIC_HTML,
                "images": [{"url": IMAGE_URL, "path": image_path.as_posix()}],
                "files": [{"url": GIF_URL, "path": gif_path.as_posix()}],
            }

            result = pipeline.process_item(item)
            output_path = markdown_store / "topics/11-13/en/topic.md"
            output = output_path.read_text(encoding="utf-8")
            expected_image_reference = Path(
                os.path.relpath(stored_image, output_path.parent)
            ).as_posix()
            expected_gif_reference = Path(
                os.path.relpath(gif_store, output_path.parent)
            ).as_posix()

            self.assertTrue(output_path.is_file())
            self.assertIn('source_url: "' + SOURCE_URL + '"', output)
            self.assertIn(
                f"![Architecture diagram]({expected_image_reference})",
                output,
            )
            self.assertIn(
                f"]({expected_gif_reference})",
                output,
            )
            self.assertIn("[next topic](next.md)", output)
            self.assertIn(
                "[Out-of-the-box workflow](#GS_Workflows_Preconf)",
                output,
            )
            self.assertIn(
                "[External help](https://support.example.com/help.html)",
                output,
            )
            self.assertEqual(
                result["markdown_file"],
                "Markdown/topics/11-13/en/topic.md",
            )
            self.assertNotIn("content_html", result)

    def test_topic_and_media_paths_avoid_basename_collisions(self):
        first_topic = topic_markdown_path(
            "https://documentation.alfabet.com/11-13/en/topic.html"
        )
        queried_topic = topic_markdown_path(
            "https://documentation.alfabet.com/11-13/en/topic.html?variant=two"
        )
        versioned_topic = topic_markdown_path(
            "https://documentation.alfabet.com/11-12/en/topic.html"
        )
        mixin = OriginalNameMixin()
        first_image = mixin.file_path(
            Request("https://documentation.alfabet.com/11-13/en/a/diagram.png")
        )
        second_image = mixin.file_path(
            Request("https://documentation.alfabet.com/11-12/en/b/diagram.png")
        )

        self.assertNotEqual(first_topic, queried_topic)
        self.assertNotEqual(first_topic, versioned_topic)
        self.assertNotEqual(first_image, second_image)
        self.assertTrue(first_image.endswith("/11-13/en/a/diagram.png"))


if __name__ == "__main__":
    unittest.main()