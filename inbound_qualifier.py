#!/usr/bin/env python3
"""
Human Signal — Contact Sales Qualification Demo
Binary routing: Enterprise AE or Manual Review
Logs all submissions to Google Sheets and emails the assigned AE for vetted leads.
"""

from __future__ import annotations

import json
import os
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import anthropic
import requests
from bs4 import BeautifulSoup

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSHEETS = True
except Exception:
    HAS_GSHEETS = False

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

TECH_INDUSTRIES = {
    "software", "technology", "artificial intelligence", "ai", "machine learning",
    "data infrastructure", "developer tools", "cloud", "saas", "robotics", "autonomous vehicles"
}
REGULATED_INDUSTRIES = {
    "healthcare", "health tech", "biotech", "life sciences", "financial services",
    "fintech", "insurance", "government", "public sector", "defense", "legal"
}


AE_ROSTER = [
    {
        "name": "Sarah Chen",
        "email": os.environ.get("AE_SARAH_EMAIL", "sarah.chen@example.com"),
        "industries": {"healthcare", "health tech", "biotech", "life sciences", "financial services", "fintech", "insurance"},
        "handles_regulated": True,
        "description": "Regulated industries",
    },
    {
        "name": "Michael Torres",
        "email": os.environ.get("AE_MICHAEL_EMAIL", "michael.torres@example.com"),
        "industries": {"software", "technology", "artificial intelligence", "ai", "machine learning", "developer tools", "cloud", "saas"},
        "handles_regulated": False,
        "description": "Tech and AI-native companies",
    },
    {
        "name": "Priya Patel",
        "email": os.environ.get("AE_PRIYA_EMAIL", "priya.patel@example.com"),
        "industries": set(),
        "handles_regulated": True,
        "description": "Strategic and complex accounts",
    },
    {
        "name": "David Kim",
        "email": os.environ.get("AE_DAVID_EMAIL", "david.kim@example.com"),
        "industries": set(),
        "handles_regulated": False,
        "description": "General coverage",
    },
]

COMPANY_OVERRIDES = {
    # "OpenAI": "Priya Patel",
    # "Waymo": "Michael Torres",
}

RAW_HEADERS = [
    "timestamp", "first_name", "last_name", "company_email", "company", "using_label_studio_oss",
    "reason_for_reaching_out", "website", "company_context", "recent_news", "company_domain",
]

QUALIFIED_HEADERS = [
    "timestamp", "lead_id", "full_name", "company", "company_email", "using_label_studio_oss",
    "decision", "confidence", "assigned_ae", "assigned_ae_email", "industry", "project_scope",
    "use_case_complexity", "regulated_data_flag", "urgency", "enterprise_score", "signals",
    "reasoning", "draft_internal_summary", "website",
]

REVIEW_HEADERS = [
    "timestamp", "lead_id", "full_name", "company", "company_email", "using_label_studio_oss",
    "decision", "confidence", "industry", "project_scope", "use_case_complexity",
    "regulated_data_flag", "urgency", "enterprise_score", "signals", "reasoning",
    "review_status", "reviewer_notes", "website",
]


@dataclass
class LeadSubmission:
    first_name: str
    last_name: str
    company_email: str
    company: str
    using_label_studio_oss: str
    reason_for_reaching_out: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def company_domain(self) -> str:
        email = (self.company_email or "").strip().lower()
        if "@" in email:
            return email.split("@", 1)[1]
        return ""


