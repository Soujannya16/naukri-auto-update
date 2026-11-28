import argparse
from datetime import datetime
import logging
import os
import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

SCRIPT_DIR = Path(__file__).resolve().parent
RESUME_PREFIX = "Roy_Soujannya_Resume"
DATE_SUFFIX_PATTERN = re.compile(r"_\d{2}-\d{2}-\d{4}$")
SESSION_FILE = SCRIPT_DIR / "naukri_session.json"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
LOGIN_URL = "https://www.naukri.com/nlogin/login"

# XPaths matching the "Update resume" button in the Naukri Resume card (#lazyAttachCV)
UPDATE_RESUME_XPATHS = [
    "xpath=//div[@id='lazyAttachCV']//input[@type='button' and @value='Update resume' and contains(@class, 'dummyUpload')]",
    "xpath=//div[@id='lazyAttachCV']//input[contains(@class, 'dummyUpload')]",
    "xpath=//input[@type='button' and @value='Update resume' and contains(@class, 'dummyUpload')]",
    "xpath=//div[contains(@class, 'uploadBtn')]//input[@type='button' and contains(@class, 'dummyUpload')]",
]
FILE_INPUT_FALLBACK_XPATH = "xpath=//div[@id='lazyAttachCV']//input[@type='file']"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("naukri_resume_updater")


def load_env_file() -> None:
    """Load key-value pairs from .env in the script directory if present."""
    env_path = SCRIPT_DIR / ".env"
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


