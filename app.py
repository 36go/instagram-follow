import threading
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from instagram_service import InstagramService, InstagramServiceError


APP_TITLE = "Instagram Cleaner"


class InstagramCleanerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("920x620")
        self.root.minsize(820, 560)

        self.service = InstagramService("session.json")
        self.non_followers: list[str] = []

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.delay_var = tk.StringVar(value="2")

        self._build_ui()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        self.root.rowconfigure(3, weight=1)

        login_frame = ttk.LabelFrame(self.root, text="Instagram Login")
        login_frame.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
        login_frame.columnconfigure(1, weight=1)
        login_frame.columnconfigure(3, weight=1)

        ttk.Label(login_frame, text="Username").grid(row=0, column=0, padx=6, pady=8, sticky="w")
        ttk.Entry(login_frame, textvariable=self.username_var).grid(
            row=0, column=1, padx=6, pady=8, sticky="ew"
        )

        ttk.Label(login_frame, text="Password").grid(row=0, column=2, padx=6, pady=8, sticky="w")
        ttk.Entry(login_frame, textvariable=self.password_var, show="*").grid(
            row=0, column=3, padx=6, pady=8, sticky="ew"
        )

        self.login_button = ttk.Button(login_frame, text="Login", command=self.login)
        self.login_button.grid(row=0, column=4, padx=6, pady=8)

        action_frame = ttk.LabelFrame(self.root, text="Actions")
        action_frame.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        action_frame.columnconfigure(5, weight=1)

        self.fetch_button = ttk.Button(
            action_frame, text="Find People Not Following Back", command=self.fetch_non_followers, state=tk.DISABLED
        )
        self.fetch_button.grid(row=0, column=0, padx=6, pady=8)

        self.unfollow_selected_button = ttk.Button(
            action_frame, text="Unfollow Selected", command=self.unfollow_selected, state=tk.DISABLED
        )
        self.unfollow_selected_button.grid(row=0, column=1, padx=6, pady=8)

        self.unfollow_all_button = ttk.Button(
            action_frame, text="Unfollow All Listed", command=self.unfollow_all, state=tk.DISABLED
        )
        self.unfollow_all_button.grid(row=0, column=2, padx=6, pady=8)

        ttk.Label(action_frame, text="Delay (sec)").grid(row=0, column=3, padx=(18, 4), pady=8)
        ttk.Entry(action_frame, textvariable=self.delay_var, width=6).grid(row=0, column=4, padx=4, pady=8)
        ttk.Label(action_frame, text="Use 2-4 seconds to reduce rate-limit risk.").grid(
            row=0, column=5, padx=8, pady=8, sticky="w"
        )

        list_frame = ttk.LabelFrame(self.root, text="Accounts Not Following You Back")
        list_frame.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.user_list = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        self.user_list.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.user_list.yview)
        list_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.user_list.configure(yscrollcommand=list_scroll.set)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, state=tk.DISABLED, height=9)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log("Application started. Enter your credentials and click Login.")

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

    def _run_async(self, work) -> None:
        thread = threading.Thread(target=work, daemon=True)
        thread.start()

    def login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        if not username or not password:
            messagebox.showerror(APP_TITLE, "Please enter username and password.")
            return

        self.login_button.configure(state=tk.DISABLED)
        self.log("Logging in...")

        def work() -> None:
            try:
                self.service.login(username, password)
            except InstagramServiceError as exc:
                self.root.after(0, lambda: self._on_login_failed(str(exc)))
                return
            self.root.after(0, self._on_login_success)

        self._run_async(work)

    def _on_login_success(self) -> None:
        self.login_button.configure(state=tk.NORMAL)
        self._set_action_buttons(True)
        self.log("Login successful.")
        messagebox.showinfo(APP_TITLE, "Login successful.")

    def _on_login_failed(self, error_text: str) -> None:
        self.login_button.configure(state=tk.NORMAL)
        self.log(f"Login failed: {error_text}")
        messagebox.showerror(APP_TITLE, error_text)

    def fetch_non_followers(self) -> None:
        self._set_action_buttons(False)
        self.log("Loading accounts. This may take some time for large accounts...")

        def work() -> None:
            try:
                users = self.service.get_not_following_back()
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
        self.log(f"Found {len(users)} account(s) not following you back.")

    def _on_fetch_failed(self, error_text: str) -> None:
        self._set_action_buttons(True)
        self.log(f"Failed to load accounts: {error_text}")
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
        failed = result.get("failed", [])
        if removed:
            self.non_followers = [username for username in self.non_followers if username not in removed]
            self.user_list.delete(0, tk.END)
            for username in self.non_followers:
                self.user_list.insert(tk.END, username)

        self._set_action_buttons(True)
        self.log(
            f"Unfollow done. Removed: {len(result.get('removed', []))}, Failed: {len(result.get('failed', []))}."
        )
        if failed:
            messagebox.showwarning(APP_TITLE, "Finished with some failures. Check log for details.")
        else:
            messagebox.showinfo(APP_TITLE, "Finished successfully.")

    def _on_unfollow_failed(self, error_text: str) -> None:
        self._set_action_buttons(True)
        self.log(f"Unfollow failed: {error_text}")
        messagebox.showerror(APP_TITLE, error_text)

    def _parse_delay(self) -> float | None:
        try:
            delay = float(self.delay_var.get().strip())
        except ValueError:
            messagebox.showerror(APP_TITLE, "Delay must be a number.")
            return None
        if delay < 0.5:
            messagebox.showerror(APP_TITLE, "Delay must be at least 0.5 seconds.")
            return None
        return delay


def main() -> None:
    root = tk.Tk()
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = InstagramCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
