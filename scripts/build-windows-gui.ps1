[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$DistDir = "dist",
    [string]$WorkDir = "build\pyinstaller",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Description
    )

    if (-not (Test-Path $Path)) {
        throw "Missing ${Description}: $Path"
    }
}

function Assert-AnyBundleFile {
    param(
        [string]$BundleDir,
        [string]$Filter,
        [string]$Description
    )

    $match = Get-ChildItem -Path $BundleDir -Recurse -File -Filter $Filter -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $match) {
        throw "Missing ${Description} in bundle: $Filter"
    }
}

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

$bundleDir = Join-Path $distPath "ClayFF-Toolkit"
$exePath = Join-Path $bundleDir "ClayFF-Toolkit.exe"

& $Python -m PyInstaller --noconfirm --clean --distpath $distPath --workpath $workPath $specPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Assert-PathExists -Path $exePath -Description "bundled executable"
Assert-AnyBundleFile -BundleDir $bundleDir -Filter "clayff.txt" -Description "ClayFF parameter resource"
Assert-AnyBundleFile -BundleDir $bundleDir -Filter "qwindows.dll" -Description "Qt Windows platform plugin"
Assert-AnyBundleFile -BundleDir $bundleDir -Filter "ovito*.pyd" -Description "OVITO Python extension"

& $exePath --smoke-test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$zipPath = Join-Path $distPath "ClayFF-Toolkit-Windows-x64.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path (Join-Path $distPath "ClayFF-Toolkit") -DestinationPath $zipPath
Assert-PathExists -Path $zipPath -Description "Windows GUI bundle zip"

Write-Host "Created Windows GUI bundle: $zipPath"
