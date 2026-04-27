import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path so we can import api.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import app

# Create test client — this simulates sending real HTTP requests
# to your API without needing the server to actually be running
client = TestClient(app)


# -------------------------------------------------------
# TEST GROUP 1 — Basic endpoints
# Tests that the simple GET endpoints work correctly
# -------------------------------------------------------

def test_root():
    """
    Test the root endpoint returns a welcome message
    and lists all available endpoints
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "endpoints" in data
    print("✓ Root endpoint working")


def test_health_check():
    """
    Test the health endpoint returns healthy status
    and shows current model and provider
    """
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "api_provider" in data
    assert "model" in data
    assert "team" in data
    print("✓ Health check passing")


def test_get_config():
    """
    Test the config endpoint returns all required
    configuration fields
    """
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "api_provider" in data
    assert "model" in data
    assert "team_name" in data
    assert "report_date" in data
    assert "date_range" in data
    assert "max_tokens" in data
    assert "temperature" in data
    print("✓ Config endpoint returning all fields")


def test_reload_config():
    """
    Test that reload-config endpoint works and
    returns updated configuration
    """
    response = client.post("/reload-config")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "Configuration reloaded successfully"
    assert "model" in data
    assert "api_provider" in data
    assert "team_name" in data
    assert "report_date" in data
    assert "date_range" in data
    print("✓ Reload config working")


# -------------------------------------------------------
# TEST GROUP 2 — Edge case validation
# Tests that bad input is rejected with correct errors
# These should all return 400 status code
# -------------------------------------------------------

def test_empty_input():
    """
    Test that empty input is rejected
    Expected: 400 error with empty input message
    """
    response = client.post("/format-report", json={
        "raw_text": ""
    })
    assert response.status_code == 400
    data = response.json()
    assert "empty" in data["detail"].lower()
    print("✓ Empty input correctly rejected")


def test_whitespace_only_input():
    """
    Test that input with only spaces/newlines is rejected
    Expected: 400 error with empty input message
    """
    response = client.post("/format-report", json={
        "raw_text": "   \n\n   \t   "
    })
    assert response.status_code == 400
    data = response.json()
    assert "empty" in data["detail"].lower()
    print("✓ Whitespace-only input correctly rejected")


def test_gibberish_input():
    """
    Test that gibberish input (mostly symbols) is rejected
    Expected: 400 error with symbols/characters message
    """
    response = client.post("/format-report", json={
        "raw_text": "@@### $$$ !!! %%% *** &&& ^^^ ~~~"
    })
    assert response.status_code == 400
    data = response.json()
    assert "symbol" in data["detail"].lower() or "character" in data["detail"].lower()
    print("✓ Gibberish input correctly rejected")


def test_too_short_input():
    """
    Test that very short input is rejected
    Expected: 400 error with too short message
    """
    response = client.post("/format-report", json={
        "raw_text": "fixed a bug"
    })
    assert response.status_code == 400
    data = response.json()
    assert "short" in data["detail"].lower()
    print("✓ Too short input correctly rejected")


def test_no_modules_input():
    """
    Test that input without any module/project names is rejected
    Expected: 400 error with no modules message
    """
    response = client.post("/format-report", json={
        "raw_text": "had a great week met with the team discussed plans for the future and reviewed some documents"
    })
    assert response.status_code == 400
    data = response.json()
    assert "module" in data["detail"].lower() or "project" in data["detail"].lower()
    print("✓ No modules input correctly rejected")


# -------------------------------------------------------
# TEST GROUP 3 — Successful formatting
# Tests that valid input is formatted correctly
# These should all return 200 status code
# -------------------------------------------------------

def test_format_report_module_grouped():
    """
    Test formatting of module-grouped raw notes
    (React Interview, Live Interview etc)
    Expected: 200 with formatted report and quality passed
    """
    response = client.post("/format-report", json={
        "raw_text": """React Interview
  fix: #jent-15202 fixed login timeout issue
  enhc: improved interview loading speed
  chore: updated dependencies

Live Interview
  feat: added screen sharing support
  fix: #jent-15301 fixed audio drop on mobile""",
        "team_name": "MMU",
        "report_date": "Apr 27, 2026",
        "date_range": "Apr 20 – Apr 27"
    })
    assert response.status_code == 200
    data = response.json()
    assert "formatted_report" in data
    assert len(data["formatted_report"]) > 100
    assert data["quality_check"] == True
    assert data["missing_sections"] == []
    assert "MMU" in data["formatted_report"]
    assert "Key Updates" in data["formatted_report"]
    assert "Key Achievements" in data["formatted_report"]
    assert "Challenges Encountered" in data["formatted_report"]
    assert "Team Challenges" in data["formatted_report"]
    assert "Key Tasks Scheduled for Next Week" in data["formatted_report"]
    print("✓ Module-grouped report formatted correctly")


def test_format_report_person_grouped():
    """
    Test formatting of person-grouped raw notes
    (Arun, Sumit, Milind etc)
    Expected: 200 with formatted report preserving person names
    """
    response = client.post("/format-report", json={
        "raw_text": """Arun
  Bug:
    inte- 1059, 1067, 1068
    jent- 14954, 14811
  ATS:
    Nexus ATS custom field changes
    Tracker RMS token expiry issue

Sumit
  Candidate Recommendation
    fix: #jent-15038 fixed candidate sorting
    update: improved matching algorithm""",
        "team_name": "MMU",
        "report_date": "Apr 27, 2026",
        "date_range": "Apr 20 – Apr 27"
    })
    assert response.status_code == 200
    data = response.json()
    assert "formatted_report" in data
    assert data["quality_check"] == True
    assert "Arun" in data["formatted_report"]
    assert "Sumit" in data["formatted_report"]
    print("✓ Person-grouped report formatted correctly")


