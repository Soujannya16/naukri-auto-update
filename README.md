## Prerequisites

1. **Python 3.8+**
2. **Install Playwright:**
   ```bash
   pip install playwright
   playwright install chromium
   ```
3. **Configuration:**
   Create a `.env` file in the root directory:
   ```env
   NAUKRI_EMAIL=your_email@example.com
   NAUKRI_PASSWORD=your_password
   ```

---

## Usage

### 1. Dry Run (Recommended for First Run)
Tests navigation and form population without clicking Save:
```bash
python update_tagline.py --dry-run
```

### 2. Standard Update
Updates the current title to a specific designation:
```bash
python update_tagline.py --new-title "Software Engineer"
```

### 3. Toggle Mode (Profile Freshness)
Automatically swaps between old and new titles (e.g., `Software Engineer 1` <-> `Software Engineer`):
```bash
python update_tagline.py --toggle
```

### 4. Headless Execution
Run silently in the background:
```bash
python update_tagline.py --headless --toggle
```

## Features

- **Session Persistence**: Stores cookies in `naukri_session.json` to bypass repeated logins and CAPTCHAs.
- **Toggle Mode (`--toggle`)**: Alternates between two designated titles to refresh profile activity timestamps.
- **Dry-Run Mode (`--dry-run`)**: Validates DOM selectors and fills inputs without saving changes.
- **Robust Selectors**: Multi-layer fallback selectors tailored to Naukri's Employment DOM structure.
- **Auto-Suggestion Handling**: Automatically selects exact matches from Naukri's designation dropdown.
- **Headed & Headless Modes**: Runs headed by default for visibility; supports headless execution for background jobs.
- **Visual Verification**: Saves before and after screenshots (`profile_tagline_updated.png`, `dry_run_success.png`, or `error_exception.png`) for auditability.

---

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--new-title` | `Software Engineer` | Target designation to apply |
| `--old-title` | `Software Engineer 1` | Alternate/fallback designation |
| `--toggle` | `False` | Swaps between old and new titles automatically |
| `--dry-run` | `False` | Opens modal and fills fields without saving |
| `--headless` | `False` | Runs browser in headless mode |
