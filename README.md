# Alfabet Crawler

A Scrapy crawler for the public Alfabet documentation site. It follows links on `documentation.alfabet.com`, extracts each page's `#Main-Area` topic, downloads topic images and PDF/SVG files, and writes readable Markdown.

## Prerequisite

Install Python 3.10 or newer and make it available on `PATH`. The setup scripts create an isolated `.venv` and install the declared packages there; they do not require Homebrew and do not install Python itself.

## Setup and run

From this directory:

macOS or Linux:

```sh
./setup.sh
./run.sh
```

Windows PowerShell:

```powershell
.\setup.ps1
.\run.ps1
```

Settings may be supplied as `NAME=value` or explicitly with Scrapy's `-s NAME=value` syntax. For example, `./run.sh CLOSESPIDER_ITEMCOUNT=10 HTTPCACHE_ENABLED=False` limits scraped topic items and disables the HTTP cache. Media downloads are not counted by `CLOSESPIDER_ITEMCOUNT`; requests already in flight may cause a small overshoot. Other Scrapy arguments can be passed through to either run script.

Show runner help and examples of common Scrapy settings:

```sh
./run.sh --help
./run.sh -h
```

```powershell
.\run.ps1 --help
.\run.ps1 -h
```

Remove generated downloads, caches, topic Markdown, and the JSONL feed without starting a crawl:

```sh
./run.sh --clean
```

```powershell
.\run.ps1 --clean
```

Cleanup removes files in `Output` directory: `downloaded_files/`, `downloaded_images/`, `crawls/`, `Markdown/topics/`, `alfabet_pages.jsonl` and `httpcache/` in hte main project directory when present. It preserves the virtual environment, project code, and `Output/Markdown/LLM_INSTRUCTIONS.md`. Cleanup runs by itself; do not combine it with crawl settings or arguments.

## Manual virtual environment

macOS or Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scrapy crawl alfabet
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scrapy crawl alfabet
```

## Output

All generated files are stored under the `Output` directory, regardless of the shell's current working directory:

- `alfabet_pages.jsonl`: persistent topic records, merged by URL; crawled topics are updated and untouched topics are retained
- `Markdown/topics/`: one Markdown file per documentation topic, preserving headings, paragraphs, lists, links, code, tables, accordions, and images
- `Markdown/LLM_INSTRUCTIONS.md`: guidance for reading and using the exported documentation corpus
- `downloaded_images/`: downloaded images
- `downloaded_files/`: downloaded PDF and SVG files
- `httpcache/`: Scrapy HTTP cache (in main project directory)

The crawler follows links from the full HTML page, but exports content and media only from `#Main-Area`. The JSONL feed is merged on each crawl by URL: topics seen again replace their prior record, untouched topics remain, URL fragments do not distinguish topics, and query strings do. The feed is rewritten atomically at crawl shutdown. Markdown files include the original page URL in their front matter. Links to same-site `.html` topics are rewritten to relative Markdown paths, with fragment anchors preserved; off-site links remain absolute. Images and downloaded PDF/SVG/GIF links use relative local paths when their downloads succeed; unavailable media remains linked to its source URL.

The spider obeys the site's `robots.txt` and uses a download delay. Crawl only as permitted by the site owner and applicable terms.
