import argparse
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------
# Configuration & Environment Variables
# ---------------------------------------------------------
def load_env_file():
    """Load key-value pairs from .env if present (without requiring python-dotenv)."""
    env_path = Path(".env")
    if env_path.is_file():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val

load_env_file()

EMAIL = os.getenv("NAUKRI_EMAIL", "soujannyaroy@gmail.com")
PASSWORD = os.getenv("NAUKRI_PASSWORD", "")
DEFAULT_OLD_TITLE = "Software Engineer 1"
DEFAULT_NEW_TITLE = "Software Engineer"
SESSION_FILE = "naukri_session.json"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
LOGIN_URL = "https://www.naukri.com/nlogin/login"


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def get_current_designation(page) -> str:
    """Extract the current designation from the top profile card (.desg.typ-16Bold)."""
    try:
        page.wait_for_selector(".desg.typ-16Bold, div.desg, .subhdn", timeout=10000)
    except Exception:
        pass

    try:
        # Based on inspected DOM: <div class="desg typ-16Bold"><div>Software Engineer 1 ...</div></div>
        desg_loc = page.locator(".desg.typ-16Bold, div.desg, .subhdn .desg").first
        if desg_loc.is_visible(timeout=5000):
            full_text = desg_loc.inner_text().strip()
            lines = [line.strip() for line in full_text.splitlines() if line.strip()]
            if lines:
                return lines[0]
    except Exception as e:
        print(f"[-] Could not extract designation via .desg selector: {e}")

    try:
        subhdn = page.locator(".subhdn").first
        if subhdn.is_visible(timeout=3000):
            lines = [line.strip() for line in subhdn.inner_text().splitlines() if line.strip()]
            if lines:
                return lines[0]
    except Exception:
        pass

    return ""


def navigate_to_employment_section(page) -> bool:
    """Scroll/jump to the Employment section on the profile page."""
    print("[*] Navigating to Employment section...")

    # Method 1: Click 'Employment' link in the left Quick Links sidebar
    quick_links_selectors = [
        ".quick-links span:text-is('Employment')",
        ".quick-links a:text-is('Employment')",
        "xpath=//div[contains(@class, 'quick-links') or contains(@class, 'quickLink')]//*[text()='Employment']",
        "xpath=//a[text()='Employment']",
        "text=Employment",
    ]

    for sel in quick_links_selectors:
        try:
            link = page.locator(sel).first
            if link.is_visible(timeout=2000):
                print(f"[+] Clicking Quick Link: '{sel}'")
                link.click()
                time.sleep(1.5)
                return True
        except Exception:
            continue

    # Method 2: Scroll down to employment section container
    try:
        emp_container = page.locator("#lazyEmployment, div.card:has-text('Employment'), section:has-text('Employment')").first
        if emp_container.is_visible(timeout=3000):
            emp_container.scroll_into_view_if_needed()
            time.sleep(1.5)
            return True
    except Exception:
        pass

    # Method 3: JavaScript smooth scroll down
    page.evaluate("window.scrollBy(0, 600)")
    time.sleep(1.5)
    return True


def open_current_employment_edit(page, title_hint: str = "Software Engineer") -> bool:
    """
    Locate the current employment entry (under Employment section) and click its edit pencil icon.
    Avoids Resume Headline card by scoping to the section containing 'Add employment'.
    """
    print(f"[*] Looking for employment edit button for '{title_hint}'...")

    # Specifically target the Employment card (uniquely identified by 'Add employment')
    edit_candidates = [
        # 1. Edit icon next to the title inside the Employment card
        f"xpath=//div[contains(@class, 'card') and .//*[contains(text(), 'Add employment')]]//*[contains(text(), '{title_hint}')]/following::*[contains(@class, 'edit') or contains(@class, 'pencil') or self::em or self::span][1]",
        # 2. Any edit icon inside the Employment card
        "div.card:has-text('Add employment') span.edit",
        "div.card:has-text('Add employment') em.icon-edit",
        "div.card:has-text('Add employment') [class*='edit']",
        "xpath=//div[contains(@class, 'card') and .//*[contains(text(), 'Add employment')]]//*[contains(@class, 'edit') or contains(@class, 'pencil')]",
        # 3. Fallback to #lazyEmployment container
        "#lazyEmployment span.edit",
        "#lazyEmployment em.icon-edit",
        "#lazyEmployment [class*='edit']",
    ]

    for sel in edit_candidates:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                print(f"[+] Found employment edit button with selector: {sel}")
                loc.scroll_into_view_if_needed()
                loc.click()
                time.sleep(2)
                return True
        except Exception:
            continue

    return False


