"""
models.py — Core schemas for the AI Readiness Assessment.

The assessment evaluates enterprises across 6 dimensions based on
industry frameworks (McKinsey AI Maturity, Gartner AI Readiness, MIT CISR).
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Assessment Dimensions
# ---------------------------------------------------------------------------

class Dimension(str, Enum):
    DATA_READINESS       = "Data Readiness"
    TECHNOLOGY_INFRA     = "Technology Infrastructure"
    TALENT_SKILLS        = "Talent & Skills"
    PROCESS_AUTOMATION   = "Process & Automation Maturity"
    GOVERNANCE_RISK      = "Governance & Risk Management"
    STRATEGY_LEADERSHIP  = "Strategy & Leadership Alignment"


DIMENSION_DESCRIPTIONS = {
    Dimension.DATA_READINESS: (
        "Quality, availability, and governance of data assets. "
        "Includes data pipelines, labelling, lineage, and accessibility."
    ),
    Dimension.TECHNOLOGY_INFRA: (
        "Cloud adoption, MLOps maturity, API ecosystems, compute availability, "
        "and integration capabilities."
    ),
    Dimension.TALENT_SKILLS: (
        "Presence of data scientists, ML engineers, AI product managers, "
        "and general AI literacy across the organisation."
    ),
    Dimension.PROCESS_AUTOMATION: (
        "Degree of existing process automation, RPA adoption, workflow digitisation, "
        "and appetite for process redesign."
    ),
    Dimension.GOVERNANCE_RISK: (
        "AI policy framework, model risk management, compliance posture, "
        "bias monitoring, and responsible AI practices."
    ),
    Dimension.STRATEGY_LEADERSHIP: (
        "Executive sponsorship, AI vision clarity, budget commitment, "
        "and organisational change management capability."
    ),
}

MATURITY_LEVELS = {
    (0.0, 2.0): ("Nascent",     "red",    "AI adoption has not meaningfully begun."),
    (2.0, 4.0): ("Emerging",    "orange", "Early experiments underway; significant gaps remain."),
    (4.0, 6.0): ("Developing",  "yellow", "Foundation in place; scaling requires targeted investment."),
    (6.0, 8.0): ("Advanced",    "green",  "Strong capability; focus on optimisation and expansion."),
    (8.0, 10.1):("Leading",     "blue",   "Industry-leading AI capability; focus on innovation."),
}


def get_maturity(score: float) -> tuple[str, str, str]:
    for (lo, hi), (label, color, description) in MATURITY_LEVELS.items():
        if lo <= score < hi:
            return label, color, description
    return "Nascent", "red", ""


# ---------------------------------------------------------------------------
# Dimension Score
# ---------------------------------------------------------------------------

class DimensionScore(BaseModel):
    dimension: Dimension
    score: float = Field(ge=0.0, le=10.0, description="Score out of 10")
    maturity_level: str
    maturity_color: str
    key_strengths: list[str] = Field(default_factory=list)
    key_gaps: list[str] = Field(default_factory=list)
    evidence_excerpts: list[str] = Field(default_factory=list, description="Relevant quotes from docs")
    recommendations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Use Case Candidate
# ---------------------------------------------------------------------------

class UseCaseCandidate(BaseModel):
    title: str
    description: str
    business_process: str
    ai_approach: str                     # e.g. "RAG", "Fine-tuned classifier", "Agentic workflow"
    estimated_complexity: str            # Low / Medium / High
    estimated_roi_impact: str            # Low / Medium / High
    prerequisites: list[str]
    priority_rank: int


# ---------------------------------------------------------------------------
# Roadmap Phase
# ---------------------------------------------------------------------------

class RoadmapPhase(BaseModel):
    phase: int
    title: str
    timeline: str                        # e.g. "0–3 months"
    focus_areas: list[str]
    key_initiatives: list[str]
    success_metrics: list[str]
    dependencies: list[str]


# ---------------------------------------------------------------------------
# Full Assessment Report
# ---------------------------------------------------------------------------

class AssessmentReport(BaseModel):
    # Metadata
    report_id: str
    organisation_name: str
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    documents_analysed: list[str]
    total_pages_analysed: int

    # Overall score
    overall_score: float = Field(ge=0.0, le=10.0)
    overall_maturity: str
    overall_maturity_color: str
    executive_summary: str

    # Dimensional breakdown
    dimension_scores: list[DimensionScore]

    # Use cases
    use_case_candidates: list[UseCaseCandidate]

    # Roadmap
    roadmap_phases: list[RoadmapPhase]

    # Data gaps (critical blockers)
    critical_blockers: list[str]
    quick_wins: list[str]

    # Raw LLM outputs (for traceability)
    analyst_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# API Schemas
# ---------------------------------------------------------------------------

class AssessmentRequest(BaseModel):
    organisation_name: str = Field(default="Enterprise Client")
    additional_context: Optional[str] = Field(
        default=None,
        description="Any additional context about the organisation (industry, size, goals)"
    )


class AssessmentStatus(BaseModel):
    session_id: str
    status: str           # "processing" | "complete" | "error"
    progress_pct: int
    current_step: str
    report: Optional[AssessmentReport] = None
    error: Optional[str] = None
