param(
    [string]$Version = "dev",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$rootPath = $root.Path
$indexPath = Join-Path $rootPath "xdownloader_app/index.html"
$configExamplePath = Join-Path $rootPath "config.example.json"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

Remove-Item -Recurse -Force build, dist, release -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force release | Out-Null

pyinstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name xDownloader `
    --paths xdownloader_app `
    --add-data "$indexPath;xdownloader_app" `
    --add-data "$configExamplePath;." `
    --hidden-import src.cache `
    --hidden-import src.client `
    --hidden-import src.config `
    --hidden-import src.csv_output `
    --hidden-import src.downloader `
    --hidden-import src.logger `
    --hidden-import src.merge `
    --hidden-import src.models `
    --hidden-import src.twitter_api `
    --hidden-import src.utils `
    --hidden-import tkinter `
    --hidden-import tkinter.filedialog `
    --distpath release `
    --workpath build `
    --specpath build `
    xdownloader.py

if (-not (Test-Path "release/xDownloader.exe")) {
    throw "PyInstaller did not create release/xDownloader.exe"
}

$zipName = "xDownloader-$Version-windows.zip"
Compress-Archive -Path "release/xDownloader.exe" -DestinationPath "release/$zipName" -Force
Write-Host "Built release/xDownloader.exe"
Write-Host "Built release/$zipName"

if (-not $SkipInstaller) {
    $iscc = Get-Command iscc -ErrorAction SilentlyContinue
    if (-not $iscc) {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        )
        foreach ($candidate in $candidates) {
            if (Test-Path $candidate) {
                $iscc = Get-Item $candidate
                break
            }
        }
    }
    if (-not $iscc) {
        throw "Inno Setup compiler not found. Install Inno Setup 6 or run with -SkipInstaller."
    }

    $isccPath = if ($iscc.Source) { $iscc.Source } else { $iscc.FullName }
    $env:XDOWNLOADER_VERSION = $Version
    & $isccPath "packaging\xdownloader.iss"
    if (-not (Test-Path "release/xDownloader-Setup-$Version.exe")) {
        throw "Inno Setup did not create release/xDownloader-Setup-$Version.exe"
    }
    Write-Host "Built release/xDownloader-Setup-$Version.exe"
}
