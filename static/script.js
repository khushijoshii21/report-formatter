const API = "http://127.0.0.1:8000";
window.lastFormattedReport = null;

// -------------------------------------------------------
// RELOAD CONFIG
// -------------------------------------------------------
async function reloadConfig() {
    const btn = document.getElementById("reloadBtn");
    btn.textContent = "↺ Reloading...";
    btn.classList.add("loading");
    btn.disabled = true;

    try {
        const res = await fetch(`${API}/reload-config`, { method: "POST" });
        const data = await res.json();

        if (res.ok) {
            document.getElementById("providerTag").textContent = data.api_provider.toUpperCase();
            document.getElementById("modelTag").textContent = data.model;
            document.getElementById("teamTag").textContent = data.team_name;
            document.getElementById("teamName").placeholder = data.team_name;
            document.getElementById("reportDate").placeholder = data.report_date;
            document.getElementById("dateRange").placeholder = data.date_range;

            btn.textContent = "✓ Reloaded";
            btn.style.background = "#10b981";
            btn.style.color = "white";
            btn.style.borderColor = "#10b981";

            setTimeout(() => {
                btn.textContent = "↺ Reload Config";
                btn.style.background = "";
                btn.style.color = "";
                btn.style.borderColor = "";
            }, 2000);
        } else {
            btn.textContent = "✗ Failed";
            btn.style.background = "#dc2626";
            btn.style.color = "white";
            setTimeout(() => {
                btn.textContent = "↺ Reload Config";
                btn.style.background = "";
                btn.style.color = "";
            }, 2000);
        }
    } catch {
        btn.textContent = "✗ API Offline";
        setTimeout(() => { btn.textContent = "↺ Reload Config"; }, 2000);
    } finally {
        btn.classList.remove("loading");
        btn.disabled = false;
    }
}

// -------------------------------------------------------
// FORMAT WITH INDENT
// -------------------------------------------------------
function formatWithIndent(text) {
    const lines = text.split("\n");
    const result = lines.map(line => {
        if (!line.trim()) return "<div style='height:8px'></div>";

        const spaces = line.match(/^(\s*)/)[1].length;
        const content = line.trimStart();
        const escaped = content
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        const isMainSection = spaces === 0 && (
            content.startsWith("Key Updates") ||
            content.startsWith("Key Achievements") ||
            content.startsWith("Challenges Encountered") ||
            content.startsWith("Team Challenges") ||
            content.startsWith("Key Tasks")
        );
        const isReportHeader = spaces === 0 && !content.startsWith("-") && !isMainSection;
        const isModuleOrPerson = spaces >= 2 && spaces <= 6 && !content.startsWith("-");
        const isSubHeading = spaces >= 7 && spaces <= 12 && !content.startsWith("-");
        const isBullet = content.startsWith("-");

        if (isReportHeader) {
            return `<div style="font-weight:700;font-size:14px;color:#111;margin-bottom:4px;">${escaped}</div>`;
        }
        if (isMainSection) {
            return `<div style="font-weight:700;font-size:13px;color:#111;margin-top:14px;margin-bottom:4px;">${escaped}</div>`;
        }
        if (isModuleOrPerson) {
            return `<div style="font-weight:600;font-size:13px;color:#1a1a1a;margin-top:10px;margin-bottom:2px;padding-left:${spaces*8}px;">${escaped}</div>`;
        }
        if (isSubHeading) {
            return `<div style="font-weight:600;font-size:12px;color:#374151;margin-top:6px;margin-bottom:2px;padding-left:${spaces*8}px;">${escaped}</div>`;
        }
        if (isBullet) {
            const bulletIndent = spaces * 8;
            const textPart = escaped.startsWith("- ") ? escaped.slice(2) : escaped;
            return `<div style="padding-left:${bulletIndent}px;color:#374151;font-size:13px;line-height:1.8;display:flex;align-items:flex-start;">
                <span style="flex-shrink:0;margin-right:4px;">-</span>
                <span style="word-break:break-word;overflow-wrap:anywhere;flex:1;">${textPart}</span>
            </div>`;
        }
        return `<div style="padding-left:${spaces*8}px;color:#374151;font-size:13px;">${escaped}</div>`;
    });
    return result.join("");
}

// -------------------------------------------------------
// SHOW RESULT
// -------------------------------------------------------
function showResult(data) {
    window.lastFormattedReport = data.formatted_report;
    document.getElementById("reportOutput").innerHTML = formatWithIndent(data.formatted_report);
    setState("report");

    const qp = document.getElementById("qualityPill");
    if (data.quality_check) {
        qp.textContent = "✓ Quality passed";
        qp.className = "pill pill-green";
    } else {
        qp.textContent = "✗ Missing sections";
        qp.className = "pill pill-red";
    }

    document.getElementById("modelPill").textContent = data.model_used;
    document.getElementById("statusPills").style.display = "flex";
    document.getElementById("copyBtn").style.display = "block";
    document.getElementById("pdfBtn").style.display = "block";
}

// -------------------------------------------------------
// FORMAT REPORT
// -------------------------------------------------------
async function formatReport() {
    const rawText = document.getElementById("rawInput").value.trim();
    const teamName = document.getElementById("teamName").value.trim();
    const reportDate = document.getElementById("reportDate").value.trim();
    const dateRange = document.getElementById("dateRange").value.trim();

    if (!rawText) { showError("Please paste your raw notes first."); return; }
    if (rawText.split(" ").length < 5) { showError("Notes are too short — please add more details."); return; }

    hideError();
    setState("loading");
    document.getElementById("formatBtn").disabled = true;

    try {
        const res = await fetch(`${API}/format-report`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                raw_text: rawText,
                team_name: teamName || null,
                report_date: reportDate || null,
                date_range: dateRange || null
            })
        });

        const data = await res.json();

        if (!res.ok) {
            showError(data.detail || "Something went wrong.");
            setState("empty");
            return;
        }

        showResult(data);

    } catch {
        showError("Cannot connect to API. Is the server running?");
        setState("empty");
    } finally {
        document.getElementById("formatBtn").disabled = false;
    }
}