class GoogleSheetsLogger:
    def __init__(self) -> None:
        self.sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
        self.gc = None
        if HAS_GSHEETS and self.sheet_id:
            creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
            if creds_json:
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ]
                creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
                self.gc = gspread.authorize(creds)

    def available(self) -> bool:
        return self.gc is not None and bool(self.sheet_id)

    def _get_ws(self, title: str, headers: List[str]):
        sh = self.gc.open_by_key(self.sheet_id)
        try:
            ws = sh.worksheet(title)
        except Exception:
            ws = sh.add_worksheet(title=title, rows=200, cols=max(20, len(headers) + 2))
            ws.append_row(headers)
        if ws.row_count >= 1 and not ws.get("1:1"):
            ws.append_row(headers)
        existing_headers = ws.row_values(1)
        if existing_headers != headers:
            ws.update("1:1", [headers])
        return ws

    def append_row(self, tab_name: str, headers: List[str], row: Dict[str, Any]) -> bool:
        if not self.available():
            return False
        ws = self._get_ws(tab_name, headers)
        ws.append_row([self._stringify(row.get(h, "")) for h in headers], value_input_option="USER_ENTERED")
        return True

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        if value is None:
            return ""
        return str(value)


def get_anthropic_client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def fetch_website(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url

    headers = {"User-Agent": "Mozilla/5.0"}

    def _scrape(target_url: str) -> str:
        r = requests.get(target_url, headers=headers, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button", "noscript", "iframe"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)

    try:
        text = _scrape(url)
        if len(text) < 600:
            try:
                text += " " + _scrape(urljoin(url, "/about"))
            except Exception:
                pass
        return text[:3500]
    except Exception as exc:
        return f"(Could not fetch website: {exc})"


def infer_website(company: str, domain: str) -> str:
    if domain and "." in domain and not any(x in domain for x in ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]):
        return f"https://{domain}"
    if company:
        slug = re.sub(r"[^a-z0-9]", "", company.lower())
        if slug:
            return f"https://{slug}.com"
    return ""


def try_get_news(company_name: str) -> str:
    try:
        from duckduckgo_search import DDGS
    except Exception:
        return ""

    try:
        items: List[str] = []
        with DDGS() as ddgs:
            for item in ddgs.news(company_name, max_results=3):
                title = item.get("title", "")
                body = item.get("body", "")
                date = item.get("date", "recent")
                items.append(f"- {title} ({date}): {body[:160]}")
        return "\n".join(items)
    except Exception:
        return ""


def safe_json_parse(text: str) -> Dict[str, Any]:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text)


def build_prompt(lead: LeadSubmission, website_text: str, news_text: str) -> str:
    return f"""You are an inbound lead qualification agent for HumanSignal.

HumanSignal sells Label Studio Enterprise, a production-grade data labeling and AI evaluation platform used for LLM fine-tuning, RLHF, computer vision, NLP, speech AI, and model evaluation. HumanSignal's GTM motion is open-source to enterprise conversion.

Strong-fit accounts typically have one or more of these traits:
- Companies actively building or deploying AI/ML systems in production
- LLM fine-tuning, RLHF, computer vision, NLP, speech, or model evaluation workflows
- Tech or regulated-industry companies
- Teams with meaningful data labeling or evaluation needs
- Need for compliance, auditability, security review, or enterprise controls
- Existing open-source usage that is hitting limitations

Weak-fit accounts typically have one or more of these traits:
- Student, hobby, academic, or highly exploratory usage
- No clear business use case
- Small experiments with no production intent
- No real AI/ML workflow described

Your task: review the lead and return structured JSON only.
Be conservative. If the lead is not clearly good, choose manual_review.

INPUT:
first_name: {lead.first_name}
last_name: {lead.last_name}
company_email: {lead.company_email}
company: {lead.company}
using_label_studio_oss: {lead.using_label_studio_oss}
reason_for_reaching_out: {lead.reason_for_reaching_out}
company_domain: {lead.company_domain}
website_text: {website_text or 'None'}
recent_news: {news_text or 'None'}

Return JSON only with this exact schema:
{{
  "industry": "string",
  "project_scope": "Exploratory | Pilot | Production | Unknown",
  "use_case_complexity": "Low | Medium | High | Unknown",
  "regulated_data_flag": true,
  "urgency": "Low | Medium | High | Unknown",
  "buyer_seriousness": "Low | Medium | High | Unknown",
  "signals": ["signal 1", "signal 2"],
  "reasoning": "2-4 sentences",
  "enterprise_score": 0,
  "draft_internal_summary": "short internal AE summary"
}}

Scoring guidance:
- 8-10 = obvious enterprise lead
- 5-7 = plausible but not certain
- 0-4 = weak or unclear

Score higher for production AI/ML, data sensitivity, regulated industries, technical buyer signals, open-source limits, and strong urgency.
Score lower for vague, personal, student, or hobby use.
"""


