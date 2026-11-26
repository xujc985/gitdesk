# GitDesk Windows 安装程序验收：静默安装 → 启动 → 验证 → 卸载。
# 需要已生成 release/GitDesk-1.0.0-windows-x64-setup.exe。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Setup = Join-Path $Root "release/GitDesk-1.0.0-windows-x64-setup.exe"
if (-not (Test-Path $Setup)) { throw "Setup not found: $Setup" }
$Target = Join-Path $Root "build/install-test/GitDesk"
$Uninstall = Join-Path $Target "unins000.exe"

$install = Start-Process -FilePath $Setup -ArgumentList @("/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$Target", "/NOICONS") -Wait -PassThru
if ($install.ExitCode -ne 0) { throw "Installer failed: $($install.ExitCode)" }
if (-not (Test-Path (Join-Path $Target "GitDesk.exe"))) {
    throw "Installed GitDesk.exe missing."
}
python packaging/smoke_test.py (Join-Path $Target "GitDesk.exe")
if ($LASTEXITCODE -ne 0) { throw "Installed application smoke test failed." }
if (-not (Test-Path $Uninstall)) { throw "Uninstaller missing: $Uninstall" }
$uninstallProcess = Start-Process -FilePath $Uninstall -ArgumentList @("/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait -PassThru
if ($uninstallProcess.ExitCode -ne 0) { throw "Uninstaller failed: $($uninstallProcess.ExitCode)" }
Write-Host "Windows install, launch and uninstall verification passed."
