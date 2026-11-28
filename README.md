# Naukri Auto-Update

Playwright scripts to keep your Naukri.com profile fresh and updated automatically.

## Scripts Overview

| Script | What it updates | Best for |
|--------|-----------------|----------|
| `update_headline.py` | Toggles a trailing `.` in **Resume Headline** | Fastest daily freshness refresh (~5s, single field) |
| `update_naukri.py` | Renames & re-uploads your **Resume PDF** with today's date | Refreshing profile + keeping uploaded CV date current |
| `update_tagline.py` | Updates current role designation in **Employment** | Updating/toggling the profile tagline under your name |

---

## Prerequisites

1. **Python 3.8+**
2. **Install Playwright:**
   ```bash
   pip install playwright
   playwright install chromium
   ```
3. **Configuration:**
   Create a `.env` file in the project root (all file paths are anchored to the script directory):
   ```env
   NAUKRI_EMAIL=your_email@example.com
   NAUKRI_PASSWORD=your_password
   # Optional for update_naukri.py:
   RESUME_PATH=Roy_Soujannya_Resume.pdf
   ```

---

## Usage

### 1. Resume Headline Refresh (`update_headline.py`)
Toggles a trailing period (`.`) on your Resume Headline to trigger Naukri's "Updated Today" status:
```bash
python update_headline.py --dry-run   # Preview change without saving
python update_headline.py             # Run headed
python update_headline.py --headless  # Run in background
```

### 2. Resume PDF Upload (`update_naukri.py`)
Updates the trailing `_DD-MM-YYYY` date in your resume filename to today's date and uploads it to `#lazyAttachCV`:
```bash
python update_naukri.py                              # Uses RESUME_PATH or latest Roy_Soujannya_Resume_*.pdf
python update_naukri.py --resume path/to/resume.pdf  # Specify custom resume PDF
python update_naukri.py --headless                   # Run in background
```

### 3. Profile Tagline / Designation (`update_tagline.py`)
Edits your current job title under the Employment section:
```bash
python update_tagline.py --dry-run                      # Test selectors without saving
python update_tagline.py --new-title "Software Engineer" # Set specific title
python update_tagline.py --toggle                       # Alternate between old and new titles
python update_tagline.py --headless --toggle            # Run toggle silently in background
```

---

## Shared Features

- **Session Persistence**: Stores browser state in `naukri_session.json` to bypass repeated logins and CAPTCHAs.
- **Directory-Anchored Paths**: All scripts resolve `.env`, `naukri_session.json`, and output files relative to the script directory, safe to run from any working directory (e.g., cron / Task Scheduler).
- **Headed & Headless Modes**: Headed by default for visibility; pass `--headless` for automated runs.

---

## CLI Options

### `update_headline.py`
| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | `False` | Toggles headline in form without saving |
| `--headless` | `False` | Runs browser in headless mode |

### `update_naukri.py`
| Flag | Default | Description |
|------|---------|-------------|
| `--resume` | `RESUME_PATH` / latest `Roy_Soujannya_Resume_*.pdf` | Path to resume PDF |
| `--headless` | `False` | Runs browser in headless mode |

### `update_tagline.py`
| Flag | Default | Description |
|------|---------|-------------|
| `--new-title` | `Software Engineer` | Target designation to apply |
| `--old-title` | `Software Engineer 1` | Alternate/fallback designation |
| `--toggle` | `False` | Swaps between old and new titles automatically |
| `--dry-run` | `False` | Opens modal and fills fields without saving |
| `--headless` | `False` | Runs browser in headless mode |
