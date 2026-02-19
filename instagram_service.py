from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from instagrapi import Client
from instagrapi.exceptions import BadPassword, ChallengeRequired, LoginRequired, TwoFactorRequired


class InstagramServiceError(Exception):
    """Raised when an Instagram operation fails."""


ProgressCallback = Callable[[int, int, str, bool, str], None]


class InstagramService:
    def __init__(self, session_path: str) -> None:
        self.client = Client()
        self.session_path = Path(session_path)
        self.is_logged_in = False

    def login(self, username: str, password: str) -> None:
        username = username.strip().lstrip("@")
        password = password.strip()
        if not username or not password:
            raise InstagramServiceError("Username and password are required.")

        if self.session_path.exists():
            self.client.load_settings(str(self.session_path))

        try:
            logged_in = self.client.login(username, password)
        except BadPassword as exc:
            raise InstagramServiceError("Wrong password.") from exc
        except TwoFactorRequired as exc:
            raise InstagramServiceError(
                "Two-factor authentication is enabled. This simple build does not support 2FA yet."
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

    def get_not_following_back(self) -> list[str]:
        self._ensure_login()
        try:
            my_user_id = self.client.user_id
            if my_user_id is None:
                my_user_id = self.client.user_id_from_username(self.client.username)
            following = self.client.user_following(my_user_id)
            followers = self.client.user_followers(my_user_id)
        except Exception as exc:
            raise InstagramServiceError(f"Failed to load data: {exc}") from exc

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
                error_message = str(exc)
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
            self.client.load_settings(str(self.session_path))
            self.client.get_timeline_feed()
            self.is_logged_in = True
        except LoginRequired as exc:
            raise InstagramServiceError("Session expired. Please login again.") from exc
        except Exception as exc:
            raise InstagramServiceError(f"Session is invalid. Please login again. ({exc})") from exc
