import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


# -------------------------------------------------------
# CONFIGURATION — reads everything from config.json
# -------------------------------------------------------
def load_config():
    config_path = "config.json"
    if not os.path.exists(config_path):
        print("ERROR: config.json not found. Please create it first.")
        exit()
    with open(config_path, "r") as f:
        return json.load(f)

config = load_config()


# -------------------------------------------------------
# API CLIENT SETUP — picks the right API based on config
# -------------------------------------------------------
def setup_client():
    provider = config["api_provider"].lower()

    if provider == "groq":
        from groq import Groq
        return Groq(api_key=os.getenv("GROQ_API_KEY")), "groq"

    elif provider == "openai":
        from openai import OpenAI
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")), "openai"

    elif provider == "gemini":
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return client, "gemini"

    else:
        print(f"ERROR: Unknown API provider '{provider}' in config.json")
        print("Supported providers: groq, openai, gemini")
        exit()

client, provider = setup_client()


# -------------------------------------------------------
# SYSTEM PROMPT
# -------------------------------------------------------
SYSTEM_PROMPT = """
You are a weekly engineering report formatter.
Your job is to take raw development notes and convert them into a clean, structured weekly report.

Always output in EXACTLY this format — never skip any section:

{TEAM}, {DATE} ({DATE_RANGE})

Key Updates

    {Module or Person Name}
        - {update 1}
        - {update 2}
        - {update 3}

Key Achievements
    - {summarize the main wins in 2-3 points}

Challenges Encountered
    - {any blockers mentioned, or write: None}

Team Challenges
    - {team-level challenges, or write: None}

Key Tasks Scheduled for Next Week
    - {next week tasks or None}

CRITICAL rules you must follow — read every rule carefully:

RULE 1 — GROUPING:
- If the input is organized by PERSON NAME (like Arun, Sumit, Milind) keep it grouped by person name
- If the input is organized by MODULE NAME (like React Interview, Live Interview) keep it grouped by module name
- Never change the grouping structure that already exists in the input
- Never merge person names into module names or vice versa

RULE 2 — BULLET POINTS:
- Every single update must be on its own separate line with a dash (-)
- Never merge multiple updates into one long line
- Never use commas to join separate updates together
- Each fix, feat, enhc, chore, update must be its own separate bullet point
- If a sub-section has multiple items keep them as one bullet

RULE 3 — TICKET IDs:
- Keep ticket IDs exactly as they appear in the raw input
- Never add extra # symbols
- Never repeat # if it already appears once in a list
- For ticket lists like #14798, 15058, 14888 keep them together in one bullet as written

RULE 4 — ALREADY FORMATTED INPUT:
- If the input already looks mostly formatted and structured, do minimal changes
- Only fix indentation, add missing dashes, and ensure all 5 sections exist
- Do not restructure or reorder content that is already well organized
- Do not rewrite or summarize content that is already clean

RULE 5 — EMPTY SECTIONS:
- If a module has no updates or just a dash (-) keep it as:
    {Module Name}
        -
- Never delete modules even if they appear empty

RULE 6 — PRESERVE CONTENT:
- Never summarize or shorten any update
- Never rewrite updates in your own words
- Keep exact wording from the input
- Keep all technical terms, function names, and code references exactly as written

RULE 7 — ACHIEVEMENTS:
- Write exactly 3 achievement points based on what was actually done
- Each point must mention a specific feature, fix, or module with its actual name
- Each point must include what specifically was done — not vague summaries
- NEVER write generic statements like "Fixed several issues" or "Implemented new features"
- Good example: "Implemented cron-based scheduling and Xvfb headless browser in Auto Job Apply Script"
- Bad example: "Fixed several issues and improved performance"

RULE 8 — SUB-HEADINGS INSIDE PERSON SECTIONS:
- When a person's section has sub-headings (like Bug:, ATS:, Candidate Recommendation:, AI Interview:)
  those sub-headings must appear as their OWN indented heading — NOT repeated on every bullet
- Format it like this:

    PersonName
        SubHeading:
            - update 1
            - update 2
        AnotherSubHeading:
            - update 1

- NEVER format it like this (wrong):
    PersonName
        - SubHeading: update 1
        - SubHeading: update 2

- The sub-heading appears ONCE as a label, then all its items are indented below it
- This applies to any sub-section inside a person block: Bug, ATS, fixes, features etc.

RULE 9 — NO HALLUCINATION OR COMMENTARY:
- Never add content that does not exist in the raw input
- Never copy updates from one person's section into another person's section
- Never add explanatory text like "was not present" or "note:" or any commentary
- Never modify the meaning of any update
- If a line says "fix: #14804, using empty string as initial name" output it EXACTLY as written
- Output only what is in the raw input — nothing more, nothing less
"""


