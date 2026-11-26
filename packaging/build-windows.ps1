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
$Setup = Join-Path $Release "GitDesk-$Version-windows-x64-setup.exe"
python -m PyInstaller --noconfirm --clean --distpath "$Root/dist" --workpath "$Root/build/pyinstaller" packaging/gitdesk.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$env:GITDESK_SMOKE_LOG = Join-Path $Root "build/package-smoke.json"
New-Item -ItemType Directory -Path (Split-Path $env:GITDESK_SMOKE_LOG) -Force | Out-Null
python packaging/smoke_test.py (Join-Path $Root "dist/GitDesk/GitDesk.exe")
if ($LASTEXITCODE -ne 0) { throw "Packaged application smoke test failed." }

New-Item -ItemType Directory -Path $Release -Force | Out-Null

# 真正的 Windows 安装程序：安装路径、开始菜单/桌面图标、卸载入口。
$Inno = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$InnoPath = if ($Inno) { $Inno.Source } else { "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $InnoPath)) {
    $installer = Join-Path $env:TEMP "innosetup-6.7.4.exe"
    Invoke-WebRequest -Uri "https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe" -OutFile $installer
    & $installer /SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup installation failed." }
}
& $InnoPath /Qp "$Root\packaging\gitdesk.iss"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Setup)) { throw "Windows installer compilation failed." }
$setupHash = (Get-FileHash $Setup -Algorithm SHA256).Hash.ToLower()
Set-Content -Path "$Setup.sha256" -Value "$setupHash  $(Split-Path $Setup -Leaf)" -Encoding ascii

# 保留便携 ZIP 供不希望安装的用户选择。
if (Test-Path $Archive) { Remove-Item $Archive -Force }
Compress-Archive -Path "$Root/dist/GitDesk/*" -DestinationPath $Archive -CompressionLevel Optimal -Force
$hash = (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLower()
Set-Content -Path "$Archive.sha256" -Value "$hash  $(Split-Path $Archive -Leaf)" -Encoding ascii
Write-Host "Windows package: $Archive"
Write-Host "SHA256: $hash"
Write-Host "Windows installer: $Setup"
Write-Host "Installer SHA256: $setupHash"
