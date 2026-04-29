import os
import re
import json
import time
import logging
import io
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

load_dotenv()


# -------------------------------------------------------
# LOGGING SETUP
# -------------------------------------------------------
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/api.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------
def load_config():
    config_path = "config.json"
    if not os.path.exists(config_path):
        raise Exception("config.json not found")
    with open(config_path, "r") as f:
        return json.load(f)

config = load_config()


# -------------------------------------------------------
# API CLIENT SETUP
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
# RATE LIMITING
# -------------------------------------------------------
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)


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

app.state.limiter = limiter
# Serve static files (CSS, JS) from /static folder
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# -------------------------------------------------------
# REQUEST LOGGING MIDDLEWARE
# -------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"REQUEST  | {request.method} {request.url.path}")
    response = await call_next(request)
    duration = round((time.time() - start_time) * 1000, 2)
    logger.info(
        f"RESPONSE | {request.method} {request.url.path} "
        f"| Status: {response.status_code} "
        f"| Time: {duration}ms"
    )
    return response


# -------------------------------------------------------
# REQUEST AND RESPONSE MODELS
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

class BatchRequest(BaseModel):
    reports: list
    team_name: Optional[str] = None
    report_date: Optional[str] = None
    date_range: Optional[str] = None

class QueryRequest(BaseModel):
    question: str
    max_reports: Optional[int] = 10


# -------------------------------------------------------
# EDGE CASE DETECTION
# -------------------------------------------------------
def is_empty(text):
    return not text or not text.strip()

def is_gibberish(text):
    letters = sum(c.isalpha() for c in text)
    total = len(text.replace(" ", "").replace("\n", ""))
    if total == 0:
        return True
    return (letters / total) < 0.6

def is_too_short(text):
    words = text.split()
    return len(words) < 5

def has_no_modules(text):
    common_keywords = [
        "interview", "integration", "api", "bot", "script",
        "dashboard", "app", "service", "fix", "feat", "enhc",
        "chore", "update", "bug", "frontend", "backend", "mobile",
        "react", "live", "candidate", "jobma", "auto", "admin",
        "payment", "notification", "auth", "search", "analytics",
        "email", "jent", "#"
    ]
    text_lower = text.lower()
    matches = sum(1 for keyword in common_keywords if keyword in text_lower)
    return matches < 2

def validate_input(text):
    if is_empty(text):
        return "Input is empty — please paste your raw notes."
    if is_gibberish(text):
        return "Input appears to contain mostly symbols or special characters. Please paste proper engineering notes."
    if is_too_short(text):
        return "Input is too short — please provide more details about what was done this week."
    if has_no_modules(text):
        return "Could not detect any module or project names in your notes. Please make sure your input contains proper engineering updates."
    return None


# -------------------------------------------------------
# HELPER: fix_ticket_ids
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
# HELPER: check_quality
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
# HELPER: call_ai
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
# REPORT HISTORY
# -------------------------------------------------------
HISTORY_FILE = "data/report_history.json"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)

