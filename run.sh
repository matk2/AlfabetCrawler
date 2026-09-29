#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
SCRAPY_ARGS=()

show_help() {
    cat <<EOF
Usage: $0 [--clean|-c] [Scrapy settings and arguments...]

Settings can be passed as NAME=value or with Scrapy's -s/--set option.

Clean generated crawl outputs and exit:
    $0 --clean
    $0 -c

Examples:
  $0 CLOSESPIDER_ITEMCOUNT=10
  $0 HTTPCACHE_ENABLED=False
  $0 CLOSESPIDER_ITEMCOUNT=10 HTTPCACHE_ENABLED=False
  $0 -s CLOSESPIDER_ITEMCOUNT=10 -s HTTPCACHE_ENABLED=False

CLOSESPIDER_ITEMCOUNT limits scraped topic items. Media downloads are not
counted. Requests already in flight may cause the final count to exceed it.
EOF
}

CLEAN=0

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        --clean|-c)
            CLEAN=1
            shift
            ;;
        -s|--set)
            SCRAPY_ARGS+=("$1")
            shift
            if [[ "$#" -gt 0 ]]; then
                SCRAPY_ARGS+=("$1")
                shift
            fi
            ;;
        *)
            if [[ "$1" =~ ^[A-Za-z_][A-Za-z0-9_]*=.*$ ]]; then
                SCRAPY_ARGS+=(-s "$1")
            else
                SCRAPY_ARGS+=("$1")
            fi
            shift
            ;;
    esac
done

if [[ "$CLEAN" -eq 1 ]]; then
    if [[ "${#SCRAPY_ARGS[@]}" -gt 0 ]]; then
        printf '%s\n' "Error: --clean cannot be combined with Scrapy arguments." >&2
        exit 2
    fi

    for path in \
        "$PROJECT_ROOT/Output/downloaded_files" \
        "$PROJECT_ROOT/Output/downloaded_images" \
        "$PROJECT_ROOT/Output/httpcache" \
        "$PROJECT_ROOT/.scrapy" \
        "$PROJECT_ROOT/Output/crawls" \
        "$PROJECT_ROOT/Output/Markdown/topics"
    do
        rm -rf -- "$path"
    done
    rm -f -- "$PROJECT_ROOT/Output/alfabet_pages.jsonl"
    printf '%s\n' "Generated crawl outputs cleaned. Virtual environment and Markdown/LLM_INSTRUCTIONS.md were preserved."
    exit 0
fi

if [ ! -x "$VENV_PYTHON" ]; then
    printf '%s\n' "Virtual environment not found. Run setup.sh first." >&2
    exit 1
fi

cd "$PROJECT_ROOT"
exec "$VENV_PYTHON" -m scrapy crawl alfabet "${SCRAPY_ARGS[@]}"