# Set up the project from a fresh clone: a virtual environment with the app and its dev tools.
# Run from the project root:  powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
$ErrorActionPreference = "Stop"

$python = (Get-Command py -ErrorAction SilentlyContinue)
if ($python) { $interpreter = @("py", "-3") } else { $interpreter = @("python") }

if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv"
    & $interpreter[0] $interpreter[1..($interpreter.Length - 1)] -m venv .venv
}

Write-Host "Installing the app and its development tools"
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example; add provider credentials there if you have them."
}

Write-Host "Checking the configuration"
& .\.venv\Scripts\wowgear.exe check

Write-Host "Done. Start the app with:  .\.venv\Scripts\wowgear.exe ui"
