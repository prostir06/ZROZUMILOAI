# Копіює тему zrozumilo у каталог Tutor Open edX themes.
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ThemeSrc = Join-Path $ScriptDir 'zrozumilo'

$tutor = Get-Command tutor -ErrorAction SilentlyContinue
if (-not $tutor) {
  Write-Error 'tutor не знайдено в PATH'
}

$Root = & tutor config printroot
$ThemeDir = Join-Path $Root 'env\build\openedx\themes\zrozumilo'

New-Item -ItemType Directory -Force -Path $ThemeDir | Out-Null
Copy-Item -Recurse -Force (Join-Path $ThemeSrc 'lms') $ThemeDir
Copy-Item -Force (Join-Path $ThemeSrc 'theme.conf') $ThemeDir

Write-Host "Тему скопійовано в: $ThemeDir"
Write-Host 'Далі:'
Write-Host '  tutor local do settheme zrozumilo'
Write-Host '  tutor config save --set ZROZUMILOAI_WIDGET_JS_URL=https://chat.example.com/widget.js'
Write-Host '  tutor config save --set ZROZUMILOAI_WIDGET_TOKEN=wt_ВАШ_TOKEN'
Write-Host '  tutor images build openedx; tutor local restart'