def find_designation_input(page, current_title: str):
    """
    Find the designation input field inside the opened Employment modal or drawer.
    """
    page.wait_for_timeout(1500)

    # 1. Look for input whose existing value matches current title (e.g., 'Software Engineer 1')
    if current_title:
        try:
            val_loc = page.locator(f"input[value='{current_title}']").first
            if val_loc.is_visible(timeout=2000):
                print(f"[+] Found designation input matching value: '{current_title}'")
                return val_loc
        except Exception:
            pass

    # 2. Scan all visible inputs in the modal/drawer
    try:
        inputs = page.locator("input[type='text'], input:not([type])").all()
        for inp in inputs:
            if inp.is_visible():
                val = inp.input_value().strip()
                if "software engineer" in val.lower() or (current_title and val.lower() == current_title.lower()):
                    print(f"[+] Found input field by matching value: '{val}'")
                    return inp
    except Exception:
        pass

    # 3. Standard label-based and attribute-based selectors in Employment form
    candidate_selectors = [
        "input[placeholder*='Designation' i]",
        "input[placeholder*='designation' i]",
        "input[placeholder*='Job Title' i]",
        "input[name='designation']",
        "input#designation",
        "input#designationField",
        "input[name*='designation' i]",
        "input[id*='designation' i]",
        "xpath=//label[contains(translate(., 'DESIGNATION', 'designation'), 'designation')]/following::input[1]",
        "xpath=//label[contains(translate(., 'DESIGNATION', 'designation'), 'designation')]/..//input",
        "xpath=//span[contains(translate(., 'DESIGNATION', 'designation'), 'designation')]/following::input[1]",
    ]

    for sel in candidate_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                print(f"[+] Found designation input with selector: {sel}")
                return loc
        except Exception:
            continue

    return None


def handle_suggestion_dropdown(page, target_title: str):
    """If an auto-complete dropdown appears after typing, select the matching item."""
    page.wait_for_timeout(800)
    suggestion_selectors = [
        f".sug-list li:has-text('{target_title}')",
        f"ul[class*='sug'] li:has-text('{target_title}')",
        f"div[class*='suggestion']:has-text('{target_title}')",
        f"div[class*='tuple']:has-text('{target_title}')",
        f"li:text-is('{target_title}')",
        f".ui-menu-item:has-text('{target_title}')",
    ]

    for sel in suggestion_selectors:
        try:
            item = page.locator(sel).first
            if item.is_visible(timeout=1500):
                print(f"[+] Clicking auto-suggestion option matching '{target_title}'")
                item.click()
                return True
        except Exception:
            continue

    return False


def click_save_button(page) -> bool:
    """Click the Save button inside the active Employment modal/drawer."""
    save_selectors = [
        "button#saveEmployment",
        "form[name='employmentForm'] button[type='submit']",
        "form button:has-text('Save')",
        ".drawer button:has-text('Save')",
        ".modal button:has-text('Save')",
        "button[type='submit']:has-text('Save')",
        "button:has-text('Save')",
        "button.btn-dark-large:has-text('Save')",
        "xpath=//button[translate(normalize-space(.), 'save', 'SAVE') = 'SAVE']",
        "xpath=//button[contains(., 'Save') and not(contains(., 'Cancel'))]",
    ]

    for sel in save_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                print(f"[+] Clicking Save button with selector: {sel}")
                loc.scroll_into_view_if_needed()
                loc.click()
                return True
        except Exception:
            continue

    return False


def is_authenticated_profile_page(page) -> bool:
    """Return True if currently on profile page and authenticated (not on login)."""
    current_url = page.url.lower()
    if "login" in current_url:
        return False
    if page.locator("#usernameField, input[placeholder*='Username']").count() > 0:
        return False
    if page.locator(".desg, .subhdn, .user-name, a[href*='profile']").count() > 0:
        return True
    return False


