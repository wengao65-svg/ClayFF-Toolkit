[CmdletBinding()]
param(
    [switch]$NoGui,
    [string]$BinDir,
    [string]$Venv,
    [switch]$NoPathUpdate,
    [string]$Python
)

$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    param([string]$RequestedPython)

    if ($RequestedPython) {
        return @($RequestedPython)
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @($pyLauncher.Source, "-3")
    }

    $pythonExe = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonExe) {
        return @($pythonExe.Source)
    }

    throw "Python was not found. Install Python 3.10+ or pass -Python <path>."
}

function Add-UserPathEntry {
    param([string]$PathEntry)

    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) {
        $parts = $current -split ";" | Where-Object { $_ }
    }

    $alreadyPresent = $false
    foreach ($part in $parts) {
        if ([string]::Equals($part.TrimEnd("\"), $PathEntry.TrimEnd("\"), [StringComparison]::OrdinalIgnoreCase)) {
            $alreadyPresent = $true
            break
        }
    }

    if (-not $alreadyPresent) {
        $updated = @($parts + $PathEntry) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $updated, "User")
    }
}

$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = Split-Path -Parent $scriptDir
$pythonCommand = @(Resolve-PythonCommand -RequestedPython $Python)

if (-not $Venv) {
    $Venv = Join-Path $repoRoot ".venv"
}
if (-not $BinDir) {
    $localAppData = [Environment]::GetFolderPath("LocalApplicationData")
    $BinDir = Join-Path $localAppData "ClayFF-Toolkit\bin"
}

$coreArgs = @(
    (Join-Path $scriptDir "install_clayff_toolkit.py"),
    "--platform", "windows",
    "--repo-root", $repoRoot,
    "--python", $pythonCommand[0],
    "--venv", $Venv,
    "--bin-dir", $BinDir,
    "--no-path-update"
)

if ($pythonCommand.Count -gt 1) {
    foreach ($pythonArg in $pythonCommand[1..($pythonCommand.Count - 1)]) {
        $coreArgs += @("--python-arg", $pythonArg)
    }
}

if ($NoGui) {
    $coreArgs += "--no-gui"
}

$pythonTail = @()
if ($pythonCommand.Count -gt 1) {
    $pythonTail = $pythonCommand[1..($pythonCommand.Count - 1)]
}
$pythonExe = $pythonCommand[0]
& $pythonExe @pythonTail @coreArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not $NoPathUpdate) {
    Add-UserPathEntry -PathEntry $BinDir
}

Write-Host "Installed ClayFF-Toolkit launcher: $(Join-Path $BinDir 'clayff-toolkit.cmd')"
Write-Host "Open a new terminal, then verify with: clayff-toolkit --help"
