# Release v1.0.2

## Added
- Desktop GUI app to login to Instagram.
- Detect accounts you follow that do not follow you back.
- Unfollow selected users or all listed users.
- Local session reuse (`session.json`) to reduce repeated login prompts.
- Windows EXE build pipeline via PyInstaller.
- Visible Chrome login mode using `undetected-chromedriver + selenium`.
- Session import from browser login to continue actions in the app.
- Login error detector enhancements for captcha/challenge/rate-limit cases.

## Changed
- Updated README to include both English and Arabic documentation.
- Updated license to proprietary copyright terms for `@pj.cy`.
- Release package now includes `LICENSE`.

## Artifacts
- `InstagramCleaner.exe`