# -------------------------------------------------------
# SORTING — sorts files in proper numerical order
# week1, week2, week3... not week1, week10, week11
# -------------------------------------------------------
def sort_key(filename):
    numbers = re.findall(r'\d+', filename)
    return (int(numbers[0]) if numbers else 0, filename)


# -------------------------------------------------------
# FUNCTION: extract_dates_from_file
# Reads the top of a raw file and extracts date and
# date range if they are written there.
# Format expected at top of file:
#   Date: Apr 20, 2026
#   Range: Apr 13 – Apr 20
# If not found, returns None and falls back to config.json
# -------------------------------------------------------
def extract_dates_from_file(raw_text):
    report_date = None
    date_range = None

    lines = raw_text.strip().split("\n")

    for line in lines[:5]:  # Only check first 5 lines
        line = line.strip()

        # Check for date line
        if line.lower().startswith("date:"):
            report_date = line.split(":", 1)[1].strip()

        # Check for range line
        elif line.lower().startswith("range:"):
            date_range = line.split(":", 1)[1].strip()

        # Stop looking once we hit actual content
        elif line and not line.lower().startswith("date") and not line.lower().startswith("range"):
            break

    return report_date, date_range


# -------------------------------------------------------
# FUNCTION: strip_date_header
# Removes the date header lines from raw text before
# sending to AI — AI should not see the date header
# as part of the raw notes
# -------------------------------------------------------
def strip_date_header(raw_text):
    lines = raw_text.strip().split("\n")
    cleaned = []
    skip_blank = True

    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith("date:") or stripped.startswith("range:"):
            continue
        else:
            if skip_blank and not line.strip():
                continue
            skip_blank = False
            cleaned.append(line)

    return "\n".join(cleaned)

# -------------------------------------------------------
# EDGE CASE CHECKS
# -------------------------------------------------------
def is_too_short(text):
    words = text.split()
    return len(words) < 10


def has_no_modules(text):
    common_module_keywords = [
        "interview", "integration", "api", "bot", "script",
        "dashboard", "app", "service", "fix", "feat", "enhc",
        "chore", "update", "bug", "frontend", "backend", "mobile",
        "react", "live", "candidate", "jobma", "auto", "admin",
        "payment", "notification", "auth", "search", "analytics",
        "email", "jent", "#"
    ]
    text_lower = text.lower()
    matches = sum(1 for keyword in common_module_keywords if keyword in text_lower)
    return matches < 2


def looks_like_gibberish(text):
    letters = sum(c.isalpha() for c in text)
    total = len(text.replace(" ", "").replace("\n", ""))
    if total == 0:
        return True
    return (letters / total) < 0.6


def validate_input(text):
    issues = []
    if not text.strip():
        issues.append("empty")
        return issues
    if is_too_short(text):
        issues.append("too_short")
    if looks_like_gibberish(text):
        issues.append("gibberish")
    if has_no_modules(text):
        issues.append("no_modules")
    return issues


# -------------------------------------------------------
# FUNCTION: ask_user_for_input
# Handles all edge cases interactively
# -------------------------------------------------------
def ask_user_for_input(issues, current_text):
    print("\n" + "=" * 60)
    print("INPUT ISSUES DETECTED")
    print("=" * 60)

    extra_info = ""

    if "empty" in issues:
        print("\nThe file appears to be empty.")
        print("Please type your raw notes below.")
        print("When done, type END on a new line and press Enter:")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        return "\n".join(lines)

    if "gibberish" in issues:
        print("\nYour input contains a lot of special characters or symbols.")
        print("Please confirm this is correct engineering notes (yes/no): ", end="")
        answer = input().strip().lower()
        if answer == "no":
            print("Please retype your notes below.")
            print("When done, type END on a new line and press Enter:")
            lines = []
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            return "\n".join(lines)
        else:
            return "CONFIRMED:" + current_text

    if "too_short" in issues:
        print("\nYour input seems very short or incomplete.")
        print(f"Current input:\n{current_text}\n")
        print("Would you like to add more details? (yes/no): ", end="")
        answer = input().strip().lower()
        if answer == "yes":
            print("Type additional notes below.")
            print("When done, type END on a new line and press Enter:")
            lines = []
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            extra_info = "\n" + "\n".join(lines)

    if "no_modules" in issues:
        print("\nI could not detect any module or project names in your notes.")
        print("Example modules: React Interview, Live Interview, Integration")
        print("\nPlease enter the module/project names involved this week")
        print("(comma separated, e.g: React Interview, Live Interview, API):")
        modules_input = input().strip()
        if modules_input:
            extra_info += f"\nModules involved this week: {modules_input}"

    return current_text + extra_info


