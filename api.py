import os
import re
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

load_dotenv()


# -------------------------------------------------------
# CONFIGURATION — reads from config.json
# -------------------------------------------------------
def load_config():
    config_path = "config.json"
    if not os.path.exists(config_path):
        raise Exception("config.json not found")
    with open(config_path, "r") as f:
        return json.load(f)

config = load_config()


# -------------------------------------------------------
# API CLIENT SETUP — same as formatter.py
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
        raise Exception(f"Unknown API provider: {provider}")

client, provider = setup_client()


# -------------------------------------------------------
# SYSTEM PROMPT — same as formatter.py
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
- If the input is organized by PERSON NAME keep it grouped by person name
- If the input is organized by MODULE NAME keep it grouped by module name
- Never change the grouping structure that already exists in the input

RULE 2 — BULLET POINTS:
- Every single update must be on its own separate line with a dash (-)
- Never merge multiple updates into one long line
- Each fix, feat, enhc, chore, update must be its own separate bullet point

RULE 3 — TICKET IDs:
- Keep ticket IDs exactly as they appear in the raw input
- Never add extra # symbols
- Never repeat # if it already appears once in a list

RULE 4 — ALREADY FORMATTED INPUT:
- If the input already looks mostly formatted, do minimal changes
- Only fix indentation, add missing dashes, and ensure all 5 sections exist

RULE 5 — EMPTY SECTIONS:
- If a module has no updates or just a dash (-) keep it as is
- Never delete modules even if they appear empty

RULE 6 — PRESERVE CONTENT:
- Never summarize or shorten any update
- Keep exact wording from the input

RULE 7 — ACHIEVEMENTS:
- Write exactly 3 specific achievement points
- Each must mention actual module names and features
- NEVER write generic statements like "Fixed several issues"

RULE 8 — SUB-HEADINGS INSIDE PERSON SECTIONS:
- Sub-headings appear as their OWN indented heading — NOT repeated on every bullet
- Format:
    PersonName
        SubHeading:
            - update 1
            - update 2

RULE 9 — NO HALLUCINATION OR COMMENTARY:
- Never add content not in raw input
- Never copy updates between wrong sections
- Output only what is in the raw input
"""


# -------------------------------------------------------
# FASTAPI APP
# -------------------------------------------------------
app = FastAPI(
    title="Report Formatter API",
    description="Converts raw weekly engineering notes into structured reports",
    version="1.0.0"
)

# Allow requests from any origin (needed for web clients)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# -------------------------------------------------------
# REQUEST AND RESPONSE MODELS
# These define what the API accepts and returns
# -------------------------------------------------------
class FormatRequest(BaseModel):
    raw_text: str
    team_name: Optional[str] = None
    report_date: Optional[str] = None
    date_range: Optional[str] = None

class FormatResponse(BaseModel):
    formatted_report: str
    team_name: str
    report_date: str
    date_range: str
    model_used: str
    api_provider: str
    quality_check: bool
    missing_sections: list


# -------------------------------------------------------
# HELPER: fix_ticket_ids — same as formatter.py
# -------------------------------------------------------
def fix_ticket_ids(text):
    lines = text.split("\n")
    fixed_lines = []
    for line in lines:
        line = re.sub(r'(?<!#)(jent-\s*|inte-\s*)(\d+)', r'#\1\2', line)
        line = re.sub(r'(fix:|bug:|enhc:|update:|feat:)\s+(\d+)', r'\1 #\2', line)
        if line.count("#") > 1:
            first_hash = line.index("#")
            before = line[:first_hash + 1]
            after = line[first_hash + 1:]
            after = re.sub(r'#(\d)', r'\1', after)
            after = re.sub(r'#(jent-)', r'\1', after)
            after = re.sub(r'#(inte-)', r'\1', after)
            after = re.sub(r',\s*(jent-\s*|inte-\s*)(\d+)', r', \2', after)
            line = before + after
        fixed_lines.append(line)
    return "\n".join(fixed_lines)


# -------------------------------------------------------
# HELPER: check_quality — same as formatter.py
# -------------------------------------------------------
def check_quality(formatted_text):
    required_sections = [
        "Key Updates",
        "Key Achievements",
        "Challenges Encountered",
        "Team Challenges",
        "Key Tasks Scheduled for Next Week"
    ]
    missing = [s for s in required_sections if s not in formatted_text]
    return len(missing) == 0, missing


# -------------------------------------------------------
# HELPER: call_ai — sends text to configured AI
# -------------------------------------------------------
def call_ai(raw_text, team_name, report_date, date_range):
    user_message = f"""
