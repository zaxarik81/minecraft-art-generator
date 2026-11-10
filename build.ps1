$ErrorActionPreference = "Stop"
$appRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $appRoot
py -3.13 -m pip install -r requirements.txt
py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --name MineSchematic app.py --distpath dist-schematic-new --workpath build-schematic-new
py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --name MinePixelArt pixel_art.py --distpath dist-pixel --workpath build-pixel
Write-Host "Готово: $appRoot\dist-schematic-new\MineSchematic.exe"
Write-Host "Готово: $appRoot\dist-pixel\MinePixelArt.exe"
