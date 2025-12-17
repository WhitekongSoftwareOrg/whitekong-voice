$TargetFile = "c:\Users\abril\Proyectos\wisperkong\whitekong-voice\dist\WhiteKongVoice.exe"
$ShortcutName = "WhiteKong Voice"

$WScriptShell = New-Object -ComObject WScript.Shell

# 1. Acceso directo en Escritorio
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutFile = "$DesktopPath\$ShortcutName.lnk"
$Shortcut = $WScriptShell.CreateShortcut($ShortcutFile)
$Shortcut.TargetPath = $TargetFile
$Shortcut.Save()
Write-Host "Acceso directo creado en Escritorio: $ShortcutFile"

# 2. Acceso directo en Menú Inicio
$StartMenuPath = [Environment]::GetFolderPath("StartMenu")
$ProgramsPath = "$StartMenuPath\Programs"
if (-not (Test-Path $ProgramsPath)) { New-Item -ItemType Directory -Path $ProgramsPath | Out-Null }
$StartMenuShortcut = "$ProgramsPath\$ShortcutName.lnk"
$Shortcut = $WScriptShell.CreateShortcut($StartMenuShortcut)
$Shortcut.TargetPath = $TargetFile
$Shortcut.Save()
Write-Host "Acceso directo creado en Menú Inicio: $StartMenuShortcut"