// -------------------------------------------------------
// UPLOAD FILE
// -------------------------------------------------------
async function uploadFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    const teamName = document.getElementById("teamName").value.trim();
    const reportDate = document.getElementById("reportDate").value.trim();
    const dateRange = document.getElementById("dateRange").value.trim();

    hideError();
    setState("loading");
    document.getElementById("formatBtn").disabled = true;

    try {
        const formData = new FormData();
        formData.append("file", file);
        if (teamName) formData.append("team_name", teamName);
        if (reportDate) formData.append("report_date", reportDate);
        if (dateRange) formData.append("date_range", dateRange);

        const res = await fetch(`${API}/upload-and-format`, {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (!res.ok) {
            showError(data.detail || "Something went wrong.");
            setState("empty");
            return;
        }

        showResult(data);

    } catch {
        showError("Cannot connect to API. Is the server running?");
        setState("empty");
    } finally {
        document.getElementById("formatBtn").disabled = false;
        event.target.value = "";
    }
}

// -------------------------------------------------------
// COPY REPORT
// -------------------------------------------------------
function copyReport() {
    const text = window.lastFormattedReport;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById("copyBtn");
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = "Copy Report"; }, 2000);
    });
}

// -------------------------------------------------------
// DOWNLOAD PDF
// -------------------------------------------------------
async function downloadPDF() {
    const text = window.lastFormattedReport;
    if (!text) { showError("Please format a report first."); return; }

    try {
        const res = await fetch(`${API}/download-pdf`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ formatted_report: text })
        });

        if (!res.ok) { showError("Failed to generate PDF."); return; }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "formatted_report.pdf";
        a.click();
        window.URL.revokeObjectURL(url);

    } catch {
        showError("Cannot connect to API. Is the server running?");
    }
}

// -------------------------------------------------------
// CLEAR ALL
// -------------------------------------------------------
function clearAll() {
    document.getElementById("rawInput").value = "";
    document.getElementById("teamName").value = "";
    document.getElementById("reportDate").value = "";
    document.getElementById("dateRange").value = "";
    setState("empty");
    document.getElementById("statusPills").style.display = "none";
    document.getElementById("copyBtn").style.display = "none";
    document.getElementById("pdfBtn").style.display = "none";
    window.lastFormattedReport = null;
    hideError();
}

// -------------------------------------------------------
// STATE MANAGEMENT
// -------------------------------------------------------
function setState(state) {
    document.getElementById("emptyState").style.display = state === "empty" ? "flex" : "none";
    document.getElementById("loadingState").style.display = state === "loading" ? "flex" : "none";
    document.getElementById("reportOutput").style.display = state === "report" ? "block" : "none";
}

function showError(msg) {
    const el = document.getElementById("errorMsg");
    el.textContent = msg;
    el.style.display = "flex";
}

function hideError() {
    document.getElementById("errorMsg").style.display = "none";
}

// -------------------------------------------------------
// ASK QUESTION
// -------------------------------------------------------
async function askQuestion() {
    const question = document.getElementById("queryInput").value.trim();

    if (!question) {
        document.getElementById("queryError").textContent = "Please type a question first.";
        document.getElementById("queryError").style.display = "block";
        return;
    }

    document.getElementById("queryError").style.display = "none";
    document.getElementById("queryAnswerBox").style.display = "none";
    document.getElementById("queryLoading").style.display = "flex";
    document.getElementById("askBtn").disabled = true;

    try {
        const res = await fetch(`${API}/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                max_reports: 10
            })
        });

        const data = await res.json();

        if (!res.ok) {
            document.getElementById("queryError").textContent = data.detail || "Something went wrong.";
            document.getElementById("queryError").style.display = "block";
            return;
        }

        document.getElementById("queryQuestion").textContent = `Q: ${data.question}`;
        document.getElementById("queryMeta").textContent = `Searched ${data.reports_searched} report(s) • ${data.model_used}`;
        document.getElementById("queryAnswer").textContent = data.answer;
        document.getElementById("queryAnswerBox").style.display = "block";

    } catch {
        document.getElementById("queryError").textContent = "Cannot connect to API. Is the server running?";
        document.getElementById("queryError").style.display = "block";
    } finally {
        document.getElementById("queryLoading").style.display = "none";
        document.getElementById("askBtn").disabled = false;
    }
}

function askSuggestion(question) {
    document.getElementById("queryInput").value = question;
    askQuestion();
}

// -------------------------------------------------------
// LOAD CONFIG ON STARTUP
// -------------------------------------------------------
async function loadConfig() {
    try {
        const res = await fetch(`${API}/config`);
        const data = await res.json();
        document.getElementById("providerTag").textContent = data.api_provider.toUpperCase();
        document.getElementById("modelTag").textContent = data.model;
        document.getElementById("teamTag").textContent = data.team_name;
        document.getElementById("teamName").placeholder = data.team_name;
        document.getElementById("reportDate").placeholder = data.report_date;
        document.getElementById("dateRange").placeholder = data.date_range;
    } catch {
        document.getElementById("providerTag").textContent = "API Offline";
    }
}

loadConfig();