# -------------------------------------------------------
# FUNCTION: ask_for_metadata
# Confirms team name, date, date range once per run
# -------------------------------------------------------
def ask_for_metadata(team_name, report_date, date_range):
    print("\n" + "-" * 40)
    print("Please confirm report details:")
    print("-" * 40)

    print(f"Team name is '{team_name}'. Press Enter to keep or type new name: ", end="")
    new_name = input().strip()
    if new_name:
        team_name = new_name

    print(f"Report date is '{report_date}'. Press Enter to keep or type new date: ", end="")
    new_date = input().strip()
    if new_date:
        report_date = new_date

    print(f"Date range is '{date_range}'. Press Enter to keep or type new range: ", end="")
    new_range = input().strip()
    if new_range:
        date_range = new_range

    return team_name, report_date, date_range


# -------------------------------------------------------
# FUNCTION: format_report
# Sends raw notes to whichever API is configured
# -------------------------------------------------------
def format_report(raw_text, team_name, report_date, date_range):
    user_message = f"""
Team: {team_name}
Report Date: {report_date}
Date Range: {date_range}

Raw updates to format:
{raw_text}
"""

    print(f"\n  Sending to {provider.upper()} API ({config['model']})... please wait.")

    if provider in ["groq", "openai"]:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"]
        )
        return response.choices[0].message.content

    elif provider == "gemini":
        from google.genai import types
        response = client.models.generate_content(
            model=config["model"],
            contents=SYSTEM_PROMPT + "\n\n" + user_message,
            config=types.GenerateContentConfig(
                max_output_tokens=config["max_tokens"],
                temperature=config["temperature"]
            )
        )
        return response.text


# -------------------------------------------------------
# FUNCTION: fix_ticket_ids
# Fixes two ticket ID formatting issues:
# 1. #14798, #15058, #14888 → #14798, 15058, 14888
#    (# should appear only once at the start)
# 2. inte- 1059, 1067 → #inte- 1059, 1067
#    jent- 14954 → #jent- 14954
#    (add # if missing at start of ticket reference)
# -------------------------------------------------------
def fix_ticket_ids(text):
    lines = text.split("\n")
    fixed_lines = []

    for line in lines:

        # Fix 1 — add # before jent- and inte- if missing
        # Handles both "jent-15038" and "jent- 15038" (with space)
        line = re.sub(r'(?<!#)(jent-\s*|inte-\s*)(\d+)', r'#\1\2', line)

        # Fix 2 — add # before standalone numbers after fix:/bug: etc
        # Example: "fix: 14969" → "fix: #14969"
        line = re.sub(r'(fix:|bug:|enhc:|update:|feat:)\s+(\d+)', r'\1 #\2', line)

        # Fix 3 — remove duplicate # in ticket ID lists
        # Strategy: find first # position, then remove ALL subsequent #
        # that appear before digits or ticket prefixes
        if line.count("#") > 1:
            first_hash = line.index("#")
            before = line[:first_hash + 1]
            after = line[first_hash + 1:]
            # Remove # before digits like #15036
            after = re.sub(r'#(\d)', r'\1', after)
            # Remove # before jent- with or without space like #jent-15036
            after = re.sub(r'#(jent-)', r'\1', after)
            # Remove # before inte- with or without space like #inte-1059
            after = re.sub(r'#(inte-)', r'\1', after)
            # Now also remove the prefix entirely for subsequent tickets
            # "jent-15036" after first ticket becomes just "15036"
            after = re.sub(r',\s*(jent-\s*|inte-\s*)(\d+)', r', \2', after)
            line = before + after
            
        fixed_lines.append(line)

    return "\n".join(fixed_lines)


# -------------------------------------------------------
# FUNCTION: check_quality
# Checks all required sections are present in output
# -------------------------------------------------------
def check_quality(formatted_text):
    required_sections = [
        "Key Updates",
        "Key Achievements",
        "Challenges Encountered",
        "Team Challenges",
        "Key Tasks Scheduled for Next Week"
    ]
    missing = []
    for section in required_sections:
        if section not in formatted_text:
            missing.append(section)
    if missing:
        print(f"  WARNING — missing sections: {', '.join(missing)}")
        return False
    else:
        print(f"  Quality check passed — all sections present")
        return True


# -------------------------------------------------------
# FUNCTION: save_report
# Saves formatted report to configured output folder
# -------------------------------------------------------
def save_report(formatted_text, filename):
    folder = config["formatted_folder"]
    filepath = f"{folder}/{filename}_report.txt"
    with open(filepath, "w") as f:
        f.write(formatted_text)
    print(f"  Saved to: {filepath}")
    return filepath


