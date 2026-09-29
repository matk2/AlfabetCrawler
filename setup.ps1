$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$PythonCommand = "python"
$PythonArguments = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
    $PythonArguments = @("-3")
} elseif (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.10 or newer is required and must be available on PATH."
}

& $PythonCommand @PythonArguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.10 or newer is required."
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $PythonCommand @PythonArguments -m venv (Join-Path $ProjectRoot ".venv")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create the virtual environment."
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}

& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install project requirements."
}