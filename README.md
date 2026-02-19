# Instagram Cleaner (Python + EXE)

Desktop app that logs into Instagram, checks accounts you follow that do not follow you back, and lets you unfollow them while keeping followers.

[![Instagram](https://img.shields.io/badge/Instagram-pj.cy-E4405F?logo=instagram&logoColor=white)](https://instagram.com/pj.cy)

## Features
- Login with Instagram account.
- Fetch `not_following_back` list.
- Unfollow selected users.
- Unfollow all users in the list.
- Simple desktop GUI (Tkinter).
- Build to Windows EXE with PyInstaller.

## Project Files
- `app.py`: GUI application.
- `instagram_service.py`: Instagram API logic using `instagrapi`.
- `build_exe.bat`: Build EXE.
- `make_release.ps1`: Prepare release folder + zip.
- `RELEASE_NOTES.md`: Release notes.

## Requirements
- Windows
- Python 3.10+

## Setup
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run (Python)
```powershell
python app.py
```

## Build EXE
```powershell
.\build_exe.bat
```

EXE output:
- `dist\InstagramCleaner.exe`

## Create Release Package
```powershell
.\make_release.ps1 -Version v1.0.0
```

Release output:
- `release\v1.0.0\InstagramCleaner.exe`
- `release\InstagramCleaner-v1.0.0.zip`

## Notes
- Instagram may temporarily limit actions if too many unfollows are made quickly.
- Use delay 2-4 seconds between unfollow actions for safer operation.
- This tool uses your own credentials locally and stores session in `session.json`.
- You are responsible for complying with Instagram Terms of Use.