def classify_with_llm(lead: LeadSubmission, website_text: str, news_text: str) -> Dict[str, Any]:
    client = get_anthropic_client()
    prompt = build_prompt(lead, website_text, news_text)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text if msg.content else "{}"
    parsed = safe_json_parse(text)
    parsed.setdefault("signals", [])
    parsed.setdefault("reasoning", "")
    parsed.setdefault("industry", "Unknown")
    parsed.setdefault("project_scope", "Unknown")
    parsed.setdefault("use_case_complexity", "Unknown")
    parsed.setdefault("regulated_data_flag", False)
    parsed.setdefault("urgency", "Unknown")
    parsed.setdefault("buyer_seriousness", "Unknown")
    parsed.setdefault("enterprise_score", 0)
    parsed.setdefault("draft_internal_summary", "")
    return parsed


def finalize_decision(llm_result: Dict[str, Any]) -> Tuple[str, float]:
    score = int(llm_result.get("enterprise_score", 0) or 0)
    industry = str(llm_result.get("industry", "Unknown") or "Unknown").strip().lower()
    regulated = bool(llm_result.get("regulated_data_flag", False))
    scope = str(llm_result.get("project_scope", "Unknown"))
    complexity = str(llm_result.get("use_case_complexity", "Unknown"))
    urgency = str(llm_result.get("urgency", "Unknown"))
    seriousness = str(llm_result.get("buyer_seriousness", "Unknown"))

    rule_points = 0
    if regulated:
        rule_points += 2
    if industry in TECH_INDUSTRIES or industry in REGULATED_INDUSTRIES:
        rule_points += 1
    if scope == "Production":
        rule_points += 2
    elif scope == "Pilot":
        rule_points += 1
    if complexity == "High":
        rule_points += 2
    elif complexity == "Medium":
        rule_points += 1
    if urgency == "High":
        rule_points += 1
    if seriousness == "High":
        rule_points += 1

    combined = score + rule_points
    confidence = max(0.3, min(0.98, combined / 12.0))

    enterprise = False
    if regulated and scope in {"Pilot", "Production"}:
        enterprise = True
    elif combined >= 8 and seriousness != "Low":
        enterprise = True
    elif score >= 8:
        enterprise = True

    return ("enterprise_ae" if enterprise else "manual_review"), round(confidence, 2)


def assign_ae(company: str, industry: str, regulated_data_flag: bool, complexity: str, scope: str) -> Dict[str, str]:
    override_name = COMPANY_OVERRIDES.get(company.strip())
    if override_name:
        for ae in AE_ROSTER:
            if ae["name"] == override_name:
                return {"name": ae["name"], "email": ae["email"], "reason": "Company override"}

    normalized_industry = (industry or "").strip().lower()

    if regulated_data_flag or normalized_industry in REGULATED_INDUSTRIES:
        ae = next(a for a in AE_ROSTER if a["name"] == "Sarah Chen")
        return {"name": ae["name"], "email": ae["email"], "reason": "Regulated or sensitive data"}

    if normalized_industry in TECH_INDUSTRIES:
        ae = next(a for a in AE_ROSTER if a["name"] == "Michael Torres")
        return {"name": ae["name"], "email": ae["email"], "reason": "Tech or AI-native account"}

    if complexity == "High" or scope == "Production":
        ae = next(a for a in AE_ROSTER if a["name"] == "Priya Patel")
        return {"name": ae["name"], "email": ae["email"], "reason": "Complex or strategic account"}

    ae = next(a for a in AE_ROSTER if a["name"] == "David Kim")
    return {"name": ae["name"], "email": ae["email"], "reason": "General qualified inbound"}