def find_latest_matching_resume(search_dir: Path, prefix: str) -> Path | None:
    """Find the most recently modified PDF matching '<prefix>_*.pdf' or '<prefix>.pdf'."""
    candidates = sorted(
        list(search_dir.glob(f"{prefix}_*.pdf")) + list(search_dir.glob(f"{prefix}.pdf")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0].resolve() if candidates else None


def resolve_resume_path(resume_arg: str | None) -> Path | None:
    """Locate the resume file, falling back to existing dated variants if needed."""
    today_str = datetime.now().strftime("%d-%m-%Y")

    if resume_arg:
        path = Path(resume_arg)
        if not path.is_absolute():
            path = SCRIPT_DIR / path
        if path.is_file():
            return path.resolve()

        # If a previously dated path was configured (e.g. in .env), look for today's or latest match
        base_prefix = DATE_SUFFIX_PATTERN.sub("", path.stem)
        search_dir = path.parent if path.parent.is_dir() else SCRIPT_DIR
        todays_file = search_dir / f"{base_prefix}_{today_str}{path.suffix}"
        if todays_file.is_file():
            return todays_file.resolve()
        latest = find_latest_matching_resume(search_dir, base_prefix)
        if latest:
            return latest
        logger.error("Resume file not found: %s", path)
        return None

    todays_default = SCRIPT_DIR / f"{RESUME_PREFIX}_{today_str}.pdf"
    if todays_default.is_file():
        return todays_default.resolve()

    latest = find_latest_matching_resume(SCRIPT_DIR, RESUME_PREFIX)
    if latest:
        return latest

    logger.error("No matching resume PDF found in %s for prefix '%s'.", SCRIPT_DIR, RESUME_PREFIX)
    return None


def update_resume_filename_with_today(resume_path: Path) -> Path:
    """Rename the CV file's trailing date segment (DD-MM-YYYY) to today's date."""
    today_str = datetime.now().strftime("%d-%m-%Y")
    if DATE_SUFFIX_PATTERN.search(resume_path.stem):
        new_stem = DATE_SUFFIX_PATTERN.sub(f"_{today_str}", resume_path.stem)
    else:
        new_stem = f"{resume_path.stem}_{today_str}"

    new_path = resume_path.with_name(f"{new_stem}{resume_path.suffix}")
    if new_path == resume_path:
        logger.info("Resume filename already reflects today's date: %s", resume_path.name)
        return resume_path

    if new_path.exists():
        logger.info("Target dated resume already exists, using: %s", new_path.name)
        return new_path

    resume_path.rename(new_path)
    logger.info("Renamed resume file for today's upload: '%s' -> '%s'", resume_path.name, new_path.name)
    return new_path


def is_authenticated_profile_page(page) -> bool:
    """Return True if currently on the authenticated Naukri profile page."""
    current_url = page.url.lower()
    if "login" in current_url or "nlogin" in current_url:
        return False
    if page.locator("#usernameField").count() > 0:
        return False
    return "mnjuser/profile" in current_url or page.locator("#lazyAttachCV").count() > 0


def ensure_login(context, page, email: str, password: str) -> bool:
    """Navigate to profile page and log in if no active session exists."""
    logger.info("Navigating to Naukri profile page: %s", PROFILE_URL)
    page.goto(PROFILE_URL, timeout=60000)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError:
        logger.debug("Timed out waiting for domcontentloaded on initial profile load.")
    time.sleep(2)

    if is_authenticated_profile_page(page):
        logger.info("Already authenticated using existing session.")
        return True

    logger.info("No active session detected. Proceeding to login.")
    if "login" not in page.url.lower():
        page.goto(LOGIN_URL, timeout=60000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except PlaywrightTimeoutError:
            pass

    if not email or not password:
        logger.error("NAUKRI_EMAIL and NAUKRI_PASSWORD must be configured in .env or environment variables.")
        return False

    try:
        page.wait_for_selector("#usernameField", state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        logger.error("Login form (#usernameField) did not become visible on %s", page.url)
        return False

    logger.info("Submitting login credentials for %s", email)
    page.fill("#usernameField", email)
    page.fill("#passwordField", password)
    page.click("button[type='submit']")

    try:
        page.wait_for_url(
            lambda url: "nlogin" not in url.lower() and "login" not in url.lower() and "mnjuser" in url.lower(),
            timeout=60000,
        )
    except PlaywrightTimeoutError:
        logger.warning("Login redirect wait timed out; checking profile page directly.")

    page.goto(PROFILE_URL, timeout=60000)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError:
        pass
    time.sleep(2)

    if not is_authenticated_profile_page(page):
        logger.error("Login verification failed; still not on authenticated profile page (%s).", page.url)
        return False

    try:
        context.storage_state(path=str(SESSION_FILE))
        logger.info("Saved authenticated session to %s", SESSION_FILE)
    except Exception as exc:
        logger.warning("Failed to save session state: %s", exc)

    return True


def find_update_resume_button(page):
    """Locate the visible 'Update resume' button using the configured XPaths."""
    for xpath in UPDATE_RESUME_XPATHS:
        loc = page.locator(xpath).first
        try:
            if loc.is_visible(timeout=4000):
                logger.info("Located 'Update resume' button using selector: %s", xpath)
                return loc
        except Exception:
            continue
    return None


def upload_resume(page, resume_path: Path) -> bool:
    """Trigger the Update resume button and upload the given PDF file."""
    logger.info("Waiting for Resume section (#lazyAttachCV)...")
    try:
        page.wait_for_selector("#lazyAttachCV", state="visible", timeout=20000)
    except PlaywrightTimeoutError:
        logger.error("Resume section (#lazyAttachCV) did not become visible on %s", page.url)
        return False

    upload_btn = find_update_resume_button(page)
    if upload_btn is None:
        logger.error("Could not locate 'Update resume' button with any configured XPath.")
        return False

    upload_btn.scroll_into_view_if_needed()

    logger.info("Clicking 'Update resume' button to upload: %s", resume_path)
    uploaded = False
    try:
        with page.expect_file_chooser(timeout=10000) as fc_info:
            upload_btn.click()
        file_chooser = fc_info.value
        file_chooser.set_files(str(resume_path))
        uploaded = True
        logger.info("Selected file via browser file chooser: %s", resume_path.name)
    except PlaywrightTimeoutError:
        logger.warning("File chooser did not open on button click; trying hidden file input fallback.")
        file_input = page.locator(FILE_INPUT_FALLBACK_XPATH).first
        if file_input.count() > 0:
            file_input.set_input_files(str(resume_path))
            uploaded = True
            logger.info("Selected file via fallback file input: %s", resume_path.name)

    if not uploaded:
        logger.error("Failed to attach resume file via both file chooser and fallback file input.")
        return False

    # Wait for upload network request / DOM status update
    logger.info("Waiting for upload confirmation...")
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except PlaywrightTimeoutError:
        logger.debug("Network did not go completely idle within 20s; continuing verification.")
    time.sleep(3)

    result_text = ""
    try:
        result_loc = page.locator("#lazyAttachCV #result, #lazyAttachCV #results_resumeParser").first
        if result_loc.count() > 0:
            result_text = result_loc.inner_text().strip()
    except Exception:
        pass

    if result_text:
        logger.info("Naukri upload status text: %s", result_text)

    card_text = ""
    try:
        card_text = page.locator("#lazyAttachCV").inner_text()
    except Exception as exc:
        logger.warning("Could not read #lazyAttachCV text after upload: %s", exc)

    if resume_path.name in card_text:
        logger.info("Verified uploaded filename '%s' is displayed in the Resume section.", resume_path.name)
    elif "error" in result_text.lower() or "failed" in result_text.lower():
        logger.error("Upload reported an error from Naukri: %s", result_text)
        return False
    else:
        logger.warning(
            "Upload completed, but '%s' was not detected in #lazyAttachCV text yet. Check profile manually.",
            resume_path.name,
        )

    return True


def update_profile(resume_path: Path, headless: bool = False) -> bool:
    """Update CV filename to today's date, log into Naukri, and upload the PDF."""
    email = os.getenv("NAUKRI_EMAIL", "")
    password = os.getenv("NAUKRI_PASSWORD", "")

    if not resume_path.is_file():
        logger.error("Resume file not found: %s", resume_path)
        return False

    try:
        resume_path = update_resume_filename_with_today(resume_path)
    except OSError as exc:
        logger.error("Failed to rename resume file '%s' with today's date: %s", resume_path, exc)
        return False

    logger.info("Starting Naukri resume update | resume=%s | headless=%s", resume_path, headless)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                channel="chrome",
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )

        context_args = {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 800},
        }
        if SESSION_FILE.is_file():
            logger.info("Loading saved session from %s", SESSION_FILE)
            context_args["storage_state"] = str(SESSION_FILE)

        context = browser.new_context(**context_args)
        page = context.new_page()

        try:
            if not ensure_login(context, page, email, password):
                logger.error("Aborting resume upload due to authentication failure.")
                return False

            if not upload_resume(page, resume_path):
                logger.error("Resume upload failed.")
                return False

            try:
                context.storage_state(path=str(SESSION_FILE))
            except Exception as exc:
                logger.warning("Could not refresh session file: %s", exc)

            logger.info("SUCCESS: Naukri profile resume updated with '%s'.", resume_path.name)
            return True

        except Exception as exc:
            logger.exception("Unexpected error while updating Naukri resume: %s", exc)
            return False
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload/update resume on Naukri profile using Playwright.")
    parser.add_argument(
        "--resume",
        default=os.getenv("RESUME_PATH") or None,
        help=f"Path to resume PDF (defaults to latest {RESUME_PREFIX}_*.pdf in script folder)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode",
    )
    args = parser.parse_args()

    target_resume = resolve_resume_path(args.resume)
    if target_resume is None:
        sys.exit(1)

    ok = update_profile(resume_path=target_resume, headless=args.headless)
    sys.exit(0 if ok else 1)
