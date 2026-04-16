import os
import json
import random
from dotenv import load_dotenv

load_dotenv()


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



def load_pairs():
    raw_folder = "data/raw"
    formatted_folder = "data/formatted"

    pairs = []

    for filename in sorted(os.listdir(raw_folder)):
        if not filename.endswith(".txt"):
            continue

        base = filename.replace(".txt", "")
        formatted_filename = f"{base}_report.txt"
        formatted_path = os.path.join(formatted_folder, formatted_filename)
        raw_path = os.path.join(raw_folder, filename)

        if not os.path.exists(formatted_path):
            print(f"  WARNING: No formatted file found for {filename} — skipping")
            continue

        with open(raw_path, "r") as f:
            raw_text = f.read().strip()

        with open(formatted_path, "r") as f:
            formatted_text = f.read().strip()

        if not raw_text or not formatted_text:
            print(f"  WARNING: Empty file detected for {filename} — skipping")
            continue

        pairs.append({
            "raw": raw_text,
            "formatted": formatted_text,
            "source_file": filename
        })
        print(f"  Loaded pair: {filename} → {formatted_filename}")

    return pairs


def convert_to_jsonl(pair):
    return {
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.strip()
            },
            {
                "role": "user",
                "content": pair["raw"]
            },
            {
                "role": "assistant",
                "content": pair["formatted"]
            }
        ]
    }


# -------------------------------------------------------
# FUNCTION 3: split_dataset
# Splits all examples into 80% train and 20% test.
# This is standard practice in machine learning.
# Train = what the model learns from
# Test = what we use to check if learning worked
# -------------------------------------------------------
def split_dataset(examples, train_ratio=0.8):
    # Shuffle randomly so train/test are not biased
    random.seed(42)  # seed means results are reproducible
    shuffled = examples.copy()
    random.shuffle(shuffled)

    # Calculate split point
    split_point = int(len(shuffled) * train_ratio)

    train = shuffled[:split_point]
    test = shuffled[split_point:]

    return train, test


# -------------------------------------------------------
# FUNCTION 4: save_jsonl
# Saves a list of examples to a .jsonl file.
# Each line in the file = one training example.
# -------------------------------------------------------
def save_jsonl(examples, filepath):
    with open(filepath, "w") as f:
        for example in examples:
            # json.dumps converts dict to a single line string
            f.write(json.dumps(example) + "\n")
    print(f"  Saved {len(examples)} examples to: {filepath}")


# -------------------------------------------------------
# FUNCTION 5: validate_jsonl
# Reads the saved JSONL file and checks every line is
# properly formatted. Catches errors before fine tuning.
# -------------------------------------------------------
def validate_jsonl(filepath):
    print(f"\nValidating: {filepath}")
    errors = 0
    total = 0

    with open(filepath, "r") as f:
        for line_number, line in enumerate(f, 1):
            total += 1
            line = line.strip()

            # Check line is not empty
            if not line:
                print(f"  ERROR on line {line_number}: empty line")
                errors += 1
                continue

            # Check line is valid JSON
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print(f"  ERROR on line {line_number}: invalid JSON")
                errors += 1
                continue

            # Check messages key exists
            if "messages" not in obj:
                print(f"  ERROR on line {line_number}: missing 'messages' key")
                errors += 1
                continue

            # Check all 3 roles are present
            roles = [m["role"] for m in obj["messages"]]
            if "system" not in roles:
                print(f"  ERROR on line {line_number}: missing system message")
                errors += 1
            if "user" not in roles:
                print(f"  ERROR on line {line_number}: missing user message")
                errors += 1
            if "assistant" not in roles:
                print(f"  ERROR on line {line_number}: missing assistant message")
                errors += 1

            # Check no empty content
            for message in obj["messages"]:
                if not message.get("content", "").strip():
                    print(f"  ERROR on line {line_number}: empty content in {message['role']} message")
                    errors += 1

    if errors == 0:
        print(f"  Validation passed — {total} examples, 0 errors")
        return True
    else:
        print(f"  Validation failed — {errors} error(s) found in {total} examples")
        return False


# -------------------------------------------------------
# FUNCTION 6: print_sample
# Prints one example from the dataset so you can visually
# verify it looks correct before using it for fine tuning
# -------------------------------------------------------
def print_sample(examples, label):
    if not examples:
        return
    print(f"\n--- Sample from {label} ---")
    sample = examples[0]
    for message in sample["messages"]:
        role = message["role"].upper()
        content = message["content"]
        # Only print first 200 chars to keep output clean
        preview = content[:200] + "..." if len(content) > 200 else content
        print(f"\n[{role}]:\n{preview}")
    print("\n--- End of sample ---")


# -------------------------------------------------------
# MAIN PROGRAM
# -------------------------------------------------------
if __name__ == "__main__":

    print("=" * 60)
    print("DATASET GENERATOR")
    print("=" * 60)

    # Step 1: Load all raw+formatted pairs
    print("\nStep 1: Loading raw and formatted pairs...")
    pairs = load_pairs()

    if not pairs:
        print("\nNo pairs found. Make sure data/raw/ and data/formatted/ have matching files.")
        exit()

    print(f"\nTotal pairs loaded: {len(pairs)}")

    # Step 2: Convert to JSONL format
    print("\nStep 2: Converting to JSONL format...")
    all_examples = [convert_to_jsonl(pair) for pair in pairs]
    print(f"  Converted {len(all_examples)} examples")

    # Step 3: Split into train and test
    print("\nStep 3: Splitting into train and test sets...")
    train_examples, test_examples = split_dataset(all_examples)
    print(f"  Train: {len(train_examples)} examples")
    print(f"  Test:  {len(test_examples)} examples")

    # Step 4: Save to JSONL files
    print("\nStep 4: Saving JSONL files...")
    save_jsonl(train_examples, "data/dataset/train.jsonl")
    save_jsonl(test_examples, "data/dataset/test.jsonl")

    # Step 5: Validate both files
    print("\nStep 5: Validating saved files...")
    validate_jsonl("data/dataset/train.jsonl")
    validate_jsonl("data/dataset/test.jsonl")

    # Step 6: Print a sample so you can visually check
    print("\nStep 6: Printing a sample example...")
    print_sample(train_examples, "train set")

    print("\n" + "=" * 60)
    print("Dataset generation complete!")
    print("Files saved in: data/dataset/")
    print("=" * 60)
