# Create a GitDesk desktop shortcut with the application icon.
# Usage: powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$icon = Join-Path $here "assets\gitdesk.ico"
$pythonw = (Get-Command pythonw -ErrorAction Stop).Source
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut(
    (Join-Path $desktop "GitDesk.lnk"))
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + (Join-Path $here "gitdesk.pyw") + '"'
$shortcut.WorkingDirectory = $here
$shortcut.IconLocation = $icon
$shortcut.Description = "GitDesk - Native Git desktop client"
$shortcut.Save()
Write-Host "Created: $(Join-Path $desktop 'GitDesk.lnk')"
