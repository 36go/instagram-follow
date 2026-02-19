# Instagram Cleaner (Python + EXE)

[![Instagram](https://img.shields.io/badge/Instagram-pj.cy-E4405F?logo=instagram&logoColor=white)](https://instagram.com/pj.cy)

## English
Desktop app for Instagram follow cleanup.

### Current Login Flow
- The `Login` button opens a visible Chrome window.
- You sign in manually inside Instagram in Chrome.
- After successful sign-in, the app imports session and automatically starts counting accounts that do not follow you back.

### Features
- Browser-based automation powered by `selenium + undetected-chromedriver`.
- Detect accounts you follow that do not follow you back.
- Unfollow selected users or all listed users.
- In-app error detector for challenge/rate-limit/login problems.

### Requirements
- Windows
- Python 3.10+
- Google Chrome installed (Arabic or English UI both supported)

### Setup
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Run
```powershell
python app.py
```

### Build EXE
```powershell
.\build_exe.bat
```

Output:
- `dist\InstagramCleaner.exe`

### Create Release Package
```powershell
New-Item -ItemType Directory -Force -Path release\v1.0.5 | Out-Null
Copy-Item dist\InstagramCleaner.exe release\v1.0.5\InstagramCleaner.exe -Force
Copy-Item README.md release\v1.0.5\README.md -Force
Copy-Item RELEASE_NOTES.md release\v1.0.5\RELEASE_NOTES.md -Force
Copy-Item LICENSE release\v1.0.5\LICENSE -Force
Compress-Archive -Path release\v1.0.5\* -DestinationPath release\InstagramCleaner-v1.0.5.zip -Force
```

## العربية
تطبيق سطح مكتب لتنظيف المتابعات في إنستغرام.

### طريقة تسجيل الدخول الحالية
- زر `Login` هو نفسه الذي يفتح متصفح Chrome بشكل ظاهر.
- المستخدم يسجل الدخول يدويًا داخل إنستغرام من Chrome.
- بعد نجاح الدخول، التطبيق يأخذ الجلسة تلقائيًا ويبدأ مباشرة عدّ الحسابات التي لا تتابعك.

### المميزات
- أتمتة كاملة عبر `selenium + undetected-chromedriver`.
- اكتشاف الحسابات التي تتابعها ولا تتابعك.
- إلغاء متابعة حسابات محددة أو كل الحسابات في القائمة.
- كاشف أخطاء داخل التطبيق لحالات التحدي أو تقييد إنستغرام.

### المتطلبات
- Windows
- Python 3.10 أو أحدث
- وجود Google Chrome (سواء عربي أو إنجليزي)

### التثبيت
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### التشغيل
```powershell
python app.py
```

### بناء EXE
```powershell
.\build_exe.bat
```

الناتج:
- `dist\InstagramCleaner.exe`

### تجهيز ملف Release
```powershell
New-Item -ItemType Directory -Force -Path release\v1.0.5 | Out-Null
Copy-Item dist\InstagramCleaner.exe release\v1.0.5\InstagramCleaner.exe -Force
Copy-Item README.md release\v1.0.5\README.md -Force
Copy-Item RELEASE_NOTES.md release\v1.0.5\RELEASE_NOTES.md -Force
Copy-Item LICENSE release\v1.0.5\LICENSE -Force
Compress-Archive -Path release\v1.0.5\* -DestinationPath release\InstagramCleaner-v1.0.5.zip -Force
```

## Notes
- Instagram can challenge or rate-limit aggressive actions.
- Keep unfollow delay around 2-5 seconds.
- You are responsible for compliance with Instagram Terms of Use.
