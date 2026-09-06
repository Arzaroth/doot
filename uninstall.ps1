<#
.SYNOPSIS
    Desinstalle doot (Windows). -Purge efface aussi les donnees (journal,
    jingle genere, sons perso).
#>
[CmdletBinding()]
param([switch] $Purge)

$ErrorActionPreference = 'SilentlyContinue'

$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\doot'
$AppDir     = Join-Path $InstallDir 'app'
$BinDir     = Join-Path $InstallDir 'bin'
$DataDir    = Join-Path $env:LOCALAPPDATA 'doot'
$lnkPath    = Join-Path ([Environment]::GetFolderPath('Startup')) 'doot.lnk'

Write-Host "`ndoot - desinstallation" -ForegroundColor White

# arret du daemon
$cmd = Join-Path $BinDir 'doot.cmd'
if (Test-Path $cmd) { & $cmd --stop | Out-Null }
Get-Process pythonw, python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -and (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like '*-m doot*' } |
    Stop-Process -Force

if (Test-Path $lnkPath) { Remove-Item $lnkPath -Force; Write-Host '  raccourci   : retire' }
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force; Write-Host '  code        : retire' }

# nettoyage PATH / PYTHONPATH utilisateur
foreach ($var in @(@{ Name = 'Path'; Frag = $BinDir }, @{ Name = 'PYTHONPATH'; Frag = $AppDir })) {
    $value = [Environment]::GetEnvironmentVariable($var.Name, 'User')
    if ($value -and $value -like "*$($var.Frag)*") {
        $clean = ($value -split ';' | Where-Object { $_ -and $_ -ne $var.Frag }) -join ';'
        [Environment]::SetEnvironmentVariable($var.Name, $clean, 'User')
        Write-Host "  $($var.Name.PadRight(11)): nettoye"
    }
}

if ($Purge) {
    if (Test-Path $DataDir) { Remove-Item $DataDir -Recurse -Force }
    Write-Host '  donnees     : effacees'
} else {
    Write-Host "  donnees     : conservees dans $DataDir (-Purge pour les effacer)"
}

Write-Host "`n  Plus de doot. Le squelette range sa trompette.`n"
