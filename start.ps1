param(
    [string]$OpenAIApiKey = "",
    [switch]$DemoMode
)

$ErrorActionPreference = "Stop"

function Get-PythonCommand {
    $commandCandidates = @()

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source) {
        $commandCandidates += ,@($pythonCommand.Source, @())
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher -and $pyLauncher.Source) {
        $commandCandidates += ,@($pyLauncher.Source, @("-3"))
    }

    $pathCandidates = @(
        "$HOME\.conda\envs\py38\python.exe",
        "$HOME\env\Scripts\python.exe",
        "$HOME\AppData\Local\Programs\Python\Python312\python.exe",
        "$HOME\AppData\Local\Programs\Python\Python311\python.exe",
        "$HOME\AppData\Local\Programs\Python\Python310\python.exe",
        "$HOME\AppData\Local\Programs\Python\Python39\python.exe",
        "$HOME\AppData\Local\Programs\Python\Python38\python.exe"
    )

    foreach ($candidate in $pathCandidates) {
        if (Test-Path $candidate) {
            $commandCandidates += ,@($candidate, @())
        }
    }

    return $commandCandidates | Select-Object -First 1
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = Get-PythonCommand

if (-not $pythonCommand) {
    Write-Host "Python was not found on PATH or in common local install locations." -ForegroundColor Red
    Write-Host "Install Python 3.8+ or update the script with your Python path, then run again." -ForegroundColor Yellow
    exit 1
}

$pythonExe = $pythonCommand[0]
$pythonArgs = $pythonCommand[1]

Write-Host "Using Python: $pythonExe" -ForegroundColor Cyan

if ($OpenAIApiKey) {
    $env:OPENAI_API_KEY = $OpenAIApiKey
    Write-Host "OpenAI API key loaded for this session." -ForegroundColor Green
} elseif (-not $env:OPENAI_API_KEY) {
    Write-Host "OPENAI_API_KEY is not set. The app will fall back to demo mode." -ForegroundColor Yellow
}

if ($DemoMode) {
    $env:DEMO_MODE = "true"
    Write-Host "Demo mode enabled." -ForegroundColor Yellow
}

Push-Location $projectRoot
try {
    & $pythonExe @pythonArgs -m pip install -r requirements.txt
    & $pythonExe @pythonArgs -m playwright install chromium
    & $pythonExe @pythonArgs app.py
} finally {
    Pop-Location
}