def ensure_login(context, page, email: str, password: str) -> bool:
    """Navigate to profile or log in if session is not active."""
    print("[*] Navigating to Naukri profile page...")
    page.goto(PROFILE_URL, timeout=60000)

    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    time.sleep(2)

    # Check if already authenticated on profile page
    if is_authenticated_profile_page(page):
        print("[+] Already logged in with active session!")
        return True

    # Otherwise perform login
    print("[*] No active session detected. Going to login page...")
    if "login" not in page.url.lower():
        page.goto(LOGIN_URL, timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

    if not email or not password:
        print("[!] ERROR: NAUKRI_EMAIL and NAUKRI_PASSWORD must be configured in .env file.")
        return False

    print(f"[*] Entering login credentials for {email}...")
    try:
        page.wait_for_selector("#usernameField", state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        print("[!] Could not find #usernameField on login page.")
        page.screenshot(path="error_login_page.png")
        return False

    page.fill("#usernameField", email)
    page.fill("#passwordField", password)
    page.click("button[type='submit']")

    print("[*] Submitted credentials.")
    print("    -> If Naukri displays a CAPTCHA or OTP prompt, please solve it in the browser window.")

    # Wait for URL to leave login page
    try:
        page.wait_for_url(
            lambda url: "nlogin" not in url.lower() and ("mnjuser" in url.lower() or "naukri.com" in url.lower()),
            timeout=60000
        )
    except PlaywrightTimeoutError:
        print("[!] Login wait timed out. Checking if navigated away from login...")

    # Ensure on profile page
    print("[*] Loading profile page...")
    page.goto(PROFILE_URL, timeout=60000)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_selector(".desg, .subhdn", state="visible", timeout=20000)
        print("[+] Profile page loaded successfully!")
    except Exception as e:
        print(f"[-] Waiting for profile elements: {e}")

    # Check if login succeeded
    if is_authenticated_profile_page(page):
        try:
            context.storage_state(path=SESSION_FILE)
            print(f"[+] Session saved to '{SESSION_FILE}' for future runs.")
        except Exception as e:
            print(f"[-] Could not save session: {e}")
        return True
    else:
        print("[!] Login verification failed: Still not on authenticated profile page.")
        page.screenshot(path="error_login_failed.png")
        return False


# ---------------------------------------------------------
# Main Tagline Update Routine
# ---------------------------------------------------------
def update_tagline(
    new_title: str = DEFAULT_NEW_TITLE,
    old_title: str = DEFAULT_OLD_TITLE,
    headless: bool = False,
    dry_run: bool = False,
    toggle: bool = False
):
    """
    Main function to update or toggle the profile tagline on Naukri.
    """
    print("=" * 60)
    print(" Naukri Tagline / Designation Updater (Playwright)")
    print("=" * 60)
    print(f"Target Title : {new_title}")
    print(f"Old Title    : {old_title}")
    print(f"Headless     : {headless}")
    print(f"Dry Run      : {dry_run}")
    print(f"Toggle Mode  : {toggle}")
    print("-" * 60)

    with sync_playwright() as p:
        # Launch browser (prefer installed Chrome for stealth, fallback to chromium)
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
        if Path(SESSION_FILE).is_file():
            print(f"[+] Loading existing session state from '{SESSION_FILE}'")
            context_args["storage_state"] = SESSION_FILE

        context = browser.new_context(**context_args)
        page = context.new_page()

        try:
            # Step 1: Ensure Logged In
            if not ensure_login(context, page, EMAIL, PASSWORD):
                print("[!] Login failed or credentials missing.")
                return False

            # Step 2: Extract current tagline from profile header
            print("[*] Inspecting profile header...")
            page.wait_for_timeout(2000)
            current_tagline = get_current_designation(page)
            print(f"[+] Detected current tagline: '{current_tagline}'")

            # Determine actual target if toggle mode is requested
            effective_target = new_title
            if toggle and current_tagline:
                if current_tagline.strip().lower() == new_title.strip().lower():
                    effective_target = old_title
                else:
                    effective_target = new_title
                print(f"[+] Toggle mode active: Switching from '{current_tagline}' -> '{effective_target}'")

            # Check if title already matches
            if current_tagline and current_tagline.strip().lower() == effective_target.strip().lower() and not dry_run:
                print(f"[!] Tagline is ALREADY '{effective_target}'. Nothing to update!")
                print("    (Tip: Use --toggle to alternate back and forth)")
                return True

            # Step 3: Scroll to Employment section & open edit modal
            # Note: Naukri's tagline is stored under the Employment section (current job at Best Buy)
            navigate_to_employment_section(page)

            print("[*] Opening Employment edit modal...")
            if not open_current_employment_edit(page, title_hint="Software Engineer"):
                print("[!] Failed to locate Employment edit pencil.")
                page.screenshot(path="error_employment_edit_not_found.png")
                return False

            # page.screenshot(path="employment_edit_opened.png")
            print("[+] Saved screenshot of opened form to 'employment_edit_opened.png'")

            # Step 4: Find Designation input field
            print(f"[*] Locating designation input (looking for '{current_tagline or old_title}')...")
            desg_input = find_designation_input(page, current_tagline or old_title)

            if not desg_input:
                print("[!] Designation input not found in Employment form.")
                page.screenshot(path="error_input_not_found.png")
                print("[!] Saved error screenshot to 'error_input_not_found.png'")
                return False

            # Step 5: Update the field with the new title
            print(f"[*] Filling new designation: '{effective_target}'...")
            desg_input.click()
            desg_input.fill("")
            # Type slowly to trigger React change/autocomplete events
            desg_input.type(effective_target, delay=50)

            # Handle autocomplete suggestions
            handle_suggestion_dropdown(page, effective_target)
            desg_input.press("Tab")

            page.wait_for_timeout(1000)

            # Step 6: Save changes or Dry Run
            if dry_run:
                print(f"[+] DRY-RUN SUCCESS: Form populated with '{effective_target}'. (Not saved)")
                # page.screenshot(path="dry_run_success.png")
                print("[+] Saved inspection screenshot to 'dry_run_success.png'")
                return True

            print("[*] Saving changes...")
            if not click_save_button(page):
                print("[-] Could not find Save button via primary selectors, pressing Enter...")
                desg_input.press("Enter")

            # Wait for save completion
            page.wait_for_timeout(3000)
            page.wait_for_load_state("networkidle")

            # Update saved session
            try:
                context.storage_state(path=SESSION_FILE)
            except Exception:
                pass

            # Step 7: Verify updated tagline in top profile header
            print("[*] Verifying update on profile...")
            page.goto(PROFILE_URL, timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            updated_tagline = get_current_designation(page)
            print(f"[+] Current tagline on profile after save: '{updated_tagline}'")

            # page.screenshot(path="profile_tagline_updated.png")
            print("[+] Saved verification screenshot to 'profile_tagline_updated.png'")

            if effective_target.lower() in updated_tagline.lower():
                print(f"\n[SUCCESS] Profile tagline successfully updated to '{effective_target}'!")
                return True
            else:
                print(f"\n[?] Warning: Detected tagline '{updated_tagline}' differs from target '{effective_target}'.")
                print("    Please check 'profile_tagline_updated.png' to review the result.")
                return False

        except Exception as e:
            print(f"[!] An error occurred during automation: {e}")
            try:
                page.screenshot(path="error_exception.png")
                print("[+] Saved error screenshot to 'error_exception.png'")
            except Exception:
                pass
            return False
        finally:
            browser.close()


# ---------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update Naukri profile tagline/designation using Playwright."
    )
    parser.add_argument(
        "--new-title",
        default=DEFAULT_NEW_TITLE,
        help=f"Target designation/tagline to set (default: '{DEFAULT_NEW_TITLE}')"
    )
    parser.add_argument(
        "--old-title",
        default=DEFAULT_OLD_TITLE,
        help=f"Expected current designation/tagline (default: '{DEFAULT_OLD_TITLE}')"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: False for visual testing)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Test mode: opens modal and fills the field, but does NOT click Save"
    )
    parser.add_argument(
        "--toggle",
        action="store_true",
        default=False,
        help="Toggle between old and new titles automatically (ideal for daily refreshing)"
    )

    args = parser.parse_args()

    success = update_tagline(
        new_title=args.new_title,
        old_title=args.old_title,
        headless=args.headless,
        dry_run=args.dry_run,
        toggle=args.toggle
    )

    sys.exit(0 if success else 1)
