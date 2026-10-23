param([string]$Python = ".\.venv\Scripts\python.exe")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force build | Out-Null
@'
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PIL import Image
image = QImage(256, 256, QImage.Format.Format_ARGB32)
image.fill(0)
painter = QPainter(image)
QSvgRenderer('cat_analyst/assets/logo.svg').render(painter)
painter.end()
image.save('build/logo.png')
Image.open('build/logo.png').save('build/logo.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
'@ | & $Python -
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }
& $Python -m PyInstaller --noconfirm --onefile --windowed --noupx --name CAT-Analyst --specpath build --paths "$PSScriptRoot" --collect-all rapidocr_onnxruntime --add-data "${PSScriptRoot}/cat_analyst/assets:cat_analyst/assets" --icon "$PSScriptRoot/build/logo.ico" --exclude-module tkinter --exclude-module pytest cat_analyst/__main__.py
if ($LASTEXITCODE -ne 0) { throw "Executable build failed" }
New-Item -ItemType Directory -Force release | Out-Null
$report = Join-Path $PSScriptRoot "release\self-test.json"
$process = Start-Process -FilePath "$PSScriptRoot\dist\CAT-Analyst.exe" -ArgumentList @('--self-test', ('"' + $report + '"')) -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Executable self-test failed: $report" }
if (!(Get-Content $report -Raw | ConvertFrom-Json).ok) { throw "Invalid self-test result" }
Copy-Item dist\CAT-Analyst.exe release\CAT-Analyst.exe -Force
(Get-FileHash release\CAT-Analyst.exe -Algorithm SHA256).Hash + '  CAT-Analyst.exe' | Set-Content release\SHA256SUMS.txt
Write-Host "Ready: release\CAT-Analyst.exe"
