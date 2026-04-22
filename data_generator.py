import os
import re
import json
import random
from dotenv import load_dotenv

load_dotenv()


# -------------------------------------------------------
# CONFIGURATION — reads from config.json
# Same config as formatter.py so both use same model
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
# API CLIENT SETUP — same as formatter.py
# Picks the right API based on config.json
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
# MODULES — realistic module and person names
# The AI will randomly pick from these to create variety
# -------------------------------------------------------
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

PERSON_NAMES = [
    "Arun", "Sumit", "Milind", "Prashant", "Pratik",
    "Rahul", "Amit", "Neha", "Rohit", "Vikram"
]

SUB_SECTIONS = [
    "Bug", "ATS", "Fixes", "Enhancements",
    "Features", "Chores", "API Changes"
]


# -------------------------------------------------------
# GENERATOR PROMPT — asks AI to generate BOTH raw notes
# AND formatted report in one single API call.
# This saves ~40% tokens vs doing it separately.
# Includes all formatting rules from mentor feedback.
# -------------------------------------------------------
GENERATOR_PROMPT = """
You are a software engineering report generator.
Your job is to generate realistic weekly engineering data in JSON format.

Given a list of modules or person names, generate:
1. Raw messy engineering notes (like a developer would write them)
2. A perfectly formatted report from those same notes

Output ONLY valid JSON in this exact structure — nothing else, no markdown, no backticks:

{
  "raw": "the raw messy notes here",
  "formatted": "the clean formatted report here"
}

Rules for raw notes:
- Randomly choose ONE of these two styles:
  STYLE A: Organize by PERSON NAME (like Arun, Sumit, Milind)
            Each person has 2-3 sub-sections (like Bug:, ATS:, Live Interview:)
            Each sub-section has 2-4 items
  STYLE B: Organize by MODULE NAME (like React Interview, Live Interview)
            Each module has 3-5 updates directly underneath
- Mix update types: fix, enhc, chore, feat, update, bug
- Include realistic ticket IDs like inte- 1059, jent- 14954, #14798, #15058
- Some weeks have next week tasks at the bottom, some don't
- Some weeks have challenges, most don't
- Keep it realistic and varied — messy, informal, like real developer notes
- Never make it look like a proper report already

Rules for formatted report:
- Always use this EXACT structure with proper indentation:

MMU, Apr 20, 2026 (Apr 13 - Apr 20)

Key Updates

    {Person or Module Name}
        {SubHeading if exists}:
            - update 1
            - update 2
        {Another SubHeading}:
            - update 1

    {Next Person or Module}
        - update 1
        - update 2

Key Achievements
    - specific achievement 1 mentioning actual feature name
    - specific achievement 2 mentioning actual module name
    - specific achievement 3 mentioning actual fix with detail

Challenges Encountered
    - None

Team Challenges
    - None

Key Tasks Scheduled for Next Week
    - next week task 1
    - next week task 2 or None if no tasks mentioned

CRITICAL formatting rules:
1. SUB-HEADINGS: If person has sub-sections (Bug:, ATS:) they appear as indented labels NOT repeated on every bullet
   CORRECT:
       Arun
           Bug:
               - #inte- 1059, 1067
               - #jent- 14954, 14811
           ATS:
               - Nexus ATS custom field changes
   WRONG:
       Arun
           - Bug: #inte- 1059, 1067
           - ATS: Nexus ATS custom field changes

2. TICKET IDs: # appears only ONCE at start of a ticket list
   CORRECT: - fix: #14798, 15058, 14888
   WRONG:   - fix: #14798, #15058, #14888

3. TICKET PREFIXES: inte- and jent- must have # added
   CORRECT: - #inte- 1059, 1067, 1068
   WRONG:   - inte- 1059, 1067, 1068

4. ACHIEVEMENTS: Always specific, never generic
   CORRECT: - Implemented cron-based scheduling in Auto Job Apply Script
   WRONG:   - Fixed several issues and improved performance

5. PRESERVE CONTENT: Never summarize or rewrite updates
   Keep exact wording from raw notes

6. NO HALLUCINATION: Never add content not in raw notes
"""


