# Instagram Cleaner (Python + EXE)

[![Instagram](https://img.shields.io/badge/Instagram-pj.cy-E4405F?logo=instagram&logoColor=white)](https://instagram.com/pj.cy)

## English
Desktop app that logs into Instagram, checks accounts you follow that do not follow you back, and lets you unfollow them while keeping followers.

### Features
- Login with Instagram account.
- Fetch `not_following_back` list.
- Unfollow selected users.
- Unfollow all users in the list.
- Simple desktop GUI (Tkinter).
- Build to Windows EXE with PyInstaller.

### Project Files
- `app.py`: GUI application.
- `instagram_service.py`: Instagram API logic using `instagrapi`.
- `build_exe.bat`: Build EXE.
- `RELEASE_NOTES.md`: Release notes.
- `LICENSE`: Proprietary license.

### Requirements
- Windows
- Python 3.10+

### Setup
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Run (Python)
```powershell
python app.py
```

### Build EXE
```powershell
.\build_exe.bat
```

EXE output:
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

Release output:
- `release\v1.0.1\InstagramCleaner.exe`
- `release\InstagramCleaner-v1.0.1.zip`

### Notes
- Instagram may temporarily limit actions if too many unfollows are made quickly.
- Use delay 2-4 seconds between unfollow actions for safer operation.
- This tool uses your own credentials locally and stores session in `session.json`.
- You are responsible for complying with Instagram Terms of Use.

## العربية
تطبيق سطح مكتب يسجّل دخول إنستغرام، ويعرض الحسابات التي تتابعها لكنها لا تتابعك، ثم يسمح لك بإزالة متابعتها مع الإبقاء على من يتابعك.

### المميزات
- تسجيل الدخول بحساب إنستغرام.
- جلب قائمة `not_following_back`.
- إزالة متابعة حسابات محددة.
- إزالة متابعة كل الحسابات الموجودة في القائمة.
- واجهة بسيطة (Tkinter).
- تحويل التطبيق إلى ملف EXE على ويندوز عبر PyInstaller.

### ملفات المشروع
- `app.py`: واجهة التطبيق.
- `instagram_service.py`: منطق التعامل مع Instagram API باستخدام `instagrapi`.
- `build_exe.bat`: بناء ملف EXE.
- `RELEASE_NOTES.md`: ملاحظات الإصدار.
- `LICENSE`: ترخيص ملكية خاصة.

### المتطلبات
- نظام Windows
- Python 3.10 أو أحدث

### التثبيت
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### التشغيل (بايثون)
```powershell
python app.py
```

### بناء EXE
```powershell
.\build_exe.bat
```

ناتج البناء:
- `dist\InstagramCleaner.exe`

### إنشاء حزمة إصدار
```powershell
New-Item -ItemType Directory -Force -Path release\v1.0.1 | Out-Null
Copy-Item dist\InstagramCleaner.exe release\v1.0.1\InstagramCleaner.exe -Force
Copy-Item README.md release\v1.0.1\README.md -Force
Copy-Item RELEASE_NOTES.md release\v1.0.1\RELEASE_NOTES.md -Force
Copy-Item LICENSE release\v1.0.1\LICENSE -Force
Compress-Archive -Path release\v1.0.1\* -DestinationPath release\InstagramCleaner-v1.0.1.zip -Force
```

ناتج الإصدار:
- `release\v1.0.1\InstagramCleaner.exe`
- `release\InstagramCleaner-v1.0.1.zip`

### ملاحظات
- قد يفرض إنستغرام قيودًا مؤقتة عند تنفيذ عدد كبير من عمليات إلغاء المتابعة بسرعة.
- يفضل استخدام تأخير من 2 إلى 4 ثوانٍ بين كل عملية إلغاء متابعة.
- يتم حفظ الجلسة محليًا في `session.json`.
- أنت المسؤول عن الالتزام بشروط استخدام إنستغرام.
