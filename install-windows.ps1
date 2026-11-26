# Create a GitDesk desktop shortcut with the application icon.
# Prefer native GitDesk.exe so the Windows taskbar uses the correct icon.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$icon = Join-Path $here "assets\gitdesk.ico"
$native = Join-Path $here "dist\GitDesk\GitDesk.exe"
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut(
    (Join-Path $desktop "GitDesk.lnk"))
if (Test-Path $native) {
    $shortcut.TargetPath = $native
    $shortcut.Arguments = ""
    $shortcut.WorkingDirectory = Split-Path -Parent $native
    $shortcut.IconLocation = $native + ",0"
} else {
    $pythonw = (Get-Command pythonw -ErrorAction Stop).Source
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = '"' + (Join-Path $here "gitdesk.pyw") + '"'
    $shortcut.WorkingDirectory = $here
    $shortcut.IconLocation = $icon
}
$shortcut.Description = "GitDesk - Native Git desktop client"
$shortcut.Save()
Write-Host "Created: $(Join-Path $desktop 'GitDesk.lnk')"
Write-Host "Target: $($shortcut.TargetPath)"
