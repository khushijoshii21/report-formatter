import os
import re
import json
import random
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODULES = [
    "React Interview",
    "Live Interview",
    "Integration",
    "Interview API",
    "Candidate Recommendation",
    "Jobma Bot",
    "Auto Job Apply Script",
    "Mobile App",
    "Admin Dashboard",
    "Payment Gateway",
    "Notification Service",
    "Authentication",
    "Search Engine",
    "Analytics Dashboard",
    "Email Service"
]

# -------------------------------------------------------
# This prompt asks the AI to generate BOTH raw notes
# AND the formatted report in one single API call.
# This saves ~40% of tokens compared to doing it separately.
# The output is structured JSON so we can easily split
# the raw and formatted parts.
# -------------------------------------------------------
GENERATOR_PROMPT = """
You are a software engineering report generator.
Your job is to generate realistic weekly engineering data in JSON format.

Given a list of modules, generate:
1. Raw messy engineering notes (like a developer would write them)
2. A clean formatted report from those same notes

Output ONLY valid JSON in this exact structure — nothing else:

{
  "raw": "the raw messy notes here",
  "formatted": "the clean formatted report here"
}

Rules for raw notes:
- Pick 3-5 modules from the list provided
- Each module should have 2-5 updates
- Mix types: fix, enhc, chore, feat, update, bug
- Include realistic ticket IDs like #jent-15202
- Some weeks have next week tasks, some don't
- Keep it realistic and varied — messy, informal
- Never make it look like a proper report

Rules for formatted report:
- Always use this exact structure:

MMU, {DATE} ({DATE_RANGE})

Key Updates

    {Module Name}
        - {update 1}
        - {update 2}

Key Achievements
    - {2-3 main wins}

Challenges Encountered
    - None

Team Challenges
    - None

Key Tasks Scheduled for Next Week
    - {next week tasks or None}

- Group updates by module
- Keep all ticket IDs exactly as they appear in raw notes
- If no challenges mentioned write None
- If no next week tasks write None
"""


# -------------------------------------------------------
# FUNCTION: get_next_week_number
# Automatically detects highest existing week number
# and returns the next one to continue from
# -------------------------------------------------------
def get_next_week_number():
    raw_folder = "data/raw"
    existing_weeks = []

    for filename in os.listdir(raw_folder):
        if filename.startswith("week") and filename.endswith(".txt"):
            try:
                number = int(filename.replace("week", "").replace(".txt", ""))
                existing_weeks.append(number)
            except ValueError:
                continue

    if not existing_weeks:
        return 1

    return max(existing_weeks) + 1


# -------------------------------------------------------
# FUNCTION: generate_pair
# Calls the AI ONCE and gets back both raw notes AND
# formatted report together. Saves ~40% tokens vs
# calling twice separately.
# -------------------------------------------------------
def generate_pair(week_number, modules_to_use):

    user_message = f"""
Generate weekly engineering data for week {week_number}.
Use these modules (pick 3-5): {', '.join(modules_to_use)}

Remember:
- Raw notes should be messy and informal
- Formatted report must follow the exact structure
- Output only valid JSON, nothing else
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": GENERATOR_PROMPT},
            {"role": "user", "content": user_message}
        ],
        max_tokens=1500,
        temperature=0.9
    )

    raw_response = response.choices[0].message.content.strip()

    # Clean up response — remove markdown code blocks if present
    raw_response = re.sub(r'```json\s*', '', raw_response)
    raw_response = re.sub(r'```\s*', '', raw_response)
    raw_response = raw_response.strip()

    # Parse the JSON response
    data = json.loads(raw_response)

    return data["raw"], data["formatted"]


# -------------------------------------------------------
# FUNCTION: save_pair
# Saves both raw and formatted files together
# -------------------------------------------------------
def save_pair(raw_content, formatted_content, week_number):

    raw_path = f"data/raw/week{week_number}.txt"
    formatted_path = f"data/formatted/week{week_number}_report.txt"

    # Never overwrite existing files
    if os.path.exists(raw_path) or os.path.exists(formatted_path):
        print(f"  SKIPPED — week{week_number} already exists")
        return False

    with open(raw_path, "w") as f:
        f.write(raw_content)

    with open(formatted_path, "w") as f:
        f.write(formatted_content)

    print(f"  Saved: week{week_number}.txt + week{week_number}_report.txt")
    return True


# -------------------------------------------------------
# FUNCTION: generate_dataset
# Main controller — generates how_many new week pairs
# automatically continuing from where you left off
# -------------------------------------------------------
def generate_dataset(how_many=27):

    start_from = get_next_week_number()
    end_at = start_from + how_many - 1

    print("=" * 60)
    print("SMART DATASET GENERATOR (raw + formatted in one call)")
    print("=" * 60)
    print(f"Existing files detected — starting from week {start_from}")
    print(f"Generating weeks {start_from} to {end_at}")
    print(f"Estimated tokens: ~{how_many * 1500:,} (saved 40% vs old method)")
    print()

    generated = 0
    failed = 0

    for week in range(start_from, start_from + how_many):

        print(f"Generating week {week}...")

        # Randomly pick 3-5 modules for variety
        num_modules = random.randint(3, 5)
        modules_to_use = random.sample(MODULES, num_modules)

        try:
            # One API call generates both raw and formatted
            raw_content, formatted_content = generate_pair(week, modules_to_use)

            # Save both files
            saved = save_pair(raw_content, formatted_content, week)
            if saved:
                generated += 1

        except json.JSONDecodeError as e:
            print(f"  ERROR — could not parse JSON for week {week}: {e}")
            failed += 1
            continue

        except Exception as e:
            print(f"  ERROR — week {week} failed: {e}")
            failed += 1
            continue

    print()
    print("=" * 60)
    print(f"Done!")
    print(f"Generated: {generated} pairs")
    print(f"Failed: {failed}")
    print(f"Latest file: data/raw/week{end_at}.txt")
    print()

    # Count total files
    raw_count = len([f for f in os.listdir("data/raw")
                     if f.startswith("week") and f.endswith(".txt")])
    formatted_count = len([f for f in os.listdir("data/formatted")
                           if f.endswith("_report.txt")])

    print(f"Total raw files: {raw_count}")
    print(f"Total formatted files: {formatted_count}")
    print()
    print("Next step:")
    print("  python3 dataset_generator.py  <- rebuild training dataset")
    print("=" * 60)


# -------------------------------------------------------
# MAIN PROGRAM
# Change how_many to however many new weeks you want
# -------------------------------------------------------
if __name__ == "__main__":
    generate_dataset(how_many=50)