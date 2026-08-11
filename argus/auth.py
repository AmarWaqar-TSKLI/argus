"""Login pre-step for auditing authenticated apps.

Credentials come from ARGUS_LOGIN_USER / ARGUS_LOGIN_PASSWORD env vars —
never CLI arguments, so they stay out of shell history and process lists.
The form is auto-detected (standard username/password/submit shapes), and
the authenticated session is saved to <run_dir>/auth.json so --resume can
restore it without logging in again.
"""
import os
from pathlib import Path

from argus import browser

USERNAME_SELECTOR = ("input[type=email], input[type=text], "
                     "input[name*=user i], input[name*=email i]")
SUBMIT_SELECTOR = "form button[type=submit], form input[type=submit], form button"


def login(login_url: str, run_dir: str) -> None:
    user = os.environ.get("ARGUS_LOGIN_USER", "")
    password = os.environ.get("ARGUS_LOGIN_PASSWORD", "")
    if not (user and password):
        raise SystemExit(
            "--login requires ARGUS_LOGIN_USER and ARGUS_LOGIN_PASSWORD env vars")

    page = browser.get_page()
    page.goto(login_url, wait_until="load", timeout=15000)
    page.locator(USERNAME_SELECTOR).first.fill(user, timeout=5000)
    page.locator("input[type=password]").first.fill(password, timeout=5000)
    page.locator(SUBMIT_SELECTOR).first.click(timeout=5000)
    page.wait_for_load_state("load")
    page.wait_for_timeout(600)

    state_path = str(Path(run_dir) / "auth.json")
    browser.save_storage_state(state_path)
    print(f"  logged in as {user} · session saved to auth.json", flush=True)
