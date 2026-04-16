import os
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

GENERATOR_PROMPT = """
You are a software developer writing your weekly update notes.
Write realistic, messy raw engineering notes for a weekly report.

Rules:
- Pick 3-5 random modules from the list provided
- Each module should have 2-5 updates
- Mix different types: fix, enhc, chore, feat, update, bug
- Include realistic ticket IDs like #jent-15202 or #bug-1234
- Some weeks have next week tasks, some don't
- Some weeks have challenges, most don't
- Keep it realistic and varied — not too clean, not too messy
- Never format it as a proper report — keep it raw and informal
- Vary the writing style each time

Output ONLY the raw notes, nothing else. No explanation.
"""


def get_next_week_number():
    """
    Automatically detects the highest existing week number
    in data/raw/ and returns the next one.
    So if week23.txt exists, this returns 24.
    """
    raw_folder = "data/raw"
    existing_weeks = []

    for filename in os.listdir(raw_folder):
        if filename.startswith("week") and filename.endswith(".txt"):
            # Extract the number from filename
            # "week23.txt" → "23" → 23
            try:
                number = int(filename.replace("week", "").replace(".txt", ""))
                existing_weeks.append(number)
            except ValueError:
                # Skip files that don't follow the weekN.txt pattern
                continue

    if not existing_weeks:
        return 1  # No files exist yet, start from week 1

    return max(existing_weeks) + 1  # Start after the highest existing week


def generate_raw_report(week_number, modules_to_use):
    """
    Asks the AI to generate one week of realistic raw notes.
    """
    user_message = f"""
Generate raw weekly engineering notes for week {week_number}.
Use these modules (pick 3-5): {', '.join(modules_to_use)}

Make it realistic — vary the number of updates per module,
include some ticket IDs, and occasionally add challenges
or next week tasks.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": GENERATOR_PROMPT},
            {"role": "user", "content": user_message}
        ],
        max_tokens=800,
        temperature=0.9
    )

    return response.choices[0].message.content


def save_raw_report(content, week_number):
    """
    Saves the generated raw report to data/raw/ folder.
    Never overwrites existing files.
    """
    filepath = f"data/raw/week{week_number}.txt"

    if os.path.exists(filepath):
        print(f"  SKIPPED — {filepath} already exists")
        return False

    with open(filepath, "w") as f:
        f.write(content)

    print(f"  Saved: {filepath}")
    return True


def generate_dataset(how_many=20):
    """
    Automatically detects where to start and generates
    as many new weeks as you specify.
    No hardcoded start number — always continues from
    wherever you left off.
    """

    # Automatically find where to start
    start_from = get_next_week_number()
    end_at = start_from + how_many - 1

    print("=" * 60)
    print("SYNTHETIC DATA GENERATOR")
    print("=" * 60)
    print(f"Existing files detected — starting from week {start_from}")
    print(f"Generating weeks {start_from} to {end_at}")
    print()

    generated = 0

    for week in range(start_from, start_from + how_many):

        print(f"Generating week {week}...")

        # Randomly pick 3-5 modules for variety
        num_modules = random.randint(3, 5)
        modules_to_use = random.sample(MODULES, num_modules)

        # Generate and save
        raw_content = generate_raw_report(week, modules_to_use)
        save_raw_report(raw_content, week)
        generated += 1

    print()
    print("=" * 60)
    print(f"Done! Generated {generated} new files.")
    print(f"Latest file: data/raw/week{end_at}.txt")
    print(f"Total files in data/raw/: {len(os.listdir('data/raw'))}")
    print()
    print("Next steps:")
    print("  python3 formatter.py          <- format all new files")
    print("  python3 dataset_generator.py  <- rebuild training dataset")
    print("=" * 60)


# -------------------------------------------------------
# MAIN PROGRAM
# Change how_many to however many new weeks you want
# -------------------------------------------------------
if __name__ == "__main__":
    generate_dataset(how_many=20)