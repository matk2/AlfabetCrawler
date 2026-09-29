import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter


def _inline_code(text):
    value = text.strip()
    if not value:
        return "``"
    longest_backtick_run = max(
        (len(match.group()) for match in re.finditer(r"`+", value)),
        default=0,
    )
    fence = "`" * (longest_backtick_run + 1)
    padding = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{fence}{padding}{value}{padding}{fence}"


class DocumentationMarkdownConverter(MarkdownConverter):
    def convert_span(self, el, text, parent_tags):
        if "Code" in el.get("class", []):
            return _inline_code(el.get_text())
        return text

    def convert_code(self, el, text, parent_tags):
        if "pre" in parent_tags:
            return el.get_text()
        return _inline_code(el.get_text())

    def convert_pre(self, el, text, parent_tags):
        code = el.get_text().strip("\n")
        if not code:
            return ""

        language = ""
        for tag in el.find_all(class_=True):
            for class_name in tag.get("class", []):
                match = re.match(r"(?:language|lang)-([\w+-]+)", class_name)
                if match:
                    language = match.group(1)
                    break
            if language:
                break

        return f"\n\n```{language}\n{code}\n```\n\n"

    def convert_button(self, el, text, parent_tags):
        return ""

    def convert_svg(self, el, text, parent_tags):
        return ""

    def convert_table(self, el, text, parent_tags):
        rows = []
        for row in el.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if cells:
                rows.append(
                    [
                        re.sub(r"\s+", " ", cell.get_text(" ", strip=True))
                        .replace("|", r"\|")
                        for cell in cells
                    ]
                )

        if not rows:
            return ""

        column_count = max(map(len, rows))
        normalized_rows = [
            row + [""] * (column_count - len(row))
            for row in rows
        ]
        separator = ["---"] * column_count
        markdown_rows = [normalized_rows[0], separator, *normalized_rows[1:]]
        return "\n\n" + "\n".join(
            "| " + " | ".join(row) + " |" for row in markdown_rows
        ) + "\n\n"


def _expand_accordions(soup):
    for accordion in soup.select("ul.dlt-accordion"):
        sections = []
        for item in accordion.find_all("li", class_="dlt-accordion-item", recursive=False):
            title = item.select_one(".dlt-accordion-title")
            panel = item.select_one(".dlt-accordion-content")
            if title is None or panel is None:
                continue

            heading = soup.new_tag("h2")
            heading.string = title.get_text(" ", strip=True)
            section = soup.new_tag("div")
            section.append(heading)
            for child in list(panel.contents):
                section.append(child.extract())
            sections.append(section)

        if sections:
            for section in sections:
                accordion.insert_before(section)
        accordion.decompose()


def html_to_markdown(html, source_url, media_paths=None, topic_link_resolver=None):
    soup = BeautifulSoup(html, "html.parser")
    main_area = soup.select_one("#Main-Area")
    root = main_area or soup

    _expand_accordions(root)

    for tag in root.select("script, style, svg, button"):
        tag.decompose()

    media_paths = media_paths or {}
    for image in root.select("img"):
        candidates = (image.get("src"), image.get("data-src"))
        source = next(
            (
                urljoin(source_url, candidate)
                for candidate in candidates
                if candidate
                and urlparse(urljoin(source_url, candidate)).scheme
                in {"http", "https"}
            ),
            None,
        )
        if source is None:
            image.decompose()
        else:
            image["src"] = media_paths.get(source, source)

    for link in root.select("a[href]"):
        source = urljoin(source_url, link["href"])
        if source in media_paths:
            link["href"] = media_paths[source]
        elif topic_link_resolver is not None:
            link["href"] = topic_link_resolver(source)
        else:
            link["href"] = source

    markdown = DocumentationMarkdownConverter(
        heading_style="ATX",
        bullets="-",
    ).convert_soup(root)
    return re.sub(r"\n{3,}", "\n\n", markdown).strip()