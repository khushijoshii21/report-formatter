# Report Formatter — AI Weekly Report Generator

## What this project does
This project takes raw, messy weekly engineering update notes and automatically
converts them into a clean, structured report using AI.

You drop your raw notes into a folder, run one command, and get back a perfectly
formatted report — every time, in the same structure.

## How it works
1. Raw notes are placed in data/raw/ as .txt files
2. The program sends them to Groq's AI (LLaMA 3.3 70B model) with strict formatting instructions
3. The AI returns a clean structured report
4. The report is saved to data/formatted/
5. A quality check verifies all required sections are present
6. A log file records every run with timestamps

## Tech stack
- Language: Python 3.12
- AI Model: LLaMA 3.3 70B (by Meta, via Groq API)
- API Provider: Groq (free)
- Key storage: python-dotenv

## Project structure

    report-formatter/
      ├── .env                        <- API key (never share this)
      ├── formatter.py                <- main program
      ├── dataset_generator.py        <- builds training dataset
      ├── data/
      │   ├── raw/                    <- put raw notes here
      │   ├── formatted/              <- formatted reports saved here
      │   └── dataset/                <- JSONL training data
      └── README.md

## How to run

Step 1 — Activate virtual environment

    source venv/bin/activate

Step 2 — Format all reports

    python3 formatter.py

Step 3 — Generate training dataset

    python3 dataset_generator.py

## Output format

Every report follows this exact structure:

    TEAM, DATE (DATE_RANGE)

    Key Updates
        Module Name
            - update 1
            - update 2

    Key Achievements
        - main wins

    Challenges Encountered
        - blockers or None

    Team Challenges
        - team challenges or None

    Key Tasks Scheduled for Next Week
        - next week tasks or None

## Training dataset

The dataset_generator.py script automatically:
- Pairs each raw input file with its formatted output
- Converts them into JSONL format (required for fine tuning)
- Splits them 80% train / 20% test
- Validates every line for errors

This dataset can be used to fine tune a smaller dedicated model
using OpenAI fine tuning API or Hugging Face.

## What is prompt engineering

Instead of training a model from scratch, this project uses a carefully
written system prompt that instructs the AI exactly how to format the report.
This approach works immediately with no training data needed and produces
consistent high quality output.

## What is fine tuning

Fine tuning means taking an existing AI model and training it further on your
specific examples so it learns your exact task. The JSONL dataset built by
this project is the first step toward fine tuning a smaller dedicated model.

## APIs used

Groq API — free AI API that gives access to the LLaMA 3.3 70B model.
The project is API agnostic meaning it can be switched to OpenAI or
any other provider by changing just a few lines of code.

## Next steps
- Collect more weekly examples to grow the dataset
- Fine tune a smaller model using the JSONL dataset
- Build a simple web interface for non-technical users

## Recent Updates

### Configurable System
The project is now fully configurable via config.json.
Change model, API provider, team name, dates, and folder 
paths without touching any code.

### Improved Formatting
The system prompt now handles:
- Person-grouped reports (Arun, Sumit, Milind)
- Module-grouped reports (React Interview, Live Interview)
- Sub-headings as proper indented labels
- Ticket IDs with # appearing only once
- Automatic # added before inte- and jent- prefixes
- No hallucinated content between sections

### Edge Case Handling
- Empty files — asks user to type notes
- Too short input — asks user to add more details
- Gibberish input — asks user to confirm or retype
- Missing module names — asks user to provide them

### Supported API Providers
- Groq (free, default)
- OpenAI
- Gemini

## FastAPI Service

The project can also run as an API service.

### Start the API server
source venv/bin/activate
uvicorn api:app --reload

### API runs at
http://127.0.0.1:8000

### Interactive documentation
http://127.0.0.1:8000/docs

### Endpoints

GET  /         — Welcome message
GET  /health   — Health check
GET  /config   — Current configuration
POST /format-report       — Format a single report
POST /format-report/batch — Format multiple reports

### Example request
POST /format-report
{
  "raw_text": "your raw notes here",
  "team_name": "MMU",
  "report_date": "Apr 23, 2026",
  "date_range": "Apr 13 - Apr 20"
}

### Example response
{
  "formatted_report": "MMU, Apr 23, 2026...",
  "quality_check": true,
  "missing_sections": [],
  "model_used": "llama-3.3-70b-versatile",
  "api_provider": "groq"
}
