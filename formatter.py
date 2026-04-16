import os
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


def format_report(raw_text, team_name, report_date, date_range):

    user_message = f"""
Team: {team_name}
Report Date: {report_date}
Date Range: {date_range}

Raw updates to format:
{raw_text}
"""

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



def save_report(formatted_text, filename):

    filepath = f"data/formatted/{filename}_report.txt"
    with open(filepath, "w") as f:
        f.write(formatted_text)
    print(f"  Saved to: {filepath}")
    return filepath



def save_log(log_entries):

    log_path = "data/formatted/processing_log.json"
    with open(log_path, "w") as f:
        json.dump(log_entries, f, indent=2)
    print(f"\nLog saved to: {log_path}")


def process_all_files(team_name, report_date, date_range):

    raw_folder = "data/raw"
    all_files = [f for f in os.listdir(raw_folder) if f.endswith(".txt")]

    if not all_files:
        print("No .txt files found in data/raw/ folder.")
        return

    print(f"Found {len(all_files)} file(s) to process: {all_files}\n")
    print("=" * 60)

    log_entries = []

    for filename in sorted(all_files):
        file_path = os.path.join(raw_folder, filename)
        file_base = filename.replace(".txt", "")

        print(f"Processing: {filename}")

        with open(file_path, "r") as f:
            raw_text = f.read()

        if not raw_text.strip():
            print(f"  SKIPPED — file is empty\n")
            log_entries.append({
                "file": filename,
                "status": "skipped",
                "reason": "empty file",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            continue

        print(f"  Sending to Groq API...")
        formatted = format_report(raw_text, team_name, report_date, date_range)

        passed = check_quality(formatted)

        saved_path = save_report(formatted, file_base)

        log_entries.append({
            "file": filename,
            "status": "success" if passed else "warning",
            "quality_check": "passed" if passed else "missing sections",
            "saved_to": saved_path,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        print()

    print("=" * 60)
    print(f"Done! Processed {len(all_files)} file(s).")

    save_log(log_entries)



if __name__ == "__main__":

    process_all_files(
        team_name="MMU",
        report_date="Apr 13, 2026",
        date_range="Apr 06 – Apr 10"
    )