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

function Assert-GuiDependenciesImport {
    Write-Host "Checking GUI dependencies in the build Python environment..."
    & $Python -c "import ovito; import ovito.qt_compat; print('gui_dependency_preflight=ok')"
    if ($LASTEXITCODE -ne 0) {
        throw "GUI dependency preflight failed. Use an official CPython 3.10+ interpreter with working OVITO/PySide6 imports, then rerun this script with -Python <path-to-python.exe>."
    }
}

function Set-IsolatedPythonBuildPath {
    $pythonInfoJson = & $Python -c "import json, sys; print(json.dumps({'executable': sys.executable, 'prefix': sys.prefix, 'base_prefix': sys.base_prefix}))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $pythonInfo = $pythonInfoJson | ConvertFrom-Json

    $pathCandidates = @(
        (Split-Path -Parent $pythonInfo.executable),
        $pythonInfo.prefix,
        (Join-Path $pythonInfo.prefix "Scripts"),
        (Join-Path $pythonInfo.prefix "Library\bin"),
        $pythonInfo.base_prefix,
        (Join-Path $pythonInfo.base_prefix "Scripts"),
        (Join-Path $pythonInfo.base_prefix "Library\bin"),
        (Join-Path $env:SystemRoot "System32"),
        $env:SystemRoot,
        (Join-Path $env:SystemRoot "System32\Wbem"),
        (Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0")
    )

    $isolatedPath = New-Object System.Collections.Generic.List[string]
    foreach ($path in $pathCandidates) {
        if ($path -and (Test-Path $path) -and -not $isolatedPath.Contains($path)) {
            $isolatedPath.Add($path)
        }
    }

    $env:PYTHONNOUSERSITE = "1"
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    $env:PATH = $isolatedPath -join [IO.Path]::PathSeparator
    Write-Host "Using isolated Python build environment: $($pythonInfo.prefix)"
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Windows GUI executables must be built on Windows."
}

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent $scriptDir
$specPath = Join-Path $repoRoot "packaging\windows\ClayFF-Toolkit.spec"
$bundleReadmePath = Join-Path $repoRoot "packaging\windows\README.txt"
$buildConstraintsPath = Join-Path $repoRoot "packaging\windows\build-constraints.txt"
$licenseCollectorPath = Join-Path $repoRoot "scripts\collect_third_party_licenses.py"
$distPath = Join-Path $repoRoot $DistDir
$workPath = Join-Path $repoRoot $WorkDir
$exePath = Join-Path $distPath "ClayFF-Toolkit.exe"
$bundleDir = Join-Path $distPath "ClayFF-Toolkit-Windows-x64"
$archivePath = Join-Path $distPath "ClayFF-Toolkit-Windows-x64.zip"

if (-not (Test-Path $specPath)) {
    throw "PyInstaller spec not found: $specPath"
}
Assert-PathExists -Path $bundleReadmePath -Description "Windows bundle README"
Assert-PathExists -Path $buildConstraintsPath -Description "Windows build constraints"
Assert-PathExists -Path $licenseCollectorPath -Description "third-party license collector"
Assert-PathExists -Path (Join-Path $repoRoot "LICENSE") -Description "project license"
Assert-PathExists -Path (Join-Path $repoRoot "NOTICE") -Description "project notice"
Assert-PathExists -Path (Join-Path $repoRoot "THIRD_PARTY_NOTICES.md") -Description "third-party notice"

if (-not $SkipDependencyInstall) {
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m pip install -c $buildConstraintsPath -e "$repoRoot[gui]" pyinstaller
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Set-IsolatedPythonBuildPath
Assert-GuiDependenciesImport

if (Test-Path $bundleDir) {
    Remove-Item $bundleDir -Recurse -Force
}
if (Test-Path $archivePath) {
    Remove-Item $archivePath -Force
}

& $Python -m PyInstaller --noconfirm --clean --distpath $distPath --workpath $workPath $specPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Assert-PathExists -Path $exePath -Description "standalone Windows executable"

$smokeReportPath = Join-Path $workPath "ClayFF-Toolkit-smoke-test.txt"
if (Test-Path $smokeReportPath) {
    Remove-Item $smokeReportPath -Force
}
$smokeExePath = $exePath
$smokeWorkingDir = Split-Path -Parent $exePath
if ($exePath.StartsWith("\\")) {
    $localSmokeDir = Join-Path ([System.IO.Path]::GetTempPath()) "ClayFF-Toolkit-smoke-$([guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Force -Path $localSmokeDir | Out-Null
    $smokeExePath = Join-Path $localSmokeDir "ClayFF-Toolkit.exe"
    Copy-Item -Path $exePath -Destination $smokeExePath -Force
    $smokeWorkingDir = $localSmokeDir
}
$env:CLAYFF_TOOLKIT_SMOKE_REPORT = $smokeReportPath
try {
    $smokeProcess = Start-Process -FilePath $smokeExePath -ArgumentList "--smoke-test" -WorkingDirectory $smokeWorkingDir -Wait -PassThru -WindowStyle Hidden
}
finally {
    Remove-Item Env:\CLAYFF_TOOLKIT_SMOKE_REPORT -ErrorAction SilentlyContinue
}
if (Test-Path $smokeReportPath) {
    Get-Content $smokeReportPath | ForEach-Object { Write-Host $_ }
}
if ($smokeProcess.ExitCode -ne 0) { exit $smokeProcess.ExitCode }

New-Item -ItemType Directory -Force -Path $bundleDir | Out-Null
Copy-Item -Path $exePath -Destination (Join-Path $bundleDir "ClayFF-Toolkit.exe") -Force
Copy-Item -Path $bundleReadmePath -Destination (Join-Path $bundleDir "README.txt") -Force
Copy-Item -Path $buildConstraintsPath -Destination (Join-Path $bundleDir "BUILD-CONSTRAINTS.txt") -Force
foreach ($name in @("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "CITATION.cff")) {
    Copy-Item -Path (Join-Path $repoRoot $name) -Destination (Join-Path $bundleDir $name) -Force
}

& $Python $licenseCollectorPath --output-dir $bundleDir --repo-root $repoRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m PyInstaller.utils.cliutils.archive_viewer -l $exePath |
    Out-File -Encoding utf8 (Join-Path $bundleDir "PYINSTALLER-CONTENTS.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($requiredName in @(
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "THIRD_PARTY_LICENSES.md",
    "DEPENDENCIES.txt",
    "PYINSTALLER-CONTENTS.txt"
)) {
    Assert-PathExists -Path (Join-Path $bundleDir $requiredName) -Description "Windows bundle file $requiredName"
}
Assert-PathExists -Path (Join-Path $bundleDir "licenses\PySide6-Qt\LGPL-3.0-only.txt") -Description "LGPL-3.0 license"
Assert-PathExists -Path (Join-Path $bundleDir "licenses\PySide6-Qt\GPL-3.0-only.txt") -Description "GPL-3.0 license incorporated by LGPL-3.0"

Compress-Archive -Path $bundleDir -DestinationPath $archivePath -CompressionLevel Optimal
Assert-PathExists -Path $archivePath -Description "licensed Windows distribution archive"

Write-Host "Created Windows GUI executable: $exePath"
Write-Host "Created licensed Windows distribution: $archivePath"
