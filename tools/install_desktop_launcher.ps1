param([Parameter(Mandatory=$true)][string]$LauncherPath,
      [Parameter(Mandatory=$true)][string]$DistRoot)
$ErrorActionPreference = 'Stop'
$desktopPath = [Environment]::GetFolderPath('Desktop')
$desktopRoot = [IO.Path]::GetFullPath($desktopPath).TrimEnd('\') + '\'
$outputRoot = [IO.Path]::GetFullPath($DistRoot).TrimEnd('\') + '\'
$resolvedLauncher = [IO.Path]::GetFullPath($LauncherPath)
if (-not $resolvedLauncher.StartsWith($outputRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Launcher outside output directory' }
$archivePath = [IO.Path]::GetFullPath((Join-Path $DistRoot '桌面快捷方式备份'))
if (-not ($archivePath + '\').StartsWith($outputRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Shortcut archive outside output directory' }
$shell = New-Object -ComObject WScript.Shell
foreach ($file in Get-ChildItem -LiteralPath $desktopPath -Filter '*.lnk') {
    if ($file.Name -notmatch '^口袋妖怪-PC开发版[0-9.]+\.lnk$') { continue }
    $sourcePath = [IO.Path]::GetFullPath($file.FullName)
    if (-not $sourcePath.StartsWith($desktopRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Shortcut outside desktop' }
    $target = $shell.CreateShortcut($sourcePath).TargetPath
    if (-not $target -or -not ([IO.Path]::GetFullPath($target)).StartsWith($outputRoot, [StringComparison]::OrdinalIgnoreCase)) { continue }
    New-Item -ItemType Directory -Path $archivePath -Force | Out-Null
    $destination = Join-Path $archivePath $file.Name
    if (Test-Path -LiteralPath $destination) { $destination = Join-Path $archivePath ((Get-Date -Format 'yyyyMMddHHmmssfff') + '-' + $file.Name) }
    Move-Item -LiteralPath $sourcePath -Destination $destination
}
$shortcutPath = Join-Path $desktopPath '口袋妖怪.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $existing = $shell.CreateShortcut($shortcutPath).TargetPath
    if ($existing -ne $resolvedLauncher) {
        New-Item -ItemType Directory -Path $archivePath -Force | Out-Null
        Copy-Item -LiteralPath $shortcutPath -Destination (Join-Path $archivePath ('previous-' + (Get-Date -Format 'yyyyMMddHHmmssfff') + '.lnk'))
    }
}
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $resolvedLauncher
$shortcut.WorkingDirectory = Split-Path -LiteralPath $resolvedLauncher
$shortcut.Description = '启动最新完成更新的口袋妖怪单机版'
$shortcut.Save()
Write-Output $shortcutPath