def send_email_notification(to_email: str, subject: str, body: str, reply_to: Optional[str] = None) -> Tuple[bool, str]:
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    from_email = os.environ.get("FROM_EMAIL", smtp_user)

    if not all([smtp_host, smtp_user, smtp_password, from_email]):
        return False, "SMTP credentials are not configured."

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True, "Email sent."
    except Exception as exc:
        return False, str(exc)


def build_lead_id(lead: LeadSubmission) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    company = re.sub(r"[^a-z0-9]", "", lead.company.lower())[:12] or "lead"
    return f"{company}-{stamp}"


def process_lead_submission(payload: Dict[str, str]) -> Dict[str, Any]:
    lead = LeadSubmission(
        first_name=payload.get("first_name", "").strip(),
        last_name=payload.get("last_name", "").strip(),
        company_email=payload.get("company_email", "").strip(),
        company=payload.get("company", "").strip(),
        using_label_studio_oss=payload.get("using_label_studio_oss", "").strip(),
        reason_for_reaching_out=payload.get("reason_for_reaching_out", "").strip(),
    )

    if not lead.first_name or not lead.last_name or not lead.company_email or not lead.company or not lead.reason_for_reaching_out:
        raise ValueError("Missing required form fields.")

    website = infer_website(lead.company, lead.company_domain)
    website_text = fetch_website(website)
    news_text = try_get_news(lead.company)
    llm_result = classify_with_llm(lead, website_text, news_text)
    decision, confidence = finalize_decision(llm_result)

    ae_assignment = {"name": "", "email": "", "reason": ""}
    if decision == "enterprise_ae":
        ae_assignment = assign_ae(
            company=lead.company,
            industry=llm_result.get("industry", "Unknown"),
            regulated_data_flag=bool(llm_result.get("regulated_data_flag", False)),
            complexity=llm_result.get("use_case_complexity", "Unknown"),
            scope=llm_result.get("project_scope", "Unknown"),
        )

    lead_id = build_lead_id(lead)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    result = {
        "timestamp": now,
        "lead_id": lead_id,
        "decision": decision,
        "confidence": confidence,
        "assigned_ae": ae_assignment.get("name", ""),
        "assigned_ae_email": ae_assignment.get("email", ""),
        "ae_assignment_reason": ae_assignment.get("reason", ""),
        "website": website,
        "company_context": website_text,
        "recent_news": news_text,
        "llm": llm_result,
        "lead": {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "full_name": lead.full_name,
            "company_email": lead.company_email,
            "company": lead.company,
            "using_label_studio_oss": lead.using_label_studio_oss,
            "reason_for_reaching_out": lead.reason_for_reaching_out,
            "company_domain": lead.company_domain,
        },
    }

    log_to_sheets(result)
    notify(result)
    return result