def save_to_history(raw_text, formatted_report, team_name, report_date, date_range, quality_check):
    history = load_history()
    entry = {
        "id": len(history) + 1,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "team_name": team_name,
        "report_date": report_date,
        "date_range": date_range,
        "quality_check": quality_check,
        "raw_input_length": len(raw_text.split()),
        "formatted_report": formatted_report
    }
    history.append(entry)
    os.makedirs("data", exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    logger.info(f"HISTORY  | Saved report #{entry['id']} for {team_name}")
    return entry["id"]


# -------------------------------------------------------
# PDF GENERATION
# -------------------------------------------------------
def generate_pdf(formatted_report: str) -> io.BytesIO:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib import colors

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25*mm,
        leftMargin=25*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )

    MAIN_SECTIONS = [
        "Key Updates",
        "Key Achievements",
        "Challenges Encountered",
        "Team Challenges",
        "Key Tasks Scheduled for Next Week"
    ]

    header_style = ParagraphStyle(
        'Header',
        fontSize=13,
        fontName='Helvetica-Bold',
        spaceAfter=10,
        spaceBefore=0,
        textColor=colors.HexColor('#111111')
    )
    section_style = ParagraphStyle(
        'Section',
        fontSize=12,
        fontName='Helvetica-Bold',
        spaceBefore=16,
        spaceAfter=6,
        textColor=colors.HexColor('#111111')
    )
    module_style = ParagraphStyle(
        'Module',
        fontSize=11,
        fontName='Helvetica-Bold',
        leftIndent=12,
        spaceBefore=10,
        spaceAfter=3,
        textColor=colors.HexColor('#1a1a1a')
    )
    subheading_style = ParagraphStyle(
        'SubHeading',
        fontSize=10,
        fontName='Helvetica-BoldOblique',
        leftIndent=24,
        spaceBefore=4,
        spaceAfter=1,
        textColor=colors.HexColor('#374151')
    )
    bullet_style = ParagraphStyle(
        'Bullet',
        fontSize=9.5,
        fontName='Helvetica',
        leftIndent=32,
        firstLineIndent=-10,
        spaceAfter=3,
        textColor=colors.HexColor('#374151'),
        leading=15
    )
    deep_bullet_style = ParagraphStyle(
        'DeepBullet',
        fontSize=9.5,
        fontName='Helvetica',
        leftIndent=48,
        firstLineIndent=-10,
        spaceAfter=3,
        textColor=colors.HexColor('#374151'),
        leading=15
    )

    story = []
    lines = formatted_report.split("\n")

    for line in lines:
        if not line.strip():
            story.append(Spacer(1, 3))
            continue

        spaces = len(line) - len(line.lstrip())
        content = line.strip()

        content = (content
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        is_bullet = content.startswith("-")
        is_main_section = any(content == s or content.startswith(s) for s in MAIN_SECTIONS)

        if spaces == 0 and is_main_section:
            story.append(Spacer(1, 6))
            story.append(Paragraph(content, section_style))
        elif spaces == 0 and not is_bullet:
            story.append(Paragraph(content, header_style))
            story.append(Spacer(1, 4))
        elif 1 <= spaces <= 4 and not is_bullet:
            story.append(Paragraph(content, module_style))
        elif 5 <= spaces <= 8 and not is_bullet:
            story.append(Paragraph(content, subheading_style))
        elif is_bullet and spaces <= 8:
            text = content[1:].strip()
            story.append(Paragraph(f"&#8226; {text}", bullet_style))
        elif is_bullet and spaces > 8:
            text = content[1:].strip()
            story.append(Paragraph(f"&#8226; {text}", deep_bullet_style))
        else:
            story.append(Paragraph(content, bullet_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


# -------------------------------------------------------
# ROUTES
# -------------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Report Formatter API is running",
        "version": "1.0.0",
        "endpoints": {
            "ui": "GET /ui",
            "format_report": "POST /format-report",
            "batch": "POST /format-report/batch",
            "upload": "POST /upload-and-format",
            "download_pdf": "POST /download-pdf",
            "query": "POST /query",
            "history": "GET /history",
            "logs": "GET /logs",
            "health": "GET /health",
            "config": "GET /config",
            "reload_config": "POST /reload-config",
            "docs": "GET /docs"
        }
    }


@app.get("/ui", response_class=HTMLResponse)
def ui():
    with open("templates/index.html", "r") as f:
        return f.read()


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "api_provider": config["api_provider"],
        "model": config["model"],
        "team": config["team_name"]
    }


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


@app.post("/reload-config")
def reload_config():
    global config, client, provider
    try:
        config = load_config()
        client, provider = setup_client()
        return {
            "message": "Configuration reloaded successfully",
            "api_provider": config["api_provider"],
            "model": config["model"],
            "team_name": config["team_name"],
            "report_date": config["report_date"],
            "date_range": config["date_range"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {str(e)}")


@app.get("/logs")
def get_logs(lines: int = 50):
    log_path = "logs/api.log"
    if not os.path.exists(log_path):
        return {"logs": [], "message": "No logs yet"}
    with open(log_path, "r") as f:
        all_lines = f.readlines()
    recent_lines = all_lines[-lines:]
    return {
        "total_lines": len(all_lines),
        "showing_last": lines,
        "logs": [line.strip() for line in recent_lines]
    }


@app.get("/history")
def get_history():
    history = load_history()
    if not history:
        return {"total": 0, "reports": []}
    summaries = []
    for entry in reversed(history):
        summaries.append({
            "id": entry["id"],
            "timestamp": entry["timestamp"],
            "team_name": entry["team_name"],
            "report_date": entry["report_date"],
            "date_range": entry["date_range"],
            "quality_check": entry["quality_check"]
        })
    return {"total": len(history), "reports": summaries}


@app.get("/history/{report_id}")
def get_report_by_id(report_id: int):
    history = load_history()
    for entry in history:
        if entry["id"] == report_id:
            return entry
    raise HTTPException(status_code=404, detail=f"Report #{report_id} not found")


@app.delete("/history")
def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
        logger.info("HISTORY  | All history cleared")
        return {"message": "Report history cleared successfully"}
    return {"message": "No history to clear"}


@app.post("/format-report", response_model=FormatResponse)
@limiter.limit("10/minute")
def format_report(request: Request, body: FormatRequest):
    error = validate_input(body.raw_text)
    if error:
        raise HTTPException(status_code=400, detail=error)

    team_name = body.team_name or config["team_name"]
    report_date = body.report_date or config["report_date"]
    date_range = body.date_range or config["date_range"]

    try:
        formatted = call_ai(body.raw_text, team_name, report_date, date_range)
        formatted = fix_ticket_ids(formatted)
        passed, missing = check_quality(formatted)

        save_to_history(
            raw_text=body.raw_text,
            formatted_report=formatted,
            team_name=team_name,
            report_date=report_date,
            date_range=date_range,
            quality_check=passed
        )

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
        raise HTTPException(status_code=500, detail=f"Error formatting report: {str(e)}")


@app.post("/format-report/batch")
def format_batch(request: BatchRequest):
    if not request.reports:
        raise HTTPException(status_code=400, detail="Reports list cannot be empty")
    if len(request.reports) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 reports per batch request")

    team_name = request.team_name or config["team_name"]
    report_date = request.report_date or config["report_date"]
    date_range = request.date_range or config["date_range"]
    results = []

    for i, raw_text in enumerate(request.reports):
        error = validate_input(raw_text)
        if error:
            results.append({"index": i, "status": "error", "error": error})
            continue
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
            results.append({"index": i, "status": "error", "error": str(e)})

    return {
        "total": len(request.reports),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results
    }


@app.post("/upload-and-format")
async def upload_and_format(
    file: UploadFile = File(...),
    team_name: str = None,
    report_date: str = None,
    date_range: str = None
):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")

    content = await file.read()
    raw_text = content.decode("utf-8")

    error = validate_input(raw_text)
    if error:
        raise HTTPException(status_code=400, detail=error)

    team_name = team_name or config["team_name"]
    report_date = report_date or config["report_date"]
    date_range = date_range or config["date_range"]

    try:
        formatted = call_ai(raw_text, team_name, report_date, date_range)
        formatted = fix_ticket_ids(formatted)
        passed, missing = check_quality(formatted)

        save_to_history(
            raw_text=raw_text,
            formatted_report=formatted,
            team_name=team_name,
            report_date=report_date,
            date_range=date_range,
            quality_check=passed
        )

        logger.info(f"UPLOAD   | File: {file.filename} | Quality: {passed}")

        return {
            "filename": file.filename,
            "formatted_report": formatted,
            "quality_check": passed,
            "missing_sections": missing,
            "model_used": config["model"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error formatting uploaded file: {str(e)}")


@app.post("/download-pdf")
def download_pdf(data: dict):
    formatted_report = data.get("formatted_report", "")
    if not formatted_report:
        raise HTTPException(status_code=400, detail="No report text provided")

    try:
        buffer = generate_pdf(formatted_report)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=formatted_report.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@app.post("/query")
def query_reports(request: QueryRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if len(request.question.strip()) < 5:
        raise HTTPException(status_code=400, detail="Question is too short — please ask a more specific question")

    history = load_history()

    if not history:
        raise HTTPException(
            status_code=404,
            detail="No reports found. Please format some reports first before querying."
        )

    recent_reports = history[-request.max_reports:]

    reports_context = ""
    for i, entry in enumerate(recent_reports, 1):
        reports_context += f"""
--- REPORT {i} ---
Team: {entry['team_name']}
Date: {entry['report_date']}
Range: {entry['date_range']}
Formatted on: {entry['timestamp']}

{entry['formatted_report']}

"""

    query_system_prompt = """
You are an intelligent assistant that answers questions about weekly engineering reports.
You have access to multiple weekly reports and must answer questions based on their content.

Rules:
- Answer based ONLY on information present in the provided reports
- Be specific — mention names, ticket IDs, module names from the reports
- If information is not in the reports, say "This information was not found in the available reports"
- Keep answers clear and well structured
- If asked about a person, find all their work across all reports
- If asked about a module, find all updates for that module across all reports
- If asked about tickets, find the specific ticket IDs mentioned
- Always mention which report by date the information came from
"""

    user_message = f"""
Here are the weekly engineering reports:

{reports_context}

Question: {request.question}

Please answer the question based on the reports above.
"""

    try:
        if provider in ["groq", "openai"]:
            response = client.chat.completions.create(
                model=config["model"],
                messages=[
                    {"role": "system", "content": query_system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            answer = response.choices[0].message.content
        elif provider == "gemini":
            from google.genai import types
            response = client.models.generate_content(
                model=config["model"],
                contents=query_system_prompt + "\n\n" + user_message,
                config=types.GenerateContentConfig(
                    max_output_tokens=1500,
                    temperature=0.3
                )
            )
            answer = response.text

        logger.info(f"QUERY    | Question: {request.question[:50]}...")

        return {
            "question": request.question,
            "answer": answer,
            "reports_searched": len(recent_reports),
            "model_used": config["model"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying reports: {str(e)}")