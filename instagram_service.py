from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Callable
try:
    import winreg
except ImportError:  # pragma: no cover
    winreg = None

from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    CaptchaChallengeRequired,
    ClientJSONDecodeError,
    ChallengeRequired,
    FeedbackRequired,
    LoginRequired,
    PleaseWaitFewMinutes,
    RateLimitError,
    RecaptchaChallengeForm,
    TwoFactorRequired,
)
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import undetected_chromedriver as uc


class InstagramServiceError(Exception):
    """Raised when an Instagram operation fails."""


class VerificationCodeRequired(InstagramServiceError):
    """Raised when Instagram asks for a 2FA/verification code."""


ProgressCallback = Callable[[int, int, str, bool, str], None]


class InstagramService:
    def __init__(self, session_path: str) -> None:
        self.client = Client()
        self.session_path = Path(session_path)
        self.is_logged_in = False

    def login(self, username: str, password: str, verification_code: str = "") -> None:
        username = username.strip().lstrip("@")
        password = password.strip()
        verification_code = verification_code.strip()
        if not username or not password:
            raise InstagramServiceError("Username and password are required.")

        self._load_session_settings()

        try:
            logged_in = self.client.login(username, password, verification_code=verification_code)
        except BadPassword as exc:
            raise InstagramServiceError("Wrong password.") from exc
        except (CaptchaChallengeRequired, RecaptchaChallengeForm) as exc:
            raise InstagramServiceError(
                "Instagram asked for bot verification (captcha). "
                "Open Instagram app/site, complete verification, then try login again."
            ) from exc
        except TwoFactorRequired as exc:
            if not verification_code:
                raise VerificationCodeRequired(
                    "Instagram requested a verification code (2FA)."
                ) from exc
            raise InstagramServiceError(
                "Verification code is incorrect or expired. Please try again."
            ) from exc
        except ChallengeRequired as exc:
            raise InstagramServiceError(
                "Instagram challenge required. Verify login from Instagram app/browser, then try again."
            ) from exc
        except Exception as exc:
            raise InstagramServiceError(f"Login failed: {exc}") from exc

        if not logged_in:
            raise InstagramServiceError("Login failed. Check your credentials and try again.")

        self.client.dump_settings(str(self.session_path))
        self.is_logged_in = True

    def login_with_browser(self, username: str = "", timeout_seconds: int = 300) -> None:
        username = username.strip().lstrip("@")
        driver = None

        try:
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-notifications")
            options.add_argument("--lang=en-US")
            chrome_path = self._find_chrome_binary()
            if not chrome_path:
                raise InstagramServiceError(
                    "Google Chrome was not found. Install Chrome or set CHROME_PATH to chrome.exe."
                )
            driver_kwargs = {"options": options, "use_subprocess": True}
            # Selenium requires binary path to be a plain string.
            driver_kwargs["browser_executable_path"] = str(chrome_path)
            driver = uc.Chrome(**driver_kwargs)
            driver.get("https://www.instagram.com/accounts/login/")

            if username:
                try:
                    user_input = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.NAME, "username"))
                    )
                    user_input.clear()
                    user_input.send_keys(username)
                except TimeoutException:
                    pass

            sessionid = self._wait_for_session_cookie(driver, timeout_seconds)
            self._import_session_with_retry(sessionid=sessionid, retries=3, sleep_seconds=3)
            self.client.dump_settings(str(self.session_path))
            self.is_logged_in = True
        except InstagramServiceError:
            raise
        except Exception as exc:
            raise self._wrap_instagram_error(exc, "Browser login failed")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def get_not_following_back(self) -> list[str]:
        self._ensure_login()
        try:
            my_user_id = self.client.user_id
            if my_user_id is None:
                my_user_id = self.client.user_id_from_username(self.client.username)
            following = self.client.user_following(my_user_id)
            followers = self.client.user_followers(my_user_id)
        except Exception as exc:
            raise self._wrap_instagram_error(exc, "Failed to load data")

        not_following_back = [
            user.username for user_id, user in following.items() if user_id not in followers
        ]
        not_following_back.sort(key=str.lower)
        return not_following_back

    def unfollow_users(
        self,
        usernames: list[str],
        delay_seconds: float = 2.0,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, list[str]]:
        self._ensure_login()

        removed: list[str] = []
        failed: list[str] = []
        total = len(usernames)

        for index, username in enumerate(usernames, start=1):
            cleaned = username.strip().lstrip("@")
            success = False
            error_message = ""

            if not cleaned:
                failed.append(f"{username}: empty username")
                if progress_callback:
                    progress_callback(index, total, username, False, "Empty username.")
                continue

            try:
                target_id = self.client.user_id_from_username(cleaned)
                success = self.client.user_unfollow(target_id)
                if success:
                    removed.append(cleaned)
                else:
                    error_message = "API returned False."
                    failed.append(f"{cleaned}: {error_message}")
            except Exception as exc:
                error_message = self._wrap_instagram_error(exc, "Unfollow failed").args[0]
                failed.append(f"{cleaned}: {error_message}")

            if progress_callback:
                progress_callback(index, total, cleaned, success, error_message)

            if index < total:
                time.sleep(max(delay_seconds, 0.5))

        self.client.dump_settings(str(self.session_path))
        return {"removed": removed, "failed": failed}

    def _ensure_login(self) -> None:
        if self.is_logged_in:
            return
        if not self.session_path.exists():
            raise InstagramServiceError("Not logged in. Please login first.")

        try:
            self._load_session_settings()
            self.client.get_timeline_feed()
            self.is_logged_in = True
        except LoginRequired as exc:
            raise InstagramServiceError("Session expired. Please login again.") from exc
        except Exception as exc:
            raise InstagramServiceError(f"Session is invalid. Please login again. ({exc})") from exc

    def _load_session_settings(self) -> None:
        if not self.session_path.exists():
            return
        try:
            self.client.load_settings(str(self.session_path))
        except (json.JSONDecodeError, ValueError):
            # Recover from broken or empty session files.
            self.session_path.unlink(missing_ok=True)
        except Exception:
            # Keep login flow resilient for any unreadable settings format.
            self.session_path.unlink(missing_ok=True)

    def _wrap_instagram_error(self, exc: Exception, prefix: str) -> InstagramServiceError:
        if "binary location must be a string" in str(exc).lower():
            return InstagramServiceError(
                f"{prefix}: Chrome binary path issue detected. "
                "Reinstall/update Google Chrome, then retry."
            )
        if isinstance(exc, WebDriverException):
            return InstagramServiceError(
                f"{prefix}: Could not start Chrome automation. "
                "Make sure Google Chrome is installed and updated."
            )
        if isinstance(exc, (CaptchaChallengeRequired, RecaptchaChallengeForm)):
            return InstagramServiceError(
                f"{prefix}: Instagram asked for bot verification. "
                "Complete captcha/challenge in Instagram app, then retry."
            )
        if isinstance(exc, ChallengeRequired):
            return InstagramServiceError(
                f"{prefix}: Instagram challenge required. "
                "Approve login in Instagram app/browser, then retry."
            )
        if isinstance(exc, (RateLimitError, PleaseWaitFewMinutes, FeedbackRequired)):
            return InstagramServiceError(
                f"{prefix}: Instagram temporarily limited actions. "
                "Wait a while, increase delay to 3-5 seconds, then try again."
            )
        return InstagramServiceError(f"{prefix}: {exc}")

    def _wait_for_session_cookie(self, driver, timeout_seconds: int) -> str:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            session_cookie = driver.get_cookie("sessionid")
            user_cookie = driver.get_cookie("ds_user_id")
            if (
                session_cookie
                and session_cookie.get("value")
                and user_cookie
                and user_cookie.get("value")
            ):
                return str(session_cookie["value"])
            time.sleep(2)
        raise InstagramServiceError(
            "Browser login timeout. Complete login/challenge in Chrome until fully signed in, then retry."
        )

    def _import_session_with_retry(self, sessionid: str, retries: int = 3, sleep_seconds: int = 3) -> None:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self.client = Client()
                self.client.login_by_sessionid(sessionid)
                return
            except (ClientJSONDecodeError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(sleep_seconds)
                    continue
                break
            except Exception as exc:
                last_error = exc
                break

        if last_error:
            raise InstagramServiceError(
                "Browser login was completed, but Instagram API session import failed. "
                "Wait 20-30 seconds and press Login again."
            ) from last_error

    def _find_chrome_binary(self) -> str | None:
        for env_name in ("CHROME_PATH", "CHROME_BIN"):
            env_path = os.environ.get(env_name, "").strip().strip('"')
            if env_path and Path(env_path).exists():
                return str(Path(env_path))

        registry_paths = self._find_chrome_from_registry()
        if registry_paths:
            return registry_paths

        candidates = [
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome Beta/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome Beta/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome Dev/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome Dev/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome SxS/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome SxS/Application/chrome.exe",
        ]

        for path in candidates:
            if str(path) and path.exists():
                return str(path)

        for command_name in ("chrome.exe", "chrome", "google-chrome", "google-chrome-stable"):
            found = shutil.which(command_name)
            if found:
                return str(found)

        return None

    def _find_chrome_from_registry(self) -> str | None:
        if winreg is None:
            return None

        keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        ]

        for hive, subkey in keys:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    if value and Path(value).exists():
                        return str(Path(value))
            except OSError:
                continue

        return None
