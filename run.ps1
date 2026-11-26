# GitDesk Qt 启动脚本（PowerShell）
# 用法： .\run.ps1 [仓库路径]
param([string]$RepoPath = "")

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$entry = Join-Path $here "gitdesk.pyw"
python -c "import PySide6" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "首次运行安装 PySide6 Essentials（不含浏览器内核）…"
    python -m pip install -r (Join-Path $here "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "依赖安装失败，请检查 Python 与网络。" }
}
$pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
if ($pythonw) {
    if ($RepoPath) { & $pythonw.Source $entry $RepoPath }
    else           { & $pythonw.Source $entry }
} else {
    if ($RepoPath) { & python $entry $RepoPath }
    else           { & python $entry }
}
