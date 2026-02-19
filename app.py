import threading
from datetime import datetime
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from instagram_service import InstagramService, InstagramServiceError


APP_TITLE = "Instagram Cleaner"
SAVED_ACCOUNTS_FILE = Path("accounts.json")


class InstagramCleanerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("920x620")
        self.root.minsize(820, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.service = InstagramService("session.json")
        self.non_followers: list[str] = []
        self.last_scan_counts = {"following": 0, "followers": 0}

        self.saved_accounts = self._load_saved_accounts()
        self.username_var = tk.StringVar()
        self.saved_account_var = tk.StringVar(value=self.saved_accounts[0] if self.saved_accounts else "")
        self.delay_var = tk.StringVar(value="0.8")
        self.status_var = tk.StringVar(value="Status: Idle")
        self.detector_var = tk.StringVar(value="Error Detector: No issues detected.")

        self._apply_theme()
        self._set_window_icon()
        self._build_ui()

    def _apply_theme(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(bg="#f3f6fb")
        style.configure("TFrame", background="#f3f6fb")
        style.configure("TLabelframe", background="#f3f6fb", bordercolor="#d8e0ee")
        style.configure("TLabelframe.Label", background="#f3f6fb", foreground="#1f2d3d")
        style.configure("TLabel", background="#f3f6fb", foreground="#1f2d3d")
        style.configure(
            "TButton",
            padding=(10, 6),
            background="#e9eef8",
            foreground="#1b2a41",
            bordercolor="#cfd8ea",
        )
        style.map(
            "TButton",
            background=[("active", "#dfe8f7"), ("pressed", "#d2dff4")],
        )
        style.configure("Accent.TButton", background="#4f7dff", foreground="white", bordercolor="#4f7dff")
        style.map(
            "Accent.TButton",
            background=[("active", "#3f6ef3"), ("pressed", "#335fe0")],
            foreground=[("disabled", "#eaf0ff")],
        )
        style.configure("TEntry", fieldbackground="white", bordercolor="#cad5eb")

    def _set_window_icon(self) -> None:
        icon_path = self._resource_path("assets/app_icon.ico")
        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except Exception:
                pass

    def _resource_path(self, relative_path: str) -> Path:
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / relative_path
        return Path(__file__).resolve().parent / relative_path

    def _load_saved_accounts(self) -> list[str]:
        if not SAVED_ACCOUNTS_FILE.exists():
            return []
        try:
            data = json.loads(SAVED_ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for entry in data:
            if not isinstance(entry, str):
                continue
            username = entry.strip().lstrip("@")
            if not username:
                continue
            lowered = username.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(username)
        return cleaned

    def _save_saved_accounts(self) -> None:
        try:
            SAVED_ACCOUNTS_FILE.write_text(
                json.dumps(self.saved_accounts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _refresh_saved_accounts_ui(self) -> None:
        values = list(self.saved_accounts)
        self.saved_accounts_combo.configure(values=values)
        current = self.saved_account_var.get().strip()
        if values:
            if not current or current not in values:
                self.saved_account_var.set(values[0])
        else:
            self.saved_account_var.set("")

    def _remember_account(self, username: str) -> None:
        account = username.strip().lstrip("@")
        if not account:
            return
        existing = [item for item in self.saved_accounts if item.lower() != account.lower()]
        self.saved_accounts = [account] + existing
        self.saved_accounts = self.saved_accounts[:20]
        self._save_saved_accounts()
        self._refresh_saved_accounts_ui()

    def use_selected_account(self) -> None:
        selected = self.saved_account_var.get().strip()
        if selected:
            self.username_var.set(selected)

    def remove_selected_account(self) -> None:
        selected = self.saved_account_var.get().strip()
        if not selected:
            return
        self.saved_accounts = [item for item in self.saved_accounts if item.lower() != selected.lower()]
        self._save_saved_accounts()
        self._refresh_saved_accounts_ui()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        self.root.rowconfigure(3, weight=1)
        self.root.rowconfigure(4, weight=0)

        login_frame = ttk.LabelFrame(self.root, text="Instagram Login")
        login_frame.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
        login_frame.columnconfigure(1, weight=1)

        ttk.Label(login_frame, text="Username (for account profile)").grid(row=0, column=0, padx=6, pady=8, sticky="w")
        ttk.Entry(login_frame, textvariable=self.username_var).grid(
            row=0, column=1, padx=6, pady=8, sticky="ew"
        )

        self.login_button = ttk.Button(login_frame, text="Login", style="Accent.TButton", command=self.login)
        self.login_button.grid(row=0, column=2, padx=6, pady=8)

        self.login_other_button = ttk.Button(
            login_frame,
            text="Login Another",
            command=self.login_another_account,
        )
        self.login_other_button.grid(row=0, column=3, padx=6, pady=8)

        ttk.Label(
            login_frame,
            text="Type/select account, then login. Each account gets its own Chrome profile.",
            foreground="#53627a",
        ).grid(row=1, column=1, columnspan=3, padx=8, pady=(2, 8), sticky="w")

        ttk.Label(login_frame, text="Saved accounts").grid(row=2, column=0, padx=6, pady=8, sticky="w")
        self.saved_accounts_combo = ttk.Combobox(
            login_frame,
            textvariable=self.saved_account_var,
            state="readonly",
            values=self.saved_accounts,
        )
        self.saved_accounts_combo.grid(row=2, column=1, padx=6, pady=8, sticky="ew")
        ttk.Button(login_frame, text="Use", command=self.use_selected_account).grid(
            row=2, column=2, padx=6, pady=8
        )
        ttk.Button(login_frame, text="Remove", command=self.remove_selected_account).grid(
            row=2, column=3, padx=6, pady=8
        )

        action_frame = ttk.LabelFrame(self.root, text="Actions")
        action_frame.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        action_frame.columnconfigure(5, weight=1)

        self.fetch_button = ttk.Button(
            action_frame,
            text="Find People Not Following Back",
            command=self.fetch_non_followers,
            state=tk.DISABLED,
        )
        self.fetch_button.grid(row=0, column=0, padx=6, pady=8)

        self.unfollow_selected_button = ttk.Button(
            action_frame,
            text="Unfollow Selected",
            command=self.unfollow_selected,
            state=tk.DISABLED,
        )
        self.unfollow_selected_button.grid(row=0, column=1, padx=6, pady=8)

        self.unfollow_all_button = ttk.Button(
            action_frame,
            text="Unfollow All Listed",
            command=self.unfollow_all,
            state=tk.DISABLED,
        )
        self.unfollow_all_button.grid(row=0, column=2, padx=6, pady=8)

        ttk.Label(action_frame, text="Delay (sec)").grid(row=0, column=3, padx=(18, 4), pady=8)
        ttk.Entry(action_frame, textvariable=self.delay_var, width=6).grid(row=0, column=4, padx=4, pady=8)
        ttk.Label(action_frame, text="Use 0.3-1.5 seconds for faster flow (higher risk).").grid(
            row=0, column=5, padx=8, pady=8, sticky="w"
        )

        list_frame = ttk.LabelFrame(self.root, text="Accounts Not Following You Back")
        list_frame.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.user_list = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            bg="white",
            fg="#1f2d3d",
            selectbackground="#4f7dff",
            selectforeground="white",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#d5deef",
            highlightcolor="#4f7dff",
            activestyle="none",
        )
        self.user_list.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.user_list.yview)
        list_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.user_list.configure(yscrollcommand=list_scroll.set)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            state=tk.DISABLED,
            height=9,
            bg="white",
            fg="#1f2d3d",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#d5deef",
            highlightcolor="#4f7dff",
            insertbackground="#1f2d3d",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        detector_frame = ttk.LabelFrame(self.root, text="Error Detector")
        detector_frame.grid(row=4, column=0, padx=12, pady=(0, 12), sticky="ew")
        detector_frame.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(detector_frame, textvariable=self.status_var, foreground="#1f5faa")
        self.status_label.grid(row=0, column=0, padx=8, pady=(6, 2), sticky="w")
        ttk.Label(detector_frame, textvariable=self.detector_var, wraplength=860).grid(
            row=1, column=0, padx=8, pady=(0, 8), sticky="w"
        )

        self._refresh_saved_accounts_ui()
        self.log("Application started. Click Login to open Chrome and sign in.")
        self._set_detector("INFO", "Ready to login.")

    def log(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {text}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_action_buttons(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.fetch_button.configure(state=state)
        self.unfollow_selected_button.configure(state=state)
        self.unfollow_all_button.configure(state=state)

    def _set_login_buttons(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.login_button.configure(state=state)
        self.login_other_button.configure(state=state)

    def _run_async(self, work) -> None:
        thread = threading.Thread(target=work, daemon=True)
        thread.start()

    def _set_detector(self, level: str, message: str) -> None:
        color_map = {
            "SUCCESS": "#1f7a3f",
            "WARNING": "#a85a00",
            "ERROR": "#b42318",
            "INFO": "#1f5faa",
        }
        self.status_var.set(f"Status: {level}")
        self.detector_var.set(f"Error Detector: {message}")
        level_color = color_map.get(level, "#1f5faa")
        self.status_label.configure(foreground=level_color)

    def login(self) -> None:
        self.login_with_browser(force_new=False)

    def login_another_account(self) -> None:
        self.login_with_browser(force_new=True)

    def _on_login_success(self, auto_scan: bool = False) -> None:
        self._set_login_buttons(True)
        self._set_action_buttons(True)
        active_username = (self.service.username or "").strip().lstrip("@")
        if active_username:
            self.username_var.set(active_username)
            self._remember_account(active_username)
            self.log(f"Login successful as @{active_username}.")
        else:
            self.log("Login successful.")
        if auto_scan:
            self._set_detector("INFO", "Login successful. Starting account scan automatically...")
            self.fetch_non_followers()
        else:
            self._set_detector("SUCCESS", "Login successful. Session is active.")

    def _on_login_failed(self, error_text: str) -> None:
        self._set_login_buttons(True)
        self.log(f"Login failed: {error_text}")
        level = "WARNING" if ("challenge" in error_text.lower() or "captcha" in error_text.lower()) else "ERROR"
        self._set_detector(level, error_text)
        messagebox.showerror(APP_TITLE, error_text)

    def login_with_browser(self, force_new: bool = False) -> None:
        username = self.username_var.get().strip()
        if not username:
            username = self.saved_account_var.get().strip()

        self._set_login_buttons(False)
        self._set_detector(
            "INFO",
            "Launching Chrome. Complete Instagram login/challenge there, then wait for auto-detect.",
        )
        if force_new:
            self.log("Launching Chrome login flow for another account...")
        else:
            self.log("Launching visible Chrome login flow...")

        def work() -> None:
            try:
                self.service.login_with_browser(
                    username=username,
                    timeout_seconds=300,
                    force_new=force_new,
                )
            except InstagramServiceError as exc:
                self.root.after(0, lambda: self._on_login_failed(str(exc)))
                return
            self.root.after(0, lambda: self._on_login_success(auto_scan=True))

        self._run_async(work)

    def fetch_non_followers(self) -> None:
        self._set_action_buttons(False)
        self.log("Loading accounts. This may take some time for large accounts...")
        self.last_scan_counts = {"following": 0, "followers": 0}
        scan_progress = {"following": -1, "followers": -1}
        scan_completed: set[str] = set()

        def scan_update(relation: str, count: int) -> None:
            if relation not in scan_progress:
                return
            relation_key = relation
            label = "following" if relation_key == "following" else "followers"
            previous = scan_progress.get(relation_key, -1)

            if count < 0:
                return

            if previous < 0:
                scan_progress[relation_key] = count
                self.last_scan_counts[relation_key] = count
                self.root.after(
                    0,
                    lambda label=label, count=count: self.log(
                        f"Scanning {label}: {count} account(s) loaded..."
                    ),
                )
                return

            if count > previous:
                scan_progress[relation_key] = count
                self.last_scan_counts[relation_key] = count
                if count <= 50 or (count - previous) >= 5:
                    self.root.after(
                        0,
                        lambda label=label, count=count: self.log(
                            f"Scanning {label}: {count} account(s) loaded..."
                        ),
                    )
                return

            if count == previous and relation_key not in scan_completed:
                scan_completed.add(relation_key)
                self.last_scan_counts[relation_key] = count
                self.root.after(
                    0,
                    lambda label=label, count=count: self.log(
                        f"Finished scanning {label}: {count} account(s)."
                    ),
                )

        def work() -> None:
            try:
                users = self.service.get_not_following_back(progress_callback=scan_update)
            except InstagramServiceError as exc:
                self.root.after(0, lambda: self._on_fetch_failed(str(exc)))
                return
            self.root.after(0, lambda: self._on_fetch_success(users))

        self._run_async(work)

    def _on_fetch_success(self, users: list[str]) -> None:
        self.non_followers = users
        self.user_list.delete(0, tk.END)
        for username in users:
            self.user_list.insert(tk.END, username)
        self._set_action_buttons(True)
        self.log(
            "Scan totals: "
            f"following={self.last_scan_counts.get('following', 0)}, "
            f"followers={self.last_scan_counts.get('followers', 0)}."
        )
        self.log(f"Found {len(users)} account(s) not following you back.")
        self._set_detector("SUCCESS", f"Data loaded successfully. Found {len(users)} account(s).")

    def _on_fetch_failed(self, error_text: str) -> None:
        self._set_action_buttons(True)
        self.log(f"Failed to load accounts: {error_text}")
        self._set_detector("ERROR", error_text)
        messagebox.showerror(APP_TITLE, error_text)

    def unfollow_selected(self) -> None:
        indexes = list(self.user_list.curselection())
        if not indexes:
            messagebox.showwarning(APP_TITLE, "Select at least one account.")
            return
        selected = [self.user_list.get(i) for i in indexes]
        self._start_unfollow(selected)

    def unfollow_all(self) -> None:
        if not self.non_followers:
            messagebox.showwarning(APP_TITLE, "No accounts to unfollow.")
            return
        self._start_unfollow(list(self.non_followers))

    def _start_unfollow(self, usernames: list[str]) -> None:
        delay = self._parse_delay()
        if delay is None:
            return

        preview = ", ".join(usernames[:6])
        suffix = "..." if len(usernames) > 6 else ""
        question = f"Unfollow {len(usernames)} account(s)?\n\n{preview}{suffix}"
        if not messagebox.askyesno(APP_TITLE, question):
            return

        self._set_action_buttons(False)
        self.log(f"Starting unfollow for {len(usernames)} account(s).")

        def progress(done: int, total: int, username: str, success: bool, error: str) -> None:
            def update_log() -> None:
                if success:
                    if error:
                        self.log(f"{done}/{total} skipped @{username}: {error}")
                    else:
                        self.log(f"{done}/{total} unfollowed @{username}")
                else:
                    self.log(f"{done}/{total} failed @{username}: {error}")

            self.root.after(0, update_log)

        def work() -> None:
            try:
                result = self.service.unfollow_users(usernames, delay_seconds=delay, progress_callback=progress)
            except InstagramServiceError as exc:
                self.root.after(0, lambda: self._on_unfollow_failed(str(exc)))
                return
            self.root.after(0, lambda: self._on_unfollow_finished(result))

        self._run_async(work)

    def _on_unfollow_finished(self, result: dict[str, list[str]]) -> None:
        removed = set(result.get("removed", []))
        skipped = set(result.get("skipped", []))
        failed = result.get("failed", [])
        processed = removed | skipped
        if processed:
            self.non_followers = [username for username in self.non_followers if username not in processed]
            self.user_list.delete(0, tk.END)
            for username in self.non_followers:
                self.user_list.insert(tk.END, username)

        self._set_action_buttons(True)
        self.log(
            "Unfollow done. "
            f"Removed: {len(result.get('removed', []))}, "
            f"Skipped: {len(result.get('skipped', []))}, "
            f"Failed: {len(result.get('failed', []))}."
        )
        if failed:
            self._set_detector("WARNING", f"Completed with failures: {len(failed)}. Check log.")
            messagebox.showwarning(APP_TITLE, "Finished with some failures. Check log for details.")
        else:
            self._set_detector(
                "SUCCESS",
                f"Unfollow completed. Removed: {len(result.get('removed', []))}, Skipped: {len(result.get('skipped', []))}.",
            )
            messagebox.showinfo(APP_TITLE, "Finished successfully.")

    def _on_unfollow_failed(self, error_text: str) -> None:
        self._set_action_buttons(True)
        self.log(f"Unfollow failed: {error_text}")
        self._set_detector("ERROR", error_text)
        messagebox.showerror(APP_TITLE, error_text)

    def _parse_delay(self) -> float | None:
        try:
            delay = float(self.delay_var.get().strip())
        except ValueError:
            messagebox.showerror(APP_TITLE, "Delay must be a number.")
            return None
        if delay < 0.2:
            messagebox.showerror(APP_TITLE, "Delay must be at least 0.2 seconds.")
            return None
        return delay

    def on_close(self) -> None:
        try:
            self.service.close_browser()
        except Exception:
            pass
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = InstagramCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