def test_format_report_uses_config_defaults():
    """
    Test that when team_name, report_date, date_range
    are not provided, config.json defaults are used
    """
    response = client.post("/format-report", json={
        "raw_text": """React Interview
  fix: #jent-15202 fixed login timeout issue
  enhc: improved interview loading speed

Live Interview
  feat: added screen sharing support
  fix: #jent-15301 fixed audio drop on mobile"""
    })
    assert response.status_code == 200
    data = response.json()
    assert data["team_name"] is not None
    assert data["report_date"] is not None
    assert data["date_range"] is not None
    print("✓ Config defaults used when fields not provided")


def test_format_report_custom_values():
    """
    Test that custom team_name, report_date, date_range
    override config defaults
    """
    response = client.post("/format-report", json={
        "raw_text": """React Interview
  fix: #jent-15202 fixed login timeout issue
  enhc: improved interview loading speed

Live Interview
  feat: added screen sharing support""",
        "team_name": "TEST TEAM",
        "report_date": "Apr 27, 2026",
        "date_range": "Apr 20 – Apr 27"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["team_name"] == "TEST TEAM"
    assert data["report_date"] == "Apr 27, 2026"
    assert "TEST TEAM" in data["formatted_report"]
    print("✓ Custom values override config defaults")


def test_response_contains_model_info():
    """
    Test that response always includes which model
    and provider was used
    """
    response = client.post("/format-report", json={
        "raw_text": """React Interview
  fix: #jent-15202 fixed login timeout issue
  enhc: improved interview loading speed

Live Interview
  feat: added screen sharing support"""
    })
    assert response.status_code == 200
    data = response.json()
    assert "model_used" in data
    assert "api_provider" in data
    assert len(data["model_used"]) > 0
    assert len(data["api_provider"]) > 0
    print("✓ Response includes model and provider info")


# -------------------------------------------------------
# TEST GROUP 4 — Batch endpoint
# Tests the batch formatting endpoint
# -------------------------------------------------------

def test_batch_format_valid():
    """
    Test batch formatting with valid reports
    Expected: 200 with all reports formatted successfully
    """
    response = client.post("/format-report/batch", json={
        "reports": [
            """React Interview
  fix: #jent-15202 fixed login timeout issue
  enhc: improved interview loading speed""",
            """Live Interview
  feat: added screen sharing support
  fix: #jent-15301 fixed audio drop on mobile
  enhc: improved video quality"""
        ],
        "team_name": "MMU",
        "report_date": "Apr 27, 2026",
        "date_range": "Apr 20 – Apr 27"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["successful"] == 2
    assert data["failed"] == 0
    assert len(data["results"]) == 2
    print("✓ Batch formatting working for valid reports")


def test_batch_empty_list():
    """
    Test batch endpoint with empty reports list
    Expected: 400 error
    """
    response = client.post("/format-report/batch", json={
        "reports": []
    })
    assert response.status_code == 400
    print("✓ Empty batch list correctly rejected")


def test_batch_too_many_reports():
    """
    Test batch endpoint with more than 10 reports
    Expected: 400 error with limit message
    """
    reports = ["React Interview\n  fix: #jent-15202 fixed issue\n  enhc: improved speed"] * 11
    response = client.post("/format-report/batch", json={
        "reports": reports
    })
    assert response.status_code == 400
    data = response.json()
    assert "10" in data["detail"]
    print("✓ Batch limit of 10 correctly enforced")


def test_batch_mixed_valid_invalid():
    """
    Test batch with mix of valid and invalid reports
    Expected: valid ones succeed, invalid ones fail with error
    """
    response = client.post("/format-report/batch", json={
        "reports": [
            """React Interview
  fix: #jent-15202 fixed login timeout
  enhc: improved loading speed""",
            "fixed a bug",
        ],
        "team_name": "MMU"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["successful"] == 1
    assert data["failed"] == 1
    results = data["results"]
    assert results[0]["status"] == "success"
    assert results[1]["status"] == "error"
    print("✓ Batch correctly handles mix of valid and invalid")


# -------------------------------------------------------
# TEST GROUP 5 — Ticket ID formatting
# Tests that ticket IDs are formatted correctly
# -------------------------------------------------------

def test_ticket_id_single_hash():
    """
    Test that # appears only once in ticket ID lists
    Input:  fix: #14798, #15058, #14888
    Output: fix: #14798, 15058, 14888
    """
    response = client.post("/format-report", json={
        "raw_text": """React Interview
  fix: #14798, #15058, #14888 fixed multiple login issues
  enhc: improved interview loading speed
  chore: updated dependencies""",
        "team_name": "MMU"
    })
    assert response.status_code == 200
    data = response.json()
    report = data["formatted_report"]
    # Should not have consecutive ## patterns
    assert "##" not in report
    print("✓ Ticket ID hash deduplication working")


def test_jent_prefix_gets_hash():
    """
    Test that jent- prefix automatically gets # added
    Input:  jent-15038
    Output: #jent-15038
    """
    response = client.post("/format-report", json={
        "raw_text": """React Interview
  fix: jent-15038 fixed login timeout issue
  enhc: improved interview loading speed
  chore: updated node packages""",
        "team_name": "MMU"
    })
    assert response.status_code == 200
    data = response.json()
    report = data["formatted_report"]
    assert "#jent-" in report
    print("✓ jent- prefix gets # added automatically")
