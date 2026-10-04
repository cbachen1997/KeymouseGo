param([string]$Python = '', [string]$PublishTo = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $projectRoot 'build\venv311\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Pass -Python with a Python 3.11 environment containing requirements-build.lock.' }
if (-not $PublishTo) { $PublishTo = Join-Path $projectRoot 'release\KeymouseGo.exe' }
Push-Location $projectRoot
try { & $Python -B -m unittest discover -s tests -v } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed; release unchanged.' }
$stage = Join-Path $projectRoot 'build\stage'
& $Python -m PyInstaller --noconfirm --distpath $stage --workpath (Join-Path $projectRoot 'build\work') (Join-Path $PSScriptRoot 'windows.spec')
if ($LASTEXITCODE -ne 0) { throw 'Build failed; existing published executable was not replaced.' }
$artifact = Join-Path $stage 'KeymouseGo.exe'
$checkDir = Join-Path $stage 'self-test'
$check = Join-Path $checkDir 'result.json'
if (Test-Path -LiteralPath $check) { Remove-Item -LiteralPath $check }
$previousQtPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = 'offscreen'
    $process = Start-Process -FilePath $artifact -ArgumentList @('--self-test', "`"$checkDir`"") -WindowStyle Hidden -Wait -PassThru
} finally { $env:QT_QPA_PLATFORM = $previousQtPlatform }
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $check)) { throw 'Packaged self-test failed; release unchanged.' }
$result = Get-Content -LiteralPath $check -Raw | ConvertFrom-Json
if (-not $result.success) { throw "Packaged self-test failed: $($result.error)" }
New-Item -ItemType Directory -Force (Split-Path -Parent $PublishTo) | Out-Null
Copy-Item -LiteralPath $artifact -Destination "$PublishTo.pending" -Force
Move-Item -LiteralPath "$PublishTo.pending" -Destination $PublishTo -Force
$version = (& $Python -c "import sys; sys.path.insert(0, r'$projectRoot'); from Util.Version import __version__; print(__version__)").Trim()
$manifest = [ordered]@{version=$version; commit=(& git -C $projectRoot rev-parse HEAD); sourceDirty=[bool](& git -C $projectRoot status --porcelain); sha256=(Get-FileHash -LiteralPath $PublishTo -Algorithm SHA256).Hash; bytes=(Get-Item -LiteralPath $PublishTo).Length; selfTest=$result; builtAt=(Get-Date).ToUniversalTime().ToString('o')}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path (Split-Path -Parent $PublishTo) 'release-info.json') -Encoding utf8
Get-Item -LiteralPath $PublishTo | Select-Object FullName, Length
