param([string]$Python = '', [string]$PublishTo = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $projectRoot 'build\venv311\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Pass -Python with a Python environment containing the project dependencies and PyInstaller.' }
& $Python -m PyInstaller --noconfirm --distpath (Join-Path $projectRoot 'dist') --workpath (Join-Path $projectRoot 'build\release') (Join-Path $PSScriptRoot 'windows.spec')
if ($LASTEXITCODE -ne 0) { throw 'Build failed; existing published executable was not replaced.' }
$artifact = Join-Path $projectRoot 'dist\KeymouseGo.exe'
if ($PublishTo) { Copy-Item -LiteralPath $artifact -Destination $PublishTo -Force }
Get-Item -LiteralPath $artifact | Select-Object FullName, Length
Get-FileHash -LiteralPath $artifact -Algorithm SHA256
