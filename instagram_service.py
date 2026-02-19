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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class InstagramServiceError(Exception):
    """Raised when an Instagram operation fails."""


ProgressCallback = Callable[[int, int, str, bool, str], None]
ListScanCallback = Callable[[str, int], None]


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

    ACTION_BLOCKED_KEYWORDS = {
        "try again later",
        "please wait a few minutes",
        "we restrict certain activity",
        "couldn't unfollow",
        "cannot unfollow",
        "action blocked",
        "تعذر",
        "لا يمكن",
        "حاول مرة اخرى لاحقا",
        "يرجى الانتظار",
    }

    def __init__(self, session_path: str) -> None:
        self.session_path = Path(session_path)
        self.profiles_root = Path("chrome_profiles")
        self.active_profile_key = "default"
        self.profile_dir = self.profiles_root / self.active_profile_key
        self.driver = None
        self.lock = threading.RLock()
        self.username: str | None = None

    def login(self, username: str, password: str, verification_code: str = "") -> None:
        raise InstagramServiceError("Password login is disabled. Use browser login only.")

    def login_with_browser(
        self,
        username: str = "",
        timeout_seconds: int = 300,
        force_new: bool = False,
    ) -> None:
        username = username.strip().lstrip("@")

        with self.lock:
            self._select_profile_for_login(username, force_new=force_new)
            self._ensure_driver()
            if force_new:
                self._clear_instagram_session()
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

    def _select_profile_for_login(self, username: str, force_new: bool = False) -> None:
        key = self._profile_key(username)
        restart_required = force_new or key != self.active_profile_key
        if restart_required and self.driver is not None:
            self.close_browser()
        self.active_profile_key = key
        self.profile_dir = self.profiles_root / key

    def _profile_key(self, username: str) -> str:
        value = username.strip().lstrip("@").lower()
        if not value:
            return "default"
        cleaned = re.sub(r"[^a-z0-9._-]+", "_", value).strip("._-")
        return cleaned or "default"

    def _clear_instagram_session(self) -> None:
        # Force fresh login when user asks to sign in with another account.
        try:
            self.driver.get("https://www.instagram.com/")
        except Exception:
            pass

        try:
            self.driver.delete_all_cookies()
        except Exception:
            pass

        try:
            self.driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
        except Exception:
            pass

        try:
            self.driver.execute_cdp_cmd(
                "Storage.clearDataForOrigin",
                {"origin": "https://www.instagram.com", "storageTypes": "all"},
            )
        except Exception:
            pass

        try:
            self.driver.execute_script(
                "window.localStorage.clear(); window.sessionStorage.clear();"
            )
        except Exception:
            pass

    def get_not_following_back(
        self,
        progress_callback: ListScanCallback | None = None,
    ) -> list[str]:
        with self.lock:
            self._ensure_logged_in()
            following = self._collect_user_list(
                self.username,
                "following",
                progress_callback=progress_callback,
            )
            followers = self._collect_user_list(
                self.username,
                "followers",
                progress_callback=progress_callback,
            )

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
            skipped: list[str] = []
            failed: list[str] = []
            total = len(usernames)

            for index, username in enumerate(usernames, start=1):
                cleaned = username.strip().lstrip("@")
                success = False
                error_message = ""
                did_unfollow = False

                if not cleaned:
                    failed.append(f"{username}: empty username")
                    if progress_callback:
                        progress_callback(index, total, username, False, "Empty username.")
                    continue

                try:
                    success, error_message, did_unfollow = self._unfollow_single(cleaned)
                    if success:
                        if did_unfollow:
                            removed.append(cleaned)
                        else:
                            skipped.append(cleaned)
                            if not error_message:
                                error_message = "Already not following."
                    else:
                        failed.append(f"{cleaned}: {error_message}")
                except Exception as exc:  # defensive to continue bulk flow
                    error_message = str(exc)
                    failed.append(f"{cleaned}: {error_message}")

                if progress_callback:
                    progress_callback(index, total, cleaned, success, error_message)

                if index < total:
                    time.sleep(max(delay_seconds, 0.2))

        return {"removed": removed, "skipped": skipped, "failed": failed}

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

    def _collect_user_list(
        self,
        username: str,
        relation: str,
        progress_callback: ListScanCallback | None = None,
    ) -> list[str]:
        relation = relation.strip().lower()
        if relation not in {"following", "followers"}:
            raise InstagramServiceError(f"Unsupported relation: {relation}")

        expected_total = self._open_relation_from_profile(username, relation)
        container = self._resolve_relation_container(relation)

        usernames: set[str] = set()
        stable_rounds = 0
        no_movement_rounds = 0
        max_rounds = 600

        scroll_box = self._find_scroll_box(container)

        for _ in range(max_rounds):
            previous_count = len(usernames)
            usernames.update(self._extract_usernames(container))
            current_count = len(usernames)

            if current_count > previous_count and progress_callback:
                progress_callback(relation, current_count)

            moved = self._scroll_relation_box(scroll_box)
            if not moved:
                scroll_box = self._find_scroll_box(container)
                moved = self._scroll_relation_box(scroll_box)

            if current_count == previous_count:
                stable_rounds += 1
            else:
                stable_rounds = 0

            if moved:
                no_movement_rounds = 0
            else:
                no_movement_rounds += 1

            if stable_rounds >= 14 and no_movement_rounds >= 6:
                break

            time.sleep(0.85 if stable_rounds < 4 else 1.1)

        self._close_relation_view()

        if expected_total is not None and len(usernames) < expected_total:
            recovered = self._recover_relation_with_fullpage(
                username=username,
                relation=relation,
                existing_usernames=usernames,
                expected_total=expected_total,
                progress_callback=progress_callback,
            )
            usernames.update(recovered)

        if progress_callback:
            progress_callback(relation, len(usernames))

        return sorted(usernames, key=str.lower)

    def _open_relation_from_profile(self, username: str, relation: str) -> int | None:
        self.driver.get(f"https://www.instagram.com/{username}/")
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//header"))
            )
        except TimeoutException as exc:
            raise InstagramServiceError(f"Could not open profile @{username}.") from exc

        self._close_relation_view()
        relation_link = self._find_relation_link(username, relation)
        if relation_link is None:
            raise InstagramServiceError(
                f"Could not find {relation} list button on profile @{username}."
            )

        expected_total = self._extract_relation_count_from_link(relation_link, relation)

        try:
            self.driver.execute_script("arguments[0].click();", relation_link)
        except Exception:
            try:
                relation_link.click()
            except Exception as exc:
                raise InstagramServiceError(
                    f"Could not open {relation} list from profile @{username}."
                ) from exc
        time.sleep(0.8)
        return expected_total

    def _resolve_relation_container(self, relation: str):
        try:
            dialog = WebDriverWait(self.driver, 12).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
            )
            return dialog
        except TimeoutException:
            raise InstagramServiceError(
                f"Could not open {relation} popup list from profile button."
            )

    def _find_relation_link(self, username: str, relation: str):
        username_norm = username.strip().lstrip("@").lower()
        links = self.driver.find_elements(By.XPATH, "//header//a[contains(@href,'/followers/') or contains(@href,'/following/')]")
        for link in links:
            href = link.get_attribute("href") or ""
            parsed = urlparse(href)
            parts = [part for part in (parsed.path or "").split("/") if part]
            if len(parts) < 2:
                continue
            if parts[0].lower() == username_norm and parts[1].lower() == relation:
                return link
        return None

    def _close_relation_view(self) -> None:
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.3)
        except Exception:
            pass

    def _recover_relation_with_fullpage(
        self,
        username: str,
        relation: str,
        existing_usernames: set[str],
        expected_total: int,
        progress_callback: ListScanCallback | None = None,
    ) -> set[str]:
        usernames = set(existing_usernames)
        try:
            self.driver.get(f"https://www.instagram.com/{username}/{relation}/")
            page_container = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//main"))
            )
        except Exception:
            return usernames

        stable_rounds = 0
        for _ in range(360):
            previous_count = len(usernames)
            usernames.update(self._extract_usernames(page_container))
            current_count = len(usernames)

            if current_count > previous_count and progress_callback:
                progress_callback(relation, current_count)

            if current_count >= expected_total:
                break

            if current_count == previous_count:
                stable_rounds += 1
            else:
                stable_rounds = 0

            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
            except Exception:
                pass

            if stable_rounds >= 24:
                break

            time.sleep(0.9 if stable_rounds < 6 else 1.2)

        return usernames

    def _extract_relation_count_from_link(self, relation_link, relation: str) -> int | None:
        texts: list[str] = []
        try:
            raw_text = self.driver.execute_script(
                "return (arguments[0].innerText || arguments[0].textContent || '').trim();",
                relation_link,
            )
            if raw_text:
                texts.append(str(raw_text))
        except Exception:
            pass

        for attr in ("title", "aria-label"):
            try:
                value = relation_link.get_attribute(attr) or ""
            except Exception:
                value = ""
            if value:
                texts.append(value)

        try:
            parts = relation_link.find_elements(By.XPATH, ".//*")
            for part in parts[:8]:
                part_text = (part.get_attribute("title") or part.text or "").strip()
                if part_text:
                    texts.append(part_text)
        except Exception:
            pass

        for text in texts:
            parsed = self._parse_relation_count(text, relation)
            if parsed is not None:
                return parsed

        return None

    def _parse_relation_count(self, text: str, relation: str) -> int | None:
        if not text:
            return None

        normalized = self._normalize_text(self._normalize_digits(text))
        if not normalized:
            return None

        relation_labels = [relation]
        if relation == "following":
            relation_labels.extend(["following", "يتابع", "المتابعة"])
        else:
            relation_labels.extend(["followers", "متابع", "المتابعين"])

        number_pattern = r"([0-9][0-9,\.]*\s*[kmb]?)"
        for label in relation_labels:
            label_norm = self._normalize_text(label)
            if not label_norm:
                continue
            match = re.search(number_pattern + r"\s*" + re.escape(label_norm), normalized)
            if not match:
                match = re.search(re.escape(label_norm) + r"\s*" + number_pattern, normalized)
            if match:
                value = self._parse_compact_number(match.group(1))
                if value is not None:
                    return value

        for token in re.findall(number_pattern, normalized):
            value = self._parse_compact_number(token)
            if value is not None:
                return value
        return None

    def _parse_compact_number(self, raw_value: str) -> int | None:
        token = (raw_value or "").strip().lower().replace(" ", "")
        if not token:
            return None

        suffix = ""
        if token[-1] in {"k", "m", "b"}:
            suffix = token[-1]
            token = token[:-1]

        token = token.replace(",", "")
        if token.count(".") > 1:
            token = token.replace(".", "")
        elif not suffix and token.count(".") == 1 and len(token.split(".")[-1]) == 3:
            token = token.replace(".", "")

        try:
            value = float(token)
        except ValueError:
            return None

        multipliers = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
        return int(value * multipliers.get(suffix, 1))

    def _normalize_digits(self, value: str) -> str:
        mapping = str.maketrans(
            "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٬٫",
            "01234567890123456789,.",
        )
        return value.translate(mapping)

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
        js_candidate = None
        try:
            js_candidate = self.driver.execute_script(
                (
                    "const root = arguments[0];"
                    "if (!root) return null;"
                    "const nodes = [root, ...root.querySelectorAll('div,section,ul,main')];"
                    "let best = null;"
                    "let bestDelta = 0;"
                    "for (const node of nodes) {"
                    "  const sh = Number(node.scrollHeight || 0);"
                    "  const ch = Number(node.clientHeight || 0);"
                    "  if (sh <= ch + 16) continue;"
                    "  const style = window.getComputedStyle(node);"
                    "  const oy = String(style.overflowY || style.overflow || '').toLowerCase();"
                    "  if (oy.includes('hidden') && !oy.includes('auto') && !oy.includes('scroll')) continue;"
                    "  const delta = sh - ch;"
                    "  if (delta > bestDelta) {"
                    "    best = node;"
                    "    bestDelta = delta;"
                    "  }"
                    "}"
                    "return best;"
                ),
                dialog,
            )
        except Exception:
            js_candidate = None

        if js_candidate is not None:
            return js_candidate

        xpaths = [
            ".//div[contains(@style,'overflow: hidden auto')]",
            ".//div[contains(@style,'overflow-y: auto')]",
            ".//div[contains(@style,'overflow: auto')]",
            ".//*[@style and contains(@style,'overflow')]",
        ]
        candidates = [dialog]
        for xpath in xpaths:
            try:
                elements = dialog.find_elements(By.XPATH, xpath)
            except Exception:
                continue
            if elements:
                candidates.extend(elements[:20])

        for candidate in candidates:
            metrics = self._get_scroll_metrics(candidate)
            if not metrics:
                continue
            _, scroll_height, client_height = metrics
            if scroll_height > (client_height + 24):
                return candidate

        return dialog

    def _get_scroll_metrics(self, element) -> tuple[float, float, float] | None:
        try:
            values = self.driver.execute_script(
                (
                    "const el = arguments[0];"
                    "if (!el) return null;"
                    "return [Number(el.scrollTop || 0), Number(el.scrollHeight || 0), Number(el.clientHeight || 0)];"
                ),
                element,
            )
        except Exception:
            return None

        if not values or len(values) != 3:
            return None
        return float(values[0]), float(values[1]), float(values[2])

    def _scroll_relation_box(self, element) -> bool:
        before = self._get_scroll_metrics(element)
        moved = False

        if element is not None:
            try:
                self.driver.execute_script(
                    (
                        "const el = arguments[0];"
                        "if (el && typeof el.focus === 'function') { el.focus(); }"
                    ),
                    element,
                )
            except Exception:
                pass

            try:
                self.driver.execute_script(
                    (
                        "const el = arguments[0];"
                        "if (!el) return;"
                        "const step = Math.max((el.clientHeight || 0) * 0.92, 360);"
                        "el.scrollTop = Math.min((el.scrollTop || 0) + step, el.scrollHeight || 0);"
                    ),
                    element,
                )
            except Exception:
                pass

            moved = self._did_scroll_change(before, self._get_scroll_metrics(element))
            if moved:
                return True

            try:
                self.driver.execute_script(
                    (
                        "const el = arguments[0];"
                        "if (!el) return;"
                        "const ev = new WheelEvent('wheel', {deltaY: 700, bubbles: true, cancelable: true});"
                        "el.dispatchEvent(ev);"
                    ),
                    element,
                )
            except Exception:
                pass
            moved = self._did_scroll_change(before, self._get_scroll_metrics(element))
            if moved:
                return True

            try:
                ActionChains(self.driver).move_to_element(element).click(element).send_keys(Keys.PAGE_DOWN).perform()
            except Exception:
                pass
            moved = self._did_scroll_change(before, self._get_scroll_metrics(element))
            if moved:
                return True

            try:
                element.send_keys(Keys.PAGE_DOWN)
            except Exception:
                pass
            moved = self._did_scroll_change(before, self._get_scroll_metrics(element))
            if moved:
                return True

        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.PAGE_DOWN)
            body.send_keys(Keys.END)
        except Exception:
            pass

        return self._did_scroll_change(before, self._get_scroll_metrics(element))

    def _did_scroll_change(
        self,
        before: tuple[float, float, float] | None,
        after: tuple[float, float, float] | None,
    ) -> bool:
        if before is None or after is None:
            return False
        before_top, before_height, _ = before
        after_top, after_height, _ = after
        if after_top > (before_top + 1):
            return True
        if after_height > (before_height + 4):
            return True
        return False

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

    def _unfollow_single(self, username: str) -> tuple[bool, str, bool]:
        self.driver.get(f"https://www.instagram.com/{username}/")
        try:
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.XPATH, "//header"))
            )
        except TimeoutException:
            return False, f"Profile did not load for @{username}.", False

        self._close_relation_view()
        button = self._wait_for_follow_button(timeout_seconds=5)
        if button is None:
            return False, "Could not detect follow state button.", False

        state, label = self._get_follow_state()

        if state == "not_following":
            return True, "Already not following.", False

        if state != "following":
            return False, f"Unknown follow button text: '{label or 'empty'}'", False

        try:
            try:
                self.driver.execute_script("arguments[0].click();", button)
            except Exception:
                button.click()
            time.sleep(0.4)
        except Exception as exc:
            return False, f"Failed to click Following button: {exc}", False

        # Some UIs show a confirmation dialog, others apply immediately.
        self._click_unfollow_confirmation()

        verified, verify_message = self._wait_for_unfollow_state(timeout_seconds=5)
        if verified:
            return True, "", True
        return False, verify_message, False

    def _get_follow_state(self) -> tuple[str, str]:
        button = self._find_follow_button()
        if button is None:
            return "unknown", ""

        label = self._normalize_text(button.text or button.get_attribute("aria-label") or "")
        if self._is_following_label(label):
            return "following", label
        if self._is_follow_label(label):
            return "not_following", label
        return "unknown", label

    def _wait_for_follow_button(self, timeout_seconds: int = 5):
        deadline = time.time() + max(timeout_seconds, 1)
        while time.time() < deadline:
            button = self._find_follow_button()
            if button is not None:
                return button
            time.sleep(0.25)
        return None

    def _wait_for_unfollow_state(self, timeout_seconds: int = 8) -> tuple[bool, str]:
        deadline = time.time() + max(timeout_seconds, 2)
        while time.time() < deadline:
            blocked_message = self._detect_action_blocked_message()
            if blocked_message:
                return False, blocked_message

            state, _ = self._get_follow_state()
            if state == "not_following":
                return True, ""

            # In some layouts, the confirm button appears late.
            self._click_unfollow_confirmation()
            time.sleep(0.35)

        return False, "Unfollow was not confirmed. Instagram may have blocked the action."

    def _detect_action_blocked_message(self) -> str | None:
        keywords = self._normalized_keywords(self.ACTION_BLOCKED_KEYWORDS)
        xpaths = [
            "//div[@role='alert']",
            "//div[@role='dialog']",
            "//section",
            "//body",
        ]
        for xpath in xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
            except Exception:
                continue
            for element in elements[:3]:
                text = self._normalize_text(element.text or "")
                if not text:
                    continue
                if any(keyword in text for keyword in keywords):
                    return "Instagram blocked this unfollow action (try again later)."
        return None

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
        keywords = self._normalized_keywords(self.UNFOLLOW_KEYWORDS)
        xpaths = [
            "//div[@role='dialog']//*[self::button or @role='button' or @role='menuitem' or @role='option' or @tabindex='0']",
            "//div[@role='dialog']//button | //button",
            "//*[@role='menuitem' or @role='option' or @role='button']",
        ]

        for xpath in xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
            except Exception:
                continue

            for element in elements:
                try:
                    if not element.is_displayed():
                        continue
                except Exception:
                    continue

                text = self._normalize_text(
                    (
                        element.text
                        or element.get_attribute("aria-label")
                        or element.get_attribute("title")
                        or ""
                    )
                )
                if not text:
                    continue

                if any(self._keyword_in_text(text, keyword) for keyword in keywords):
                    try:
                        self.driver.execute_script("arguments[0].click();", element)
                    except Exception:
                        try:
                            element.click()
                        except Exception:
                            continue
                    time.sleep(0.35)
                    return True

        # JS fallback for Instagram menu layouts where "Unfollow" is nested text.
        try:
            clicked = self.driver.execute_script(
                (
                    "const keywords = arguments[0] || [];"
                    "const roots = document.querySelectorAll(\"div[role='dialog'], div[role='menu'], body\");"
                    "for (const root of roots) {"
                    "  const nodes = root.querySelectorAll(\"button, [role='button'], [role='menuitem'], [role='option'], div[tabindex]\");"
                    "  for (const node of nodes) {"
                    "    const style = window.getComputedStyle(node);"
                    "    if (style.display === 'none' || style.visibility === 'hidden') continue;"
                    "    const text = String(node.innerText || node.textContent || node.getAttribute('aria-label') || node.getAttribute('title') || '')"
                    "      .toLowerCase().replace(/\\s+/g, ' ').trim();"
                    "    if (!text) continue;"
                    "    for (const keyword of keywords) {"
                    "      if (text.includes(String(keyword || '').toLowerCase())) {"
                    "        node.click();"
                    "        return true;"
                    "      }"
                    "    }"
                    "  }"
                    "}"
                    "return false;"
                ),
                keywords,
            )
            if clicked:
                time.sleep(0.35)
                return True
        except Exception:
            pass

        return False

    def _is_follow_label(self, text: str) -> bool:
        value = self._normalize_text(text)
        if not value:
            return False
        follow_match = any(
            self._keyword_in_text(value, keyword)
            for keyword in self._normalized_keywords(self.FOLLOW_KEYWORDS)
        )
        following_match = any(
            self._keyword_in_text(value, keyword)
            for keyword in self._normalized_keywords(self.FOLLOWING_KEYWORDS)
        )
        return follow_match and not following_match

    def _is_following_label(self, text: str) -> bool:
        value = self._normalize_text(text)
        if not value:
            return False
        return any(
            self._keyword_in_text(value, keyword)
            for keyword in self._normalized_keywords(self.FOLLOWING_KEYWORDS)
        )

    def _normalized_keywords(self, keywords: set[str]) -> list[str]:
        return [self._normalize_text(keyword) for keyword in keywords]

    def _keyword_in_text(self, text: str, keyword: str) -> bool:
        if not text or not keyword:
            return False
        if keyword.isascii():
            pattern = rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])"
            return re.search(pattern, text) is not None
        return keyword in text

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
