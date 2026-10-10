param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
$environment = Join-Path $projectRoot ".venv"
$interpreter = Join-Path $environment "Scripts/python.exe"

function Invoke-CheckedPython {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

Push-Location $projectRoot
try {
    if (-not (Test-Path $interpreter)) {
        if (Test-Path $environment) {
            throw "Existing .venv has no Windows Python interpreter: $interpreter"
        }
        Invoke-CheckedPython $Python @("-c", "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or later is required'")
        Invoke-CheckedPython $Python @("-m", "venv", $environment)
    }
    Invoke-CheckedPython $interpreter @("-m", "pip", "install", "-e", ".[dev]")
    Invoke-CheckedPython $interpreter @("-c", "import sys, pathlib, pytest, tree_sitter, tree_sitter_language_pack, crapper.cli; assert sys.version_info >= (3, 11); expected = pathlib.Path('src/crapper/cli.py').resolve(); actual = pathlib.Path(crapper.cli.__file__).resolve(); assert actual == expected, (actual, expected); print('Verified interpreter:', sys.executable); print('Verified checkout:', actual)")
    if (-not (Test-Path $interpreter)) {
        throw "Environment setup did not create $interpreter"
    }
    Write-Output "Run tests: & '$interpreter' -m pytest"
}
finally {
    Pop-Location
}
