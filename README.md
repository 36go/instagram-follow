# Instagram Cleaner (Python + EXE)

[![Instagram](https://img.shields.io/badge/Instagram-pj.cy-E4405F?logo=instagram&logoColor=white)](https://instagram.com/pj.cy)

## English
Desktop app to manage Instagram follow cleanup:
- Login with API (`instagrapi`) or visible Chrome automation (`undetected-chromedriver + selenium`).
- Detect accounts you follow that do not follow you back.
- Unfollow selected users or all listed users.
- Built-in error detector for login/challenge/rate-limit messages.

### Chrome Requirement
- Google Chrome must be installed.
- Chrome language can be English or Arabic.
- If Instagram shows "Are you a robot?" use `Chrome Login` in the app and complete the challenge manually in the opened browser.

### Project Files
- `app.py`: GUI application.
- `instagram_service.py`: Instagram logic and Chrome login flow.
- `assets/app_icon.ico`: App icon.
- `build_exe.bat`: EXE build script.
- `requirements.txt`: Python dependencies.
- `LICENSE`: Proprietary license.
- `RELEASE_NOTES.md`: Release notes.

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
New-Item -ItemType Directory -Force -Path release\v1.0.1 | Out-Null
Copy-Item dist\InstagramCleaner.exe release\v1.0.1\InstagramCleaner.exe -Force
Copy-Item README.md release\v1.0.1\README.md -Force
Copy-Item RELEASE_NOTES.md release\v1.0.1\RELEASE_NOTES.md -Force
Copy-Item LICENSE release\v1.0.1\LICENSE -Force
Compress-Archive -Path release\v1.0.1\* -DestinationPath release\InstagramCleaner-v1.0.1.zip -Force
```

## العربية
تطبيق سطح مكتب لإدارة تنظيف المتابعات في إنستغرام:
- تسجيل دخول عبر API (`instagrapi`) أو عبر كروم ظاهر (`undetected-chromedriver + selenium`).
- اكتشاف الحسابات التي تتابعها ولا تتابعك.
- إلغاء متابعة حسابات محددة أو كل القائمة.
- كاشف أخطاء داخل التطبيق يوضح حالة تسجيل الدخول والتحديات.

### متطلب كروم
- لازم يكون Google Chrome مثبت.
- لغة كروم ممكن تكون عربي أو إنجليزي.
- إذا ظهر لك "Are you a robot?" استخدم زر `Chrome Login` داخل التطبيق وكمل التحقق يدويًا داخل المتصفح المفتوح.

### ملفات المشروع
- `app.py`: واجهة التطبيق.
- `instagram_service.py`: منطق إنستغرام ومسار تسجيل الدخول عبر كروم.
- `assets/app_icon.ico`: أيقونة التطبيق.
- `build_exe.bat`: سكربت بناء EXE.
- `requirements.txt`: المكتبات المطلوبة.
- `LICENSE`: ترخيص ملكية خاصة.
- `RELEASE_NOTES.md`: ملاحظات الإصدار.

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
New-Item -ItemType Directory -Force -Path release\v1.0.1 | Out-Null
Copy-Item dist\InstagramCleaner.exe release\v1.0.1\InstagramCleaner.exe -Force
Copy-Item README.md release\v1.0.1\README.md -Force
Copy-Item RELEASE_NOTES.md release\v1.0.1\RELEASE_NOTES.md -Force
Copy-Item LICENSE release\v1.0.1\LICENSE -Force
Compress-Archive -Path release\v1.0.1\* -DestinationPath release\InstagramCleaner-v1.0.1.zip -Force
```

## Notes
- Instagram can temporarily rate-limit or challenge automated actions.
- Keep delay around 2-5 seconds for safer unfollow operations.
- You are responsible for compliance with Instagram Terms of Use.
