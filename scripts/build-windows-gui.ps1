[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$DistDir = "dist",
    [string]$WorkDir = "build\pyinstaller",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Windows GUI bundles must be built on Windows."
}

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent $scriptDir
$specPath = Join-Path $repoRoot "packaging\windows\ClayFF-Toolkit.spec"
$distPath = Join-Path $repoRoot $DistDir
$workPath = Join-Path $repoRoot $WorkDir

if (-not (Test-Path $specPath)) {
    throw "PyInstaller spec not found: $specPath"
}

if (-not $SkipDependencyInstall) {
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m pip install -e "$repoRoot[gui]" pyinstaller
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $Python -m PyInstaller --noconfirm --clean --distpath $distPath --workpath $workPath $specPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exePath = Join-Path $distPath "ClayFF-Toolkit\ClayFF-Toolkit.exe"
if (-not (Test-Path $exePath)) {
    throw "Expected bundled executable was not created: $exePath"
}

& $exePath --smoke-test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$zipPath = Join-Path $distPath "ClayFF-Toolkit-Windows-x64.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $distPath "ClayFF-Toolkit") -DestinationPath $zipPath

Write-Host "Created Windows GUI bundle: $zipPath"
