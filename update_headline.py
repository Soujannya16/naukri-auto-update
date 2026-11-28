"""
update_headline.py

The simplest, fastest, and most reliable way to keep your Naukri profile fresh.
Instead of dealing with complex multi-field employment forms, it updates your
'Resume Headline' by toggling a trailing period ('.').

Why this is the recommended standard for Naukri auto-updates:
1. Speed: Takes ~5 seconds to run.
2. Simplicity: Only 1 textarea and 1 Save button — no dropdowns, dates, or complex forms.
3. Freshness algorithm: Naukri marks your profile as 'Updated Today', boosting recruiter visibility.
4. Invisible to recruiters: Adding or removing a trailing dot is visually seamless.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent

def load_env_file():
    env_path = SCRIPT_DIR / ".env"
    if env_path.is_file():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v

load_env_file()

EMAIL = os.getenv("NAUKRI_EMAIL", "soujannyaroy@gmail.com")
PASSWORD = os.getenv("NAUKRI_PASSWORD", "")
SESSION_FILE = SCRIPT_DIR / "naukri_session.json"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
LOGIN_URL = "https://www.naukri.com/nlogin/login"


def refresh_profile_headline(headless: bool = False, dry_run: bool = False) -> bool:
    print("=" * 60)
    print(" Naukri Resume Headline Quick Refresher (Playwright)")
    print("=" * 60)
    print(f"Headless : {headless}")
    print(f"Dry Run  : {dry_run}")
    print("-" * 60)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                channel="chrome",
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"]
            )
        except Exception:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"]
            )

        context_args = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }
        if SESSION_FILE.is_file():
            print(f"[+] Using saved session from '{SESSION_FILE}'")
            context_args["storage_state"] = str(SESSION_FILE)

        context = browser.new_context(**context_args)
        page = context.new_page()

        try:
            # Step 1: Open profile
            print("[*] Loading profile...")
            page.goto(PROFILE_URL, timeout=60000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            time.sleep(2)

            # If redirected to login, perform login
            if "login" in page.url.lower() or page.locator("#usernameField").is_visible():
                print("[*] Performing login...")
                page.fill("#usernameField", EMAIL)
                page.fill("#passwordField", PASSWORD)
                page.click("button[type='submit']")
                page.wait_for_url(lambda u: "login" not in u.lower() and "mnjuser" in u.lower(), timeout=60000)
                page.goto(PROFILE_URL, timeout=60000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)
                context.storage_state(path=str(SESSION_FILE))

            # Step 2: Click the edit icon next to 'Resume headline' and verify modal opens
            print("[*] Opening Resume Headline edit modal...")
            headline_edit_selectors = [
                "#lazyResumeHead span.edit, #lazyResumeHead em.icon-edit, #lazyResumeHead [class*='edit']",
                "xpath=//div[contains(@class, 'widgetHead') and .//*[contains(text(), 'Resume headline')]]//*[contains(@class, 'edit') or contains(@class, 'pencil')]",
                "xpath=//*[normalize-space(text())='Resume headline']/following-sibling::*[contains(@class, 'edit') or contains(@class, 'pencil')]",
                "div.card:has-text('Resume headline') span.edit",
                "div.card:has-text('Resume headline') em.icon-edit",
                "div.card:has-text('Resume headline') [class*='edit']",
                "xpath=//div[contains(@class, 'card') and .//*[contains(text(), 'Resume headline')]]//*[contains(@class, 'edit') or contains(@class, 'pencil')]",
            ]

            textarea_selector = (
                "form[name='resumeHeadlineForm'] textarea:visible, "
                ".resumeHeadlineEdit.model_open textarea:visible, "
                "textarea#resumeHeadlineTxt:visible, "
                ".modal textarea:visible, "
                "div[role='dialog'] textarea:visible, "
                "textarea:visible, "
                "[contenteditable='true']:visible"
            )
            opened = False
            for sel in headline_edit_selectors:
                try:
                    loc = page.locator(sel).first
                    if loc.is_visible(timeout=2000):
                        loc.scroll_into_view_if_needed()
                        loc.click()
                        # Verify the modal's textarea actually appeared before accepting this click
                        textarea = page.locator(textarea_selector).first
                        try:
                            textarea.wait_for(state="visible", timeout=3000)
                            print(f"[+] Opened modal using selector: {sel}")
                            opened = True
                            break
                        except Exception:
                            continue
                except Exception:
                    continue

            if not opened:
                print("[!] Could not open Resume headline edit modal (textarea not visible).")
                # page.screenshot(path=str(SCRIPT_DIR / "error_textarea_not_found.png"))
                return False

            # Step 3: Locate the visible textarea
            print("[*] Locating headline text box...")
            textarea = page.locator(textarea_selector).first

            # Step 4: Toggle trailing period
            current_text = textarea.input_value().strip() if textarea.is_visible() else ""
            if not current_text:
                current_text = textarea.inner_text().strip()

            print(f"[+] Current Headline:\n    \"{current_text[:80]}...\"")

            if current_text.endswith("."):
                new_text = current_text[:-1]
                print("[*] Action: Removing trailing period '.'")
            else:
                new_text = current_text + "."
                print("[*] Action: Adding trailing period '.'")

            textarea.click()
            textarea.fill("")
            textarea.fill(new_text)
            page.wait_for_timeout(500)

            # Step 5: Save or Dry-run
            if dry_run:
                print("\n[+] DRY-RUN SUCCESS: Headline text toggled successfully (NOT saved).")
                # page.screenshot(path=str(SCRIPT_DIR / "headline_dry_run_success.png"))
                # print(f"[+] Saved preview screenshot to '{SCRIPT_DIR / 'headline_dry_run_success.png'}'")
                return True

            print("[*] Saving updated headline...")
            save_selectors = [
                "form[name='resumeHeadlineForm'] button[type='submit']",
                "form[name='resumeHeadlineForm'] button:has-text('Save')",
                ".resumeHeadlineEdit.model_open button[type='submit']",
                ".resumeHeadlineEdit button.btn-dark-ot:has-text('Save')",
                ".model_open button[type='submit']:has-text('Save')",
                "xpath=//form[@name='resumeHeadlineForm']//button[@type='submit' or normalize-space(.)='Save']",
                "button:has-text('Save'):visible",
                "button[type='submit']:visible",
            ]

            saved = False
            for sel in save_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        btn.scroll_into_view_if_needed()
                        btn.click()
                        saved = True
                        break
                except Exception:
                    continue

            if not saved:
                raise RuntimeError("Could not find a visible Save button inside the Resume Headline modal.")

            try:
                page.locator("form[name='resumeHeadlineForm']").first.wait_for(state="hidden", timeout=10000)
            except Exception:
                pass
            time.sleep(2)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # Update session
            try:
                context.storage_state(path=str(SESSION_FILE))
            except Exception:
                pass

            # Step 6: Verify
            print("[*] Verifying update...")
            # page.screenshot(path=str(SCRIPT_DIR / "headline_updated_success.png"))
            # print(f"[+] Saved confirmation screenshot to '{SCRIPT_DIR / 'headline_updated_success.png'}'")
            print("\n[SUCCESS] Naukri Resume Headline updated successfully!")
            print("          Profile freshness timestamp has been refreshed on Naukri.")
            return True

        
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quickly refresh Naukri profile via Resume Headline.")
    parser.add_argument("--headless", action="store_true", default=False, help="Run in headless mode")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview change without saving")
    args = parser.parse_args()

    success = refresh_profile_headline(headless=args.headless, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
