# 打包 Windows 可执行文件（单文件 GUI）。在仓库根目录执行：.\tools\build_exe.ps1
# 产物：dist\rekindle.exe（未签名，首次运行 Windows 可能提示 SmartScreen）
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = if (Test-Path (Join-Path $root '.venv\Scripts\python.exe')) { Join-Path $root '.venv\Scripts\python.exe' } else { 'python' }
Push-Location $root
try {
    & $python tools\make_version_info.py
    & $python -m PyInstaller `
        --noconfirm --clean --onefile --windowed `
        --name rekindle `
        --paths src `
        --icon assets\rekindle.ico `
        --version-file build\version_info.txt `
        --add-data "assets\rekindle.ico;assets" `
        --distpath dist --workpath build `
        tools\entry_gui.py
} finally {
    Pop-Location
}
$version = (& $python -c "import rekindle; print(rekindle.__version__)" | Select-Object -Last 1).Trim()
$versioned = Join-Path $root "dist\rekindle-v$version-win64.exe"
Copy-Item -Force (Join-Path $root 'dist\rekindle.exe') $versioned
Write-Host "`n已生成：$root\dist\rekindle.exe"
Write-Host "已生成：$versioned"