def log_to_sheets(result: Dict[str, Any]) -> None:
    logger = GoogleSheetsLogger()
    if not logger.available():
        return

    lead = result["lead"]
    llm = result["llm"]

    logger.append_row(
        "Raw_Submissions",
        RAW_HEADERS,
        {
            "timestamp": result["timestamp"],
            "first_name": lead["first_name"],
            "last_name": lead["last_name"],
            "company_email": lead["company_email"],
            "company": lead["company"],
            "using_label_studio_oss": lead["using_label_studio_oss"],
            "reason_for_reaching_out": lead["reason_for_reaching_out"],
            "website": result["website"],
            "company_context": result["company_context"],
            "recent_news": result["recent_news"],
            "company_domain": lead["company_domain"],
        },
    )

    base_row = {
        "timestamp": result["timestamp"],
        "lead_id": result["lead_id"],
        "full_name": lead["full_name"],
        "company": lead["company"],
        "company_email": lead["company_email"],
        "using_label_studio_oss": lead["using_label_studio_oss"],
        "decision": result["decision"],
        "confidence": result["confidence"],
        "industry": llm.get("industry", "Unknown"),
        "project_scope": llm.get("project_scope", "Unknown"),
        "use_case_complexity": llm.get("use_case_complexity", "Unknown"),
        "regulated_data_flag": llm.get("regulated_data_flag", False),
        "urgency": llm.get("urgency", "Unknown"),
        "enterprise_score": llm.get("enterprise_score", 0),
        "signals": llm.get("signals", []),
        "reasoning": llm.get("reasoning", ""),
        "draft_internal_summary": llm.get("draft_internal_summary", ""),
        "website": result["website"],
    }

    if result["decision"] == "enterprise_ae":
        logger.append_row(
            "Qualified_Leads",
            QUALIFIED_HEADERS,
            {
                **base_row,
                "assigned_ae": result["assigned_ae"],
                "assigned_ae_email": result["assigned_ae_email"],
            },
        )
    else:
        logger.append_row(
            "Manual_Review",
            REVIEW_HEADERS,
            {
                **base_row,
                "review_status": "Pending",
                "reviewer_notes": "",
            },
        )


def notify(result: Dict[str, Any]) -> Tuple[bool, str]:
    lead = result["lead"]
    llm = result["llm"]

    if result["decision"] == "enterprise_ae":
        subject = f"New vetted lead for review: {lead['company']} → {result['assigned_ae']}"
        body = f"""A new HumanSignal demo lead was vetted and routed to you.

Lead ID: {result['lead_id']}
Contact: {lead['full_name']}
Email: {lead['company_email']}
Company: {lead['company']}
Using Label Studio OSS: {lead['using_label_studio_oss']}
Assigned AE: {result['assigned_ae']}
Assignment reason: {result['ae_assignment_reason']}

Qualification summary:
- Decision: Enterprise AE
- Confidence: {result['confidence']}
- Industry: {llm.get('industry', 'Unknown')}
- Project scope: {llm.get('project_scope', 'Unknown')}
- Use case complexity: {llm.get('use_case_complexity', 'Unknown')}
- Regulated data: {llm.get('regulated_data_flag', False)}
- Urgency: {llm.get('urgency', 'Unknown')}
- Enterprise score: {llm.get('enterprise_score', 0)}

Signals:
- """ + "\n- ".join(llm.get("signals", [])) + f"""

Reasoning:
{llm.get('reasoning', '')}

Prospect message:
{lead['reason_for_reaching_out']}

Website:
{result['website']}
"""
        return send_email_notification(
            to_email=result["assigned_ae_email"],
            subject=subject,
            body=body,
            reply_to=lead["company_email"],
        )

    review_email = os.environ.get("MANUAL_REVIEW_EMAIL", os.environ.get("FROM_EMAIL", ""))
    if not review_email:
        return False, "No manual review email configured."

    subject = f"Manual review queue: {lead['company']}"
    body = f"""A new lead was sent to manual review.

Lead ID: {result['lead_id']}
Contact: {lead['full_name']}
Email: {lead['company_email']}
Company: {lead['company']}
Using Label Studio OSS: {lead['using_label_studio_oss']}

Qualification summary:
- Decision: Manual Review
- Confidence: {result['confidence']}
- Industry: {llm.get('industry', 'Unknown')}
- Project scope: {llm.get('project_scope', 'Unknown')}
- Use case complexity: {llm.get('use_case_complexity', 'Unknown')}
- Regulated data: {llm.get('regulated_data_flag', False)}
- Urgency: {llm.get('urgency', 'Unknown')}
- Enterprise score: {llm.get('enterprise_score', 0)}

Signals:
- """ + "\n- ".join(llm.get("signals", [])) + f"""

Reasoning:
{llm.get('reasoning', '')}

Prospect message:
{lead['reason_for_reaching_out']}

Website:
{result['website']}
"""
    return send_email_notification(
        to_email=review_email,
        subject=subject,
        body=body,
        reply_to=lead["company_email"],
    )
