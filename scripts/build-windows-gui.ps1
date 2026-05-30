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
        $pythonInfo.base_prefix,
        (Join-Path $pythonInfo.base_prefix "Scripts"),
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
$distPath = Join-Path $repoRoot $DistDir
$workPath = Join-Path $repoRoot $WorkDir
$exePath = Join-Path $distPath "ClayFF-Toolkit.exe"

if (-not (Test-Path $specPath)) {
    throw "PyInstaller spec not found: $specPath"
}
Assert-PathExists -Path $bundleReadmePath -Description "Windows bundle README"

if (-not $SkipDependencyInstall) {
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m pip install -e "$repoRoot[gui]" pyinstaller
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Set-IsolatedPythonBuildPath
Assert-GuiDependenciesImport

$legacyBundleDir = Join-Path $distPath "ClayFF-Toolkit"
if (Test-Path $legacyBundleDir) {
    Remove-Item $legacyBundleDir -Recurse -Force
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

Write-Host "Created Windows GUI executable: $exePath"
