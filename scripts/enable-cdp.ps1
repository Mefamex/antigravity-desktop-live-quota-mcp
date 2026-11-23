# Patches Antigravity Desktop Windows shortcuts (.lnk) with --remote-debugging-port=0
# so Chrome DevTools Protocol (CDP) is enabled for Live Quota Bar injection.

$ErrorActionPreference = "Stop"

$wsh = New-Object -ComObject WScript.Shell
$searchDirs = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) ''),
    (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'),
    (Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'Microsoft\Windows\Start Menu\Programs'),
    (Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar')
) | Where-Object { $_ -and (Test-Path $_) }

$patched = @()
$already = @()
$errors = @()

$shortcuts = @()
foreach ($dir in $searchDirs) {
    $shortcuts += Get-ChildItem -Path $dir -Filter '*Antigravity*.lnk' -Recurse -ErrorAction SilentlyContinue
}

foreach ($item in ($shortcuts | Sort-Object -Property FullName -Unique)) {
    try {
        $sc = $wsh.CreateShortcut($item.FullName)
        $target = [string]$sc.TargetPath
        if ($target -notmatch 'antigravity' -or $target -match 'antigravity-ide') {
            continue
        }
        $args = [string]$sc.Arguments
        if ($args -match '--remote-debugging-port') {
            $already += $item.FullName
            continue
        }
        $sc.Arguments = ("--remote-debugging-port=0 " + $args).Trim()
        $sc.Save()
        $patched += $item.FullName
    } catch {
        $errors += "$($item.FullName): $($_.Exception.Message)"
    }
}

$result = [ordered]@{
    ok = ($patched.Count -gt 0 -or $already.Count -gt 0) -and ($errors.Count -eq 0)
    patched = $patched
    already_enabled = $already
    errors = $errors
}
$result | ConvertTo-Json -Compress
