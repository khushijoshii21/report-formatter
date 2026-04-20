import os
import re
import json
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are a weekly engineering report formatter.
Your job is to take raw development notes and convert them into a clean, structured weekly report.

Always output in EXACTLY this format — never skip any section:

{TEAM}, {DATE} ({DATE_RANGE})

Key Updates

    {Module Name}
        - {update 1}
        - {update 2}

    {Another Module}
        - {update}

Key Achievements
    - {summarize the main wins in 2-3 points}

Challenges Encountered
    - {any blockers mentioned, or write: None}

Team Challenges
    - {team-level challenges, or write: None}

Key Tasks Scheduled for Next Week
    - {extract all next week tasks from the input, or write: None}

Rules you must follow:
- Group all updates under their module/project name
- Keep ticket IDs exactly as they are (like #jent-15202)
- If no challenges are mentioned, write None
- If no next week tasks are mentioned, write None
- Extract next week items into the last section
- Use clean indentation as shown above
- Never add extra commentary or explanation outside the format
"""


# -------------------------------------------------------
# SORTING — sorts files in proper numerical order
# week1, week2, week3... instead of week1, week10, week11
# -------------------------------------------------------
def sort_key(filename):
    numbers = re.findall(r'\d+', filename)
    return (int(numbers[0]) if numbers else 0, filename)


# -------------------------------------------------------
# EDGE CASE 1: Check if input is too short to be valid
# -------------------------------------------------------
def is_too_short(text):
    words = text.split()
    return len(words) < 10


# -------------------------------------------------------
# EDGE CASE 2: Check if input has any recognizable
# module or project names
# -------------------------------------------------------
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


# -------------------------------------------------------
# EDGE CASE 3: Check if input looks like gibberish
# -------------------------------------------------------
def looks_like_gibberish(text):
    letters = sum(c.isalpha() for c in text)
    total = len(text.replace(" ", "").replace("\n", ""))
    if total == 0:
        return True
    return (letters / total) < 0.6


# -------------------------------------------------------
# EDGE CASE 4: Check if ticket IDs are present
# -------------------------------------------------------
def has_ticket_ids(text):
    pattern = r'#[a-zA-Z]+-\d+'
    return bool(re.search(pattern, text))


# -------------------------------------------------------
# FUNCTION: validate_input
# Runs all edge case checks and returns list of issues
# -------------------------------------------------------
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
# When something is missing or unclear, asks the user
# to provide the missing information interactively
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
            # User confirmed it is valid — return as is and bypass re-validation
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
# Always asks user to confirm team name, date, date range
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
# Sends validated raw notes to Groq AI and returns
# the formatted report
# -------------------------------------------------------
def format_report(raw_text, team_name, report_date, date_range):
    user_message = f"""
Team: {team_name}
Report Date: {report_date}
Date Range: {date_range}

Raw updates to format:
{raw_text}
"""

    print("\n  Sending to Groq API... please wait.")

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        max_tokens=2000,
        temperature=0.3
    )
    return response.choices[0].message.content


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
# Saves formatted report to data/formatted/ folder
# -------------------------------------------------------
def save_report(formatted_text, filename):
    filepath = f"data/formatted/{filename}_report.txt"
    with open(filepath, "w") as f:
        f.write(formatted_text)
    print(f"  Saved to: {filepath}")
    return filepath


# -------------------------------------------------------
# FUNCTION: save_log
# Saves a JSON log of all processed files
# -------------------------------------------------------
def save_log(log_entries):
    log_path = "data/formatted/processing_log.json"
    with open(log_path, "w") as f:
        json.dump(log_entries, f, indent=2)
    print(f"\nLog saved to: {log_path}")


# -------------------------------------------------------
# FUNCTION: process_all_files
# Main controller — finds all files, sorts numerically,
# skips already formatted ones, validates input,
# asks for missing info, formats, checks quality, saves
# -------------------------------------------------------
def process_all_files(team_name, report_date, date_range):

    raw_folder = "data/raw"

    # Sort files numerically — week1, week2, week3...
    all_files = sorted(
        [f for f in os.listdir(raw_folder) if f.endswith(".txt")],
        key=sort_key
    )

    if not all_files:
        print("No .txt files found in data/raw/ folder.")
        return

    print(f"Found {len(all_files)} file(s) to process: {all_files}\n")
    print("=" * 60)

    log_entries = []
    metadata_confirmed = False

    for filename in all_files:
        file_path = os.path.join(raw_folder, filename)
        file_base = filename.replace(".txt", "")

        print(f"\nProcessing: {filename}")

        # Skip if already formatted — saves API tokens
        output_path = f"data/formatted/{file_base}_report.txt"
        if os.path.exists(output_path):
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

        # Validate the input before sending to AI
        issues = validate_input(raw_text)

        if issues:
            print(f"  Issues found: {', '.join(issues)}")
            raw_text = ask_user_for_input(issues, raw_text)

           # Skip re-validation if user explicitly confirmed the input
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

        # Ask user to confirm metadata only once per run
        if not metadata_confirmed:
            team_name, report_date, date_range = ask_for_metadata(
                team_name, report_date, date_range
            )
            metadata_confirmed = True

        # Send to AI and get formatted report
        formatted = format_report(raw_text, team_name, report_date, date_range)

        # Check quality
        passed = check_quality(formatted)

        # If quality check failed ask user what to do
        if not passed:
            print("  Quality check failed. Options:")
            print("  1. Retry with the same input")
            print("  2. Skip this file")
            print("  Enter 1 or 2: ", end="")
            choice = input().strip()
            if choice == "1":
                print("  Retrying...")
                formatted = format_report(raw_text, team_name, report_date, date_range)
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
    process_all_files(
        team_name="MMU",
        report_date="Apr 20, 2026",
        date_range="Apr 13 – Apr 20"
    )