Team: {team_name}
Report Date: {report_date}
Date Range: {date_range}

Raw updates to format:
{raw_text}
"""
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
# ROUTE 1: GET /
# Simple welcome message to confirm API is running
# -------------------------------------------------------
@app.get("/")
def root():
    return {
        "message": "Report Formatter API is running",
        "version": "1.0.0",
        "endpoints": {
            "format_report": "POST /format-report",
            "health": "GET /health",
            "config": "GET /config",
            "docs": "GET /docs"
        }
    }


# -------------------------------------------------------
# ROUTE 2: GET /health
# Health check — tells you if API is working
# -------------------------------------------------------
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "api_provider": config["api_provider"],
        "model": config["model"],
        "team": config["team_name"]
    }


# -------------------------------------------------------
# ROUTE 3: GET /config
# Returns current configuration (without API keys)
# -------------------------------------------------------
@app.get("/config")
def get_config():
    return {
        "api_provider": config["api_provider"],
        "model": config["model"],
        "team_name": config["team_name"],
        "report_date": config["report_date"],
        "date_range": config["date_range"],
        "max_tokens": config["max_tokens"],
        "temperature": config["temperature"]
    }


# -------------------------------------------------------
# ROUTE 4: POST /format-report
# Main endpoint — takes raw notes and returns formatted report
# This is the core of the entire API
# -------------------------------------------------------
@app.post("/format-report", response_model=FormatResponse)
def format_report(request: FormatRequest):

    # Validate input is not empty
    if not request.raw_text or not request.raw_text.strip():
        raise HTTPException(
            status_code=400,
            detail="raw_text cannot be empty"
        )

    # Validate input is not too short
    if len(request.raw_text.split()) < 5:
        raise HTTPException(
            status_code=400,
            detail="raw_text is too short — please provide more details"
        )

    # Use values from request if provided, otherwise fall back to config
    team_name = request.team_name or config["team_name"]
    report_date = request.report_date or config["report_date"]
    date_range = request.date_range or config["date_range"]

    try:
        # Call AI to format the report
        formatted = call_ai(request.raw_text, team_name, report_date, date_range)

        # Fix ticket ID formatting
        formatted = fix_ticket_ids(formatted)

        # Check quality
        passed, missing = check_quality(formatted)

        return FormatResponse(
            formatted_report=formatted,
            team_name=team_name,
            report_date=report_date,
            date_range=date_range,
            model_used=config["model"],
            api_provider=config["api_provider"],
            quality_check=passed,
            missing_sections=missing
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error formatting report: {str(e)}"
        )


# -------------------------------------------------------
# ROUTE 5: POST /format-report/batch
# Formats multiple reports at once
# Send a list of raw texts and get back all formatted
# -------------------------------------------------------
class BatchRequest(BaseModel):
    reports: list
    team_name: Optional[str] = None
    report_date: Optional[str] = None
    date_range: Optional[str] = None

@app.post("/format-report/batch")
def format_batch(request: BatchRequest):

    if not request.reports:
        raise HTTPException(
            status_code=400,
            detail="reports list cannot be empty"
        )

    if len(request.reports) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 reports per batch request"
        )

    team_name = request.team_name or config["team_name"]
    report_date = request.report_date or config["report_date"]
    date_range = request.date_range or config["date_range"]

    results = []

    for i, raw_text in enumerate(request.reports):
        try:
            formatted = call_ai(raw_text, team_name, report_date, date_range)
            formatted = fix_ticket_ids(formatted)
            passed, missing = check_quality(formatted)

            results.append({
                "index": i,
                "status": "success",
                "formatted_report": formatted,
                "quality_check": passed,
                "missing_sections": missing
            })

        except Exception as e:
            results.append({
                "index": i,
                "status": "error",
                "error": str(e)
            })

    return {
        "total": len(request.reports),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results
    }
