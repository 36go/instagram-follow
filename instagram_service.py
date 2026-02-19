from __future__ import annotations

import os
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

try:
    import winreg
except ImportError:  # pragma: no cover
    winreg = None

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class InstagramServiceError(Exception):
    """Raised when an Instagram operation fails."""


ProgressCallback = Callable[[int, int, str, bool, str], None]


class InstagramService:
    RESERVED_PATHS = {
        "accounts",
        "about",
        "api",
        "challenge",
        "developer",
        "direct",
        "explore",
        "legal",
        "reel",
        "reels",
        "stories",
        "web",
        "p",
        "tv",
    }

    FOLLOW_KEYWORDS = {
        "follow",
        "follow back",
        "متابعة",
        "تابع",
    }

    FOLLOWING_KEYWORDS = {
        "following",
        "requested",
        "يتابع",
        "تمت المتابعة",
        "طلب الإرسال",
        "طلب ارسال",
    }

    UNFOLLOW_KEYWORDS = {
        "unfollow",
        "إلغاء المتابعة",
        "الغاء المتابعة",
    }

    def __init__(self, session_path: str) -> None:
        self.session_path = Path(session_path)
        self.profile_dir = Path("chrome_profile")
        self.driver = None
        self.lock = threading.RLock()
        self.username: str | None = None

    def login(self, username: str, password: str, verification_code: str = "") -> None:
        raise InstagramServiceError("Password login is disabled. Use browser login only.")

    def login_with_browser(self, username: str = "", timeout_seconds: int = 300) -> None:
        username = username.strip().lstrip("@")

        with self.lock:
            self._ensure_driver()
            self.driver.get("https://www.instagram.com/accounts/login/")
            self._dismiss_cookie_banner()

            if username:
                self._fill_username_hint(username)

            self._wait_for_login_success(timeout_seconds)
            self.username = self._resolve_logged_in_username()
            if not self.username:
                raise InstagramServiceError(
                    "Logged in, but failed to detect account username. Open your profile once, then retry."
                )

    def get_not_following_back(self) -> list[str]:
        with self.lock:
            self._ensure_logged_in()
            following = self._collect_user_list(self.username, "following")
            followers = self._collect_user_list(self.username, "followers")

        not_following_back = sorted((set(following) - set(followers)), key=str.lower)
        return not_following_back

    def unfollow_users(
        self,
        usernames: list[str],
        delay_seconds: float = 2.0,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, list[str]]:
        with self.lock:
            self._ensure_logged_in()

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
                    success, error_message = self._unfollow_single(cleaned)
                    if success:
                        removed.append(cleaned)
                    else:
                        failed.append(f"{cleaned}: {error_message}")
                except Exception as exc:  # defensive to continue bulk flow
                    error_message = str(exc)
                    failed.append(f"{cleaned}: {error_message}")

                if progress_callback:
                    progress_callback(index, total, cleaned, success, error_message)

                if index < total:
                    time.sleep(max(delay_seconds, 0.5))

        return {"removed": removed, "failed": failed}

    def close_browser(self) -> None:
        with self.lock:
            if self.driver is not None:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

    def _ensure_driver(self) -> None:
        if self.driver is not None:
            try:
                _ = self.driver.current_url
                return
            except Exception:
                self.driver = None

        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--lang=en-US")

        chrome_path = self._find_chrome_binary()
        if not chrome_path:
            raise InstagramServiceError(
                "Google Chrome was not found. Install Chrome or set CHROME_PATH to chrome.exe."
            )

        self.profile_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.driver = uc.Chrome(
                options=options,
                browser_executable_path=str(chrome_path),
                user_data_dir=str(self.profile_dir.resolve()),
                use_subprocess=True,
            )
        except TypeError as exc:
            raise InstagramServiceError(
                "Chrome startup failed. Update Chrome and undetected-chromedriver."
            ) from exc
        except WebDriverException as exc:
            raise InstagramServiceError(
                "Could not start Chrome automation. Make sure Google Chrome is installed and updated."
            ) from exc

    def _wait_for_login_success(self, timeout_seconds: int) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                current_url = self.driver.current_url.lower()
            except Exception:
                current_url = ""

            session_cookie = self.driver.get_cookie("sessionid")
            user_cookie = self.driver.get_cookie("ds_user_id")
            logged_in = (
                session_cookie
                and session_cookie.get("value")
                and user_cookie
                and user_cookie.get("value")
                and "/accounts/login" not in current_url
            )

            if logged_in:
                return

            time.sleep(2)

        raise InstagramServiceError(
            "Browser login timeout. Complete login/challenge in Chrome, then retry."
        )

    def _fill_username_hint(self, username: str) -> None:
        try:
            user_input = WebDriverWait(self.driver, 12).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            user_input.clear()
            user_input.send_keys(username)
        except TimeoutException:
            return

    def _dismiss_cookie_banner(self) -> None:
        labels = {
            "allow all cookies",
            "only allow essential cookies",
            "accept all",
            "السماح بكل ملفات تعريف الارتباط",
            "السماح بالضرورية فقط",
            "قبول الكل",
        }
        try:
            buttons = self.driver.find_elements(By.XPATH, "//button")
            for button in buttons:
                text = self._normalize_text(button.text)
                if text in labels:
                    try:
                        button.click()
                        time.sleep(0.7)
                    except Exception:
                        pass
                    return
        except Exception:
            return

    def _resolve_logged_in_username(self) -> str | None:
        self.driver.get("https://www.instagram.com/accounts/edit/")
        try:
            username_input = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            value = (username_input.get_attribute("value") or "").strip().lstrip("@")
            if value:
                return value
        except TimeoutException:
            pass

        try:
            self.driver.get("https://www.instagram.com/")
            links = self.driver.find_elements(By.XPATH, "//a[contains(@href,'instagram.com') or starts-with(@href,'/')]")
            for link in links:
                href = link.get_attribute("href") or ""
                candidate = self._username_from_href(href)
                if candidate:
                    return candidate
        except Exception:
            pass

        return None

    def _ensure_logged_in(self) -> None:
        if self.driver is None:
            raise InstagramServiceError("Not logged in. Press Login first.")
        try:
            _ = self.driver.current_url
        except Exception as exc:
            self.driver = None
            raise InstagramServiceError("Browser session closed. Press Login again.") from exc

        if not self.username:
            self.username = self._resolve_logged_in_username()
        if not self.username:
            raise InstagramServiceError("Could not detect your Instagram username after login.")

    def _collect_user_list(self, username: str, relation: str) -> list[str]:
        relation = relation.strip().lower()
        if relation not in {"following", "followers"}:
            raise InstagramServiceError(f"Unsupported relation: {relation}")

        self.driver.get(f"https://www.instagram.com/{username}/{relation}/")
        try:
            dialog = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
            )
        except TimeoutException as exc:
            raise InstagramServiceError(
                f"Could not open {relation} list. Open your profile manually and retry."
            ) from exc

        usernames: set[str] = set()
        last_size = 0
        stable_rounds = 0

        for _ in range(220):
            usernames.update(self._extract_usernames(dialog))

            if len(usernames) == last_size:
                stable_rounds += 1
            else:
                stable_rounds = 0
                last_size = len(usernames)

            if stable_rounds >= 4:
                break

            scroll_box = self._find_scroll_box(dialog)
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scroll_box)
            time.sleep(0.7)

        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass

        return sorted(usernames, key=str.lower)

    def _extract_usernames(self, dialog) -> set[str]:
        usernames: set[str] = set()
        try:
            links = dialog.find_elements(By.XPATH, ".//a[contains(@href, '/')]")
            for link in links:
                href = link.get_attribute("href") or ""
                candidate = self._username_from_href(href)
                if candidate:
                    usernames.add(candidate)
        except Exception:
            pass
        return usernames

    def _find_scroll_box(self, dialog):
        xpaths = [
            ".//div[contains(@style,'overflow: hidden auto')]",
            ".//div[contains(@style,'overflow-y: auto')]",
            ".//div[contains(@style,'overflow: auto')]",
        ]
        for xpath in xpaths:
            elements = dialog.find_elements(By.XPATH, xpath)
            if elements:
                return elements[0]
        return dialog

    def _username_from_href(self, href: str) -> str | None:
        if not href:
            return None

        parsed = urlparse(href)
        path = parsed.path if parsed.path else href
        if not path:
            return None

        clean = path.strip("/")
        if not clean:
            return None
        first = clean.split("/")[0]
        if not first:
            return None

        normalized = first.lower()
        if normalized in self.RESERVED_PATHS:
            return None

        if not re.match(r"^[A-Za-z0-9._]+$", first):
            return None

        return first

    def _unfollow_single(self, username: str) -> tuple[bool, str]:
        self.driver.get(f"https://www.instagram.com/{username}/")
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//header"))
            )
        except TimeoutException as exc:
            return False, f"Profile did not load for @{username}."

        button = self._find_follow_button()
        if button is None:
            return False, "Could not detect follow state button."

        label = self._normalize_text(button.text or button.get_attribute("aria-label") or "")

        if self._is_follow_label(label):
            return True, "Already not following."

        if not self._is_following_label(label):
            return False, f"Unknown follow button text: '{label or 'empty'}'"

        try:
            button.click()
            time.sleep(0.8)
        except Exception as exc:
            return False, f"Failed to click Following button: {exc}"

        if not self._click_unfollow_confirmation():
            # Some UIs do immediate unfollow without dialog.
            pass

        time.sleep(1.0)
        return True, ""

    def _find_follow_button(self):
        selectors = [
            "//header//button",
            "//header//div[@role='button']",
        ]

        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
            except Exception:
                continue

            for element in elements:
                text = self._normalize_text(element.text or element.get_attribute("aria-label") or "")
                if self._is_follow_label(text) or self._is_following_label(text):
                    return element

        return None

    def _click_unfollow_confirmation(self) -> bool:
        try:
            buttons = self.driver.find_elements(By.XPATH, "//div[@role='dialog']//button | //button")
            for button in buttons:
                text = self._normalize_text(button.text)
                if any(keyword in text for keyword in self._normalized_keywords(self.UNFOLLOW_KEYWORDS)):
                    try:
                        button.click()
                        return True
                    except Exception:
                        continue
        except Exception:
            return False
        return False

    def _is_follow_label(self, text: str) -> bool:
        value = self._normalize_text(text)
        return any(keyword in value for keyword in self._normalized_keywords(self.FOLLOW_KEYWORDS))

    def _is_following_label(self, text: str) -> bool:
        value = self._normalize_text(text)
        return any(keyword in value for keyword in self._normalized_keywords(self.FOLLOWING_KEYWORDS))

    def _normalized_keywords(self, keywords: set[str]) -> list[str]:
        return [self._normalize_text(keyword) for keyword in keywords]

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.strip().lower().split())

    def _find_chrome_binary(self) -> str | None:
        for env_name in ("CHROME_PATH", "CHROME_BIN"):
            env_path = os.environ.get(env_name, "").strip().strip('"')
            if env_path and Path(env_path).exists():
                return str(Path(env_path))

        registry_path = self._find_chrome_from_registry()
        if registry_path:
            return registry_path

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
