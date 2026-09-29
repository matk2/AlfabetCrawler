$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ScrapyArgs = [System.Collections.Generic.List[string]]::new()

if ($args -contains "-h" -or $args -contains "--help") {
    @"
Usage: .\run.ps1 [--clean|-c] [Scrapy settings and arguments...]

Settings can be passed as NAME=value or with Scrapy's -s/--set option.

Clean generated crawl outputs and exit:
    .\run.ps1 --clean
    .\run.ps1 -c

Examples:
  .\run.ps1 CLOSESPIDER_ITEMCOUNT=10
  .\run.ps1 HTTPCACHE_ENABLED=False
  .\run.ps1 CLOSESPIDER_ITEMCOUNT=10 HTTPCACHE_ENABLED=False
  .\run.ps1 -s CLOSESPIDER_ITEMCOUNT=10 -s HTTPCACHE_ENABLED=False

CLOSESPIDER_ITEMCOUNT limits scraped topic items. Media downloads are not
counted. Requests already in flight may cause the final count to exceed it.
"@
    exit 0
}

$Clean = $args -contains "--clean" -or $args -contains "-c"
$OtherArgs = @($args | Where-Object { $_ -ne "--clean" -and $_ -ne "-c" })
if ($Clean) {
    if ($OtherArgs.Count -gt 0) {
        throw "--clean cannot be combined with Scrapy arguments."
    }

    $PathsToRemove = @(
        "Output/downloaded_files",
        "Output/downloaded_images",
        "Output/httpcache",
        ".scrapy",
        "Output/crawls",
        "Output/Markdown/topics"
    )
    foreach ($RelativePath in $PathsToRemove) {
        $Path = Join-Path $ProjectRoot $RelativePath
        if (Test-Path -LiteralPath $Path) {
            Remove-Item -LiteralPath $Path -Recurse -Force
        }
    }

    $FeedPath = Join-Path $ProjectRoot "Output/alfabet_pages.jsonl"
    if (Test-Path -LiteralPath $FeedPath) {
        Remove-Item -LiteralPath $FeedPath -Force
    }
    Write-Output "Generated crawl outputs cleaned. Virtual environment and Markdown/LLM_INSTRUCTIONS.md were preserved."
    exit 0
}

$ScrapyInputArgs = $OtherArgs

for ($Index = 0; $Index -lt $ScrapyInputArgs.Count; $Index++) {
    $Argument = $ScrapyInputArgs[$Index]

    if ($Argument -eq "-s" -or $Argument -eq "--set") {
        $ScrapyArgs.Add($Argument)
        if ($Index + 1 -lt $ScrapyInputArgs.Count) {
            $Index++
            $ScrapyArgs.Add($ScrapyInputArgs[$Index])
        }
        continue
    }

    if ($Argument -match "^[A-Za-z_][A-Za-z0-9_]*=.*$") {
        $ScrapyArgs.Add("-s")
        $ScrapyArgs.Add($Argument)
    } else {
        $ScrapyArgs.Add($Argument)
    }
}

$ScrapyArgumentArray = $ScrapyArgs.ToArray()

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment not found. Run setup.ps1 first."
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m scrapy crawl alfabet @ScrapyArgumentArray
    $ExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $ExitCode