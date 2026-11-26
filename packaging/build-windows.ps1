# GitDesk Windows 独立应用构建：onedir + 便携 ZIP。
# 在目标 Windows 上运行，不跨平台编译。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.10+ is required."
}
python -c "import PySide6" 2>$null
if ($LASTEXITCODE -ne 0) {
    python -m pip install -r requirements.txt
}
python -m PyInstaller --version >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    python -m pip install "pyinstaller>=6.10,<7"
}

$Version = if ($env:GITDESK_VERSION) { $env:GITDESK_VERSION } else { "1.0.0" }
$Release = Join-Path $Root "release"
$Archive = Join-Path $Release "GitDesk-$Version-windows-x64.zip"
python -m PyInstaller --noconfirm --clean --distpath "$Root/dist" --workpath "$Root/build/pyinstaller" packaging/gitdesk.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$env:GITDESK_SMOKE_LOG = Join-Path $Root "build/package-smoke.json"
New-Item -ItemType Directory -Path (Split-Path $env:GITDESK_SMOKE_LOG) -Force | Out-Null
python packaging/smoke_test.py (Join-Path $Root "dist/GitDesk/GitDesk.exe")
if ($LASTEXITCODE -ne 0) { throw "Packaged application smoke test failed." }

New-Item -ItemType Directory -Path $Release -Force | Out-Null
if (Test-Path $Archive) { Remove-Item $Archive -Force }
Compress-Archive -Path "$Root/dist/GitDesk/*" -DestinationPath $Archive -CompressionLevel Optimal
$hash = (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLower()
Set-Content -Path "$Archive.sha256" -Value "$hash  $(Split-Path $Archive -Leaf)" -Encoding ascii
Write-Host "Windows package: $Archive"
Write-Host "SHA256: $hash"