# -------------------------------------------------------
# FUNCTION: save_log
# Saves a JSON log of all processed files
# -------------------------------------------------------
def save_log(log_entries):
    log_path = f"{config['formatted_folder']}/processing_log.json"
    with open(log_path, "w") as f:
        json.dump(log_entries, f, indent=2)
    print(f"\nLog saved to: {log_path}")


# -------------------------------------------------------
# FUNCTION: process_all_files
# Main controller — finds all files, sorts numerically,
# skips already formatted ones, validates input,
# asks for missing info, formats, fixes tickets,
# checks quality, saves
# -------------------------------------------------------
def process_all_files():

    team_name = config["team_name"]
    report_date = config["report_date"]
    date_range = config["date_range"]
    raw_folder = config["raw_folder"]
    skip_existing = config["skip_existing"]
    ask_confirmation = config["ask_metadata_confirmation"]

    all_files = sorted(
        [f for f in os.listdir(raw_folder) if f.endswith(".txt")],
        key=sort_key
    )

    if not all_files:
        print("No .txt files found in raw folder.")
        return

    print(f"\nConfiguration:")
    print(f"  API Provider : {config['api_provider'].upper()}")
    print(f"  Model        : {config['model']}")
    print(f"  Team         : {config['team_name']}")
    print(f"  Date         : {config['report_date']}")
    print(f"  Date Range   : {config['date_range']}")
    print(f"  Skip existing: {config['skip_existing']}")
    print()
    print(f"Found {len(all_files)} file(s) to process")
    print("=" * 60)

    log_entries = []
    metadata_confirmed = False

    for filename in all_files:
        file_path = os.path.join(raw_folder, filename)
        file_base = filename.replace(".txt", "")

        print(f"\nProcessing: {filename}")

        # Skip if already formatted
        output_path = f"{config['formatted_folder']}/{file_base}_report.txt"
        if skip_existing and os.path.exists(output_path):
            print(f"  SKIPPED — already formatted")
            log_entries.append({
                "file": filename,
                "status": "skipped",
                "reason": "already formatted",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            continue

        # Read the raw file
        with open(file_path, "r") as f:
            raw_text = f.read()

        # Try to extract dates from top of file
        file_date, file_range = extract_dates_from_file(raw_text)

        # Use file dates if found, otherwise use config/confirmed dates
        current_date = file_date if file_date else report_date
        current_range = file_range if file_range else date_range

        if file_date:
            print(f"  Date found in file: {current_date} ({current_range})")

        # Strip date header from raw text before sending to AI
        raw_text = strip_date_header(raw_text)

        # Validate input
        issues = validate_input(raw_text)

        if issues:
            print(f"  Issues found: {', '.join(issues)}")
            raw_text = ask_user_for_input(issues, raw_text)

            if raw_text.startswith("CONFIRMED:"):
                raw_text = raw_text.replace("CONFIRMED:", "", 1)
                issues_after = []
            else:
                issues_after = validate_input(raw_text)

            if issues_after:
                print(f"  Input still has issues. Skipping {filename}.")
                log_entries.append({
                    "file": filename,
                    "status": "skipped",
                    "reason": f"input issues: {', '.join(issues_after)}",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                continue

        # Ask metadata once per run
        if not metadata_confirmed and ask_confirmation:
            team_name, report_date, date_range = ask_for_metadata(
                team_name, report_date, date_range
            )
            metadata_confirmed = True

        # Format the report
        formatted = format_report(raw_text, team_name, current_date, current_range)

        # Fix ticket ID formatting
        formatted = fix_ticket_ids(formatted)

        # Check quality
        passed = check_quality(formatted)

        if not passed:
            print("  Quality check failed. Options:")
            print("  1. Retry with the same input")
            print("  2. Skip this file")
            print("  Enter 1 or 2: ", end="")
            choice = input().strip()
            if choice == "1":
                print("  Retrying...")
                formatted = format_report(raw_text, team_name, current_date, current_range)
                formatted = fix_ticket_ids(formatted)
                passed = check_quality(formatted)
            else:
                print(f"  Skipping {filename}")
                log_entries.append({
                    "file": filename,
                    "status": "skipped",
                    "reason": "quality check failed, user skipped",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                continue

        # Save the formatted report
        saved_path = save_report(formatted, file_base)

        log_entries.append({
            "file": filename,
            "status": "success" if passed else "warning",
            "quality_check": "passed" if passed else "failed",
            "saved_to": saved_path,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    print("\n" + "=" * 60)
    print(f"Done! Processed {len(all_files)} file(s).")
    save_log(log_entries)


# -------------------------------------------------------
# MAIN PROGRAM
# -------------------------------------------------------
if __name__ == "__main__":
    process_all_files()