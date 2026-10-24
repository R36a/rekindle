# 打包 Windows 可执行文件（单文件 GUI）。在仓库根目录执行：.\tools\build_exe.ps1
# 产物：dist\rekindle.exe（未签名，首次运行 Windows 可能提示 SmartScreen）
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & .\.venv\Scripts\python.exe tools\make_version_info.py
    & .\.venv\Scripts\python.exe -m PyInstaller `
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
Write-Host "`n已生成：$root\dist\rekindle.exe"