# -------------------------------------------------------
# FUNCTION: get_next_week_number
# Automatically detects highest existing week number
# and returns the next one to continue from
# -------------------------------------------------------
def get_next_week_number():
    raw_folder = config["raw_folder"]
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
# formatted report together as JSON.
# Saves ~40% tokens vs calling twice separately.
# -------------------------------------------------------
def generate_pair(week_number, use_persons=False):

    if use_persons:
        # Person-grouped style — pick 3-5 random person names
        num_people = random.randint(3, 5)
        names = random.sample(PERSON_NAMES, num_people)
        user_message = f"""
Generate weekly engineering data for week {week_number}.
Use STYLE A — organize by PERSON NAME.
People this week: {', '.join(names)}
Each person should have 2-3 sub-sections with realistic updates.
Include ticket IDs like inte- 1059, jent- 14954, #14798 etc.
Remember to output only valid JSON.
"""
    else:
        # Module-grouped style — pick 3-5 random modules
        num_modules = random.randint(3, 5)
        modules = random.sample(MODULES, num_modules)
        user_message = f"""
Generate weekly engineering data for week {week_number}.
Use STYLE B — organize by MODULE NAME.
Modules this week: {', '.join(modules)}
Each module should have 3-5 updates directly underneath.
Include ticket IDs like #14798, #15058, jent-15038 etc.
Remember to output only valid JSON.
"""

    if provider in ["groq", "openai"]:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": GENERATOR_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1500,
            temperature=0.9
        )
        raw_response = response.choices[0].message.content.strip()

    elif provider == "gemini":
        from google.genai import types
        response = client.models.generate_content(
            model=config["model"],
            contents=GENERATOR_PROMPT + "\n\n" + user_message,
            config=types.GenerateContentConfig(
                max_output_tokens=1500,
                temperature=0.9
            )
        )
        raw_response = response.text.strip()

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
# Never overwrites existing files
# -------------------------------------------------------
def save_pair(raw_content, formatted_content, week_number):

    raw_folder = config["raw_folder"]
    formatted_folder = config["formatted_folder"]

    raw_path = f"{raw_folder}/week{week_number}.txt"
    formatted_path = f"{formatted_folder}/week{week_number}_report.txt"

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
# automatically continuing from where you left off.
# Alternates between person-grouped and module-grouped
# styles for variety in the training data.
# -------------------------------------------------------
def generate_dataset(how_many=27):

    start_from = get_next_week_number()
    end_at = start_from + how_many - 1

    print("=" * 60)
    print("SMART DATASET GENERATOR (raw + formatted in one call)")
    print("=" * 60)
    print(f"API Provider  : {config['api_provider'].upper()}")
    print(f"Model         : {config['model']}")
    print(f"Starting from : week {start_from}")
    print(f"Generating    : weeks {start_from} to {end_at}")
    print(f"Est. tokens   : ~{how_many * 1500:,}")
    print()

    generated = 0
    failed = 0

    for week in range(start_from, start_from + how_many):

        # Alternate between person-grouped and module-grouped
        # for variety — odd weeks use persons, even use modules
        use_persons = (week % 2 == 0)
        style = "person-grouped" if use_persons else "module-grouped"

        print(f"Generating week {week} ({style})...")

        try:
            raw_content, formatted_content = generate_pair(
                week, use_persons=use_persons
            )
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
    print(f"Generated : {generated} pairs")
    print(f"Failed    : {failed}")
    print()

    raw_count = len([
        f for f in os.listdir(config["raw_folder"])
        if f.startswith("week") and f.endswith(".txt")
    ])
    formatted_count = len([
        f for f in os.listdir(config["formatted_folder"])
        if f.endswith("_report.txt")
    ])

    print(f"Total raw files       : {raw_count}")
    print(f"Total formatted files : {formatted_count}")
    print()
    print("Next step:")
    print("  python3 dataset_generator.py  <- rebuild training dataset")
    print("=" * 60)


# -------------------------------------------------------
# MAIN PROGRAM
# Change how_many to however many new weeks you want
# -------------------------------------------------------
if __name__ == "__main__":
    generate_dataset(how_many=1)