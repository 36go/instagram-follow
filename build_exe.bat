@echo off
setlocal

echo [1/3] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [2/3] Building EXE with PyInstaller...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name InstagramCleaner ^
  app.py

if not exist dist\InstagramCleaner.exe (
  echo [ERROR] Build failed. EXE not found.
  exit /b 1
)

echo [3/3] Build complete.
echo EXE path: dist\InstagramCleaner.exe
endlocal
