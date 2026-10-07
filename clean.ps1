<#
.SYNOPSIS
    Frees disk space in this project folder after a run.

.DESCRIPTION
    Deletes local, rebuildable and git-ignored items: .venv, every __pycache__,
    .pytest_cache, .mypy_cache, the data/ downloads and the local outputs/ folder.
    Tracked files are never deleted: any path that contains a file tracked by git
    is skipped. Prints the MB freed. Safe to rerun (missing paths are skipped).

    Copy outputs/ elsewhere (e.g. Google Drive) before running if you need them.
    Rebuild the venv afterwards with:
        python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt

.PARAMETER DryRun
    List what would be removed and how many MB it would free, without deleting.

.EXAMPLE
    .\clean.ps1
.EXAMPLE
    .\clean.ps1 -DryRun
#>
[CmdletBinding()]
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $root) { $root = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not (Test-Path -LiteralPath (Join-Path $root '.git'))) {
    Write-Error "Refusing to run: $root is not the root of a git clone."
    exit 1
}
Push-Location -LiteralPath $root
$exitCode = 0
try {
    $haveGit = [bool](Get-Command git -ErrorAction SilentlyContinue)

    function Get-Bytes([string]$path) {
        if (-not (Test-Path -LiteralPath $path)) { return [int64]0 }
        $item = Get-Item -LiteralPath $path -Force
        if (-not $item.PSIsContainer) { return [int64]$item.Length }
        $sum = (Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue |
                Measure-Object -Property Length -Sum).Sum
        if ($sum) { return [int64]$sum } else { return [int64]0 }
    }

    function Test-HasTrackedFiles([string]$path) {
        if (-not $haveGit) { return $true }   # cannot check, so be safe and skip
        $rel = Resolve-Path -LiteralPath $path -Relative
        $tracked = & git ls-files -- $rel 2>$null
        return [bool]$tracked
    }

    # Fixed top-level targets, plus every __pycache__ outside .venv
    $targets = @(@('.venv', '.pytest_cache', '.mypy_cache', 'data', 'outputs') |
        ForEach-Object { Join-Path $root $_ } |
        Where-Object { Test-Path -LiteralPath $_ })
    $venv = Join-Path $root '.venv'
    $targets += @(Get-ChildItem -LiteralPath $root -Recurse -Force -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
        Where-Object { -not $_.FullName.StartsWith($venv + [IO.Path]::DirectorySeparatorChar) -and
                       -not $_.FullName.StartsWith((Join-Path $root '.git') + [IO.Path]::DirectorySeparatorChar) } |
        ForEach-Object { $_.FullName })

    $before = Get-Bytes $root
    $planned = [int64]0
    $failed = @()

    if (-not $targets) {
        Write-Host 'Nothing to clean.'
    }
    foreach ($t in $targets) {
        $name = Resolve-Path -LiteralPath $t -Relative
        if (Test-HasTrackedFiles $t) {
            Write-Warning "Skipping $name (contains tracked files, or git is unavailable)."
            continue
        }
        $bytes = Get-Bytes $t
        $planned += $bytes
        if ($DryRun) {
            Write-Host ('Would remove {0,-25} {1,10:N1} MB' -f $name, ($bytes / 1MB))
            continue
        }
        try {
            Remove-Item -LiteralPath $t -Recurse -Force
            Write-Host ('Removed {0,-25} {1,10:N1} MB' -f $name, ($bytes / 1MB))
        } catch {
            $failed += $name
            Write-Warning "Could not fully remove $name (a file may be in use): $($_.Exception.Message)"
        }
    }

    if ($DryRun) {
        Write-Host ('Dry run: would free {0:N1} MB (folder now {1:N1} MB).' -f ($planned / 1MB), ($before / 1MB))
    } else {
        $after = Get-Bytes $root
        Write-Host ('Freed {0:N1} MB (folder {1:N1} MB -> {2:N1} MB).' -f (($before - $after) / 1MB), ($before / 1MB), ($after / 1MB))
        Write-Host 'Rebuild the venv with: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt'
        if ($failed) { $exitCode = 1 }
    }
} finally {
    Pop-Location
}
exit $exitCode
