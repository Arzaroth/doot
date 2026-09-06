<#
.SYNOPSIS
    Installe doot pour l'utilisateur courant (Windows 10/11). Pas besoin d'admin.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -NoAutostart
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -MinSeconds 300 -MaxSeconds 1800
#>
[CmdletBinding()]
param(
    [int]    $MinSeconds = 600,
    [int]    $MaxSeconds = 3600,
    [switch] $NoAutostart
)

$ErrorActionPreference = 'Stop'

function Write-Head { param($Text) Write-Host "`n$Text" -ForegroundColor White }
function Write-Item { param($Text) Write-Host "  $Text" }

Write-Head 'doot - installation'

$Src        = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
$InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\doot'
$AppDir     = Join-Path $InstallDir 'app'
$BinDir     = Join-Path $InstallDir 'bin'

# ------------------------------------------------------------- python --------

function Find-Python {
    $candidates = @(
        @{ File = 'py';      Args = @('-3') },
        @{ File = 'python3'; Args = @() },
        @{ File = 'python';  Args = @() }
    )
    foreach ($c in $candidates) {
        $cmd = Get-Command $c.File -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            # @(...) : le stub "Python" du Microsoft Store renvoie du texte libre,
            # on ne veut surtout pas indexer une chaine caractere par caractere.
            $probe = @(& $c.File @($c.Args + @('-c', 'import sys; print(sys.executable); print("%d.%d" % sys.version_info[:2])')) 2>$null)
            if ($probe.Count -lt 2) { continue }
            $exe = "$($probe[0])".Trim()
            $ver = [version]("$($probe[1])".Trim())
            if ($exe -and (Test-Path $exe) -and $ver -ge [version]'3.8') { return $exe }
        } catch { continue }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Item 'Python 3.8+ est introuvable.'
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Item 'Installe-le puis relance ce script :'
        Write-Item '  winget install -e --id Python.Python.3.12'
    } else {
        Write-Item 'Installe-le depuis https://www.python.org/downloads/ (coche "tcl/tk" et "Add to PATH").'
    }
    exit 1
}
Write-Item "python      : $python"

$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }

& $python -c 'import tkinter' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Item 'tkinter     : MANQUANT -> reinstalle Python en cochant "tcl/tk and IDLE"'
} else {
    Write-Item 'tkinter     : OK'
}
Write-Item 'audio       : winsound (integre a Windows)'

# ------------------------------------------------------------ fichiers -------

Write-Head 'Copie des fichiers'
if (Test-Path $AppDir) { Remove-Item $AppDir -Recurse -Force }
New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
Copy-Item (Join-Path $Src 'doot') -Destination (Join-Path $AppDir 'doot') -Recurse -Force
Write-Item "code        : $AppDir\doot"

$cmdPath = Join-Path $BinDir 'doot.cmd'
@"
@echo off
set "PYTHONPATH=$AppDir;%PYTHONPATH%"
"$python" -m doot %*
"@ | Set-Content -Path $cmdPath -Encoding ASCII
Write-Item "commande    : $cmdPath"

# PATH utilisateur (pas de PATH machine, pas d'admin)
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable('Path', "$userPath;$BinDir", 'User')
    Write-Item "PATH        : $BinDir ajoute (rouvre ton terminal)"
} else {
    Write-Item 'PATH        : deja configure'
}

# --------------------------------------------------------- demarrage ---------

$startup  = [Environment]::GetFolderPath('Startup')
$lnkPath  = Join-Path $startup 'doot.lnk'

if (-not $NoAutostart) {
    Write-Head 'Demarrage automatique'
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath       = $pythonw
    $lnk.Arguments        = "-m doot --min $MinSeconds --max $MaxSeconds --quiet"
    $lnk.WorkingDirectory = $AppDir
    $lnk.Description      = 'doot - squelette trompettiste saisonnier'
    $lnk.WindowStyle      = 7
    $lnk.Save()

    # PYTHONPATH utilisateur pour que le raccourci trouve le module
    $envPyPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'User')
    if (-not $envPyPath -or $envPyPath -notlike "*$AppDir*") {
        $newPyPath = if ($envPyPath) { "$envPyPath;$AppDir" } else { $AppDir }
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $newPyPath, 'User')
    }
    Write-Item "raccourci   : $lnkPath"
    Write-Item 'doot demarrera a la prochaine ouverture de session.'
} else {
    if (Test-Path $lnkPath) { Remove-Item $lnkPath -Force }
    Write-Item 'demarrage automatique ignore (-NoAutostart)'
}

Write-Head 'Termine'
Write-Item 'Teste tout de suite : doot --once --ignore-season'
Write-Item 'Etat                : doot --status'
Write-Item 'Desinstaller        : powershell -ExecutionPolicy Bypass -File .\uninstall.ps1'
Write-Host ''
$env:PYTHONPATH = "$AppDir;$env:PYTHONPATH"
& $python -m doot --art
