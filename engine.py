"""
assessment/engine.py
====================
Claude-powered AI Readiness Assessment Engine.

For each of the 6 dimensions, the engine:
1. Retrieves the most relevant document chunks via RAG
2. Prompts Claude with the evidence + scoring rubric
3. Parses a structured JSON score with strengths, gaps, and recommendations

Then synthesises everything into:
- Overall score & maturity level
- Use case candidates (ranked by ROI × feasibility)
- A phased adoption roadmap
- Critical blockers and quick wins
"""

import json
import uuid
import logging
from anthropic import Anthropic

from config import settings
from models import (
    Dimension, DIMENSION_DESCRIPTIONS, DimensionScore, UseCaseCandidate,
    RoadmapPhase, AssessmentReport, get_maturity,
)
from ingestion.pipeline import search_documents, ExtractedDocument

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

DIMENSION_PROMPT = """You are a senior AI Strategy Consultant performing an AI Readiness Assessment.

You are evaluating the dimension: **{dimension}**
Definition: {description}

SCORING RUBRIC (score out of 10):
- 0–2 (Nascent): No meaningful capability. Major foundational gaps.
- 3–4 (Emerging): Early experiments. Significant gaps. Ad-hoc processes.
- 5–6 (Developing): Repeatable foundation. Clear gaps in scale/governance.
- 7–8 (Advanced): Strong capability. Minor gaps. Some best practices in place.
- 9–10 (Leading): Industry-leading. Systematic. Continuously improving.

EVIDENCE FROM ENTERPRISE DOCUMENTS:
{evidence}

ADDITIONAL CONTEXT:
{context}

Assess this dimension based ONLY on the evidence provided. Do not invent information.
If evidence is sparse, score conservatively and note the gap.

Respond with ONLY valid JSON:
{{
  "score": <float 0-10>,
  "key_strengths": [<up to 3 specific strengths evidenced in the docs>],
  "key_gaps": [<up to 4 specific gaps or missing capabilities>],
  "evidence_excerpts": [<1-2 direct quotes or paraphrases from the evidence>],
  "recommendations": [<3-4 specific, actionable recommendations>]
}}"""


USE_CASE_PROMPT = """You are an AI Solutions Architect identifying AI use case candidates for an enterprise.

ENTERPRISE CONTEXT (from their documents):
{context}

DIMENSION SCORES SUMMARY:
{scores_summary}

ADDITIONAL CONTEXT:
{additional_context}

Identify the TOP 5 most valuable AI use cases for this enterprise based on:
1. Evidence that the process exists and is significant
2. Feasibility given their current maturity scores
3. Expected ROI and business impact
4. Data availability

For each use case, specify an AI approach from: RAG, Fine-tuned classifier, 
Agentic workflow, Predictive model, Generative AI, Computer vision, NLP pipeline.

Respond with ONLY valid JSON — an array of 5 objects:
[{{
  "title": <concise use case name>,
  "description": <2-sentence description>,
  "business_process": <which business process this automates/augments>,
  "ai_approach": <specific AI approach>,
  "estimated_complexity": "Low" | "Medium" | "High",
  "estimated_roi_impact": "Low" | "Medium" | "High",
  "prerequisites": [<2-3 things needed before implementation>],
  "priority_rank": <1-5, 1 = highest>
}}]"""


ROADMAP_PROMPT = """You are an AI Transformation Consultant creating a phased adoption roadmap.

ORGANISATION: {org_name}
OVERALL AI READINESS SCORE: {overall_score}/10 ({maturity})

DIMENSION SCORES:
{scores_summary}

TOP USE CASES IDENTIFIED:
{use_cases_summary}

CRITICAL BLOCKERS:
{blockers}

Create a realistic 3-phase roadmap. Phase durations should reflect the organisation's 
maturity — a Nascent org needs longer foundation phases than an Advanced one.

Respond with ONLY valid JSON — an array of 3 phase objects:
[{{
  "phase": <1, 2, or 3>,
  "title": <evocative phase name>,
  "timeline": <e.g. "Months 1–3" or "Months 4–9">,
  "focus_areas": [<2-3 strategic focus areas>],
  "key_initiatives": [<4-5 specific initiatives to execute>],
  "success_metrics": [<3-4 measurable KPIs for this phase>,
  "dependencies": [<what must be true before this phase begins>]
}}]"""


SYNTHESIS_PROMPT = """You are a Chief AI Officer writing the executive summary for an AI Readiness Assessment.

ORGANISATION: {org_name}
OVERALL SCORE: {overall_score}/10 — {maturity} maturity

DIMENSION SCORES:
{scores_summary}

Write a concise executive summary (4-5 sentences) that:
1. States the overall readiness level and what it means for AI adoption
2. Highlights the 2 strongest dimensions
3. Calls out the 2 most critical gaps
4. Frames the opportunity ahead

Then provide:
- CRITICAL_BLOCKERS: 3-5 things that will prevent AI adoption if not addressed
- QUICK_WINS: 3-5 things that can be done in <90 days with high impact

Respond with ONLY valid JSON:
{{
  "executive_summary": <4-5 sentence summary>,
  "critical_blockers": [<blocker strings>],
  "quick_wins": [<quick win strings>]
}}"""


# ---------------------------------------------------------------------------
# Assessment Engine
# ---------------------------------------------------------------------------

class AssessmentEngine:

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)

    def _call_claude(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=settings.model,
            max_tokens=settings.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _parse_json(self, text: str) -> dict | list:
        """Extract and parse JSON from Claude's response."""
        text = text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = "\n".join(text.split("\n")[:-1])
        return json.loads(text.strip())

    def _retrieve_evidence(self, query: str, session_id: str) -> str:
        """Retrieve relevant document chunks for a query."""
        results = search_documents(query, session_id)
        if not results:
            return "No specific evidence found for this dimension."
        chunks = []
        for r in results[:6]:
            chunks.append(f"[Source: {r['source']}]\n{r['content'][:600]}")
        return "\n\n---\n\n".join(chunks)

    # ------------------------------------------------------------------
    # Step 1: Score each dimension
    # ------------------------------------------------------------------

    def assess_dimension(
        self,
        dimension: Dimension,
        session_id: str,
        additional_context: str = "",
    ) -> DimensionScore:
        logger.info(f"Assessing dimension: {dimension.value}")

        # Build a targeted query for this dimension
        query_map = {
            Dimension.DATA_READINESS:      "data quality data governance data pipeline data lake warehouse",
            Dimension.TECHNOLOGY_INFRA:    "cloud infrastructure API microservices DevOps MLOps platform",
            Dimension.TALENT_SKILLS:       "data scientist engineer AI skills training team capabilities",
            Dimension.PROCESS_AUTOMATION:  "automation workflow process efficiency RPA digital transformation",
            Dimension.GOVERNANCE_RISK:     "risk compliance policy governance regulation ethics AI policy",
            Dimension.STRATEGY_LEADERSHIP: "strategy leadership vision budget executive roadmap priority",
        }
        query = query_map.get(dimension, dimension.value)
        evidence = self._retrieve_evidence(query, session_id)

        prompt = DIMENSION_PROMPT.format(
            dimension=dimension.value,
            description=DIMENSION_DESCRIPTIONS[dimension],
            evidence=evidence,
            context=additional_context or "No additional context provided.",
        )

        raw = self._call_claude(prompt)
        parsed = self._parse_json(raw)

        score = float(parsed["score"])
        maturity, color, _ = get_maturity(score)

        return DimensionScore(
            dimension=dimension,
            score=round(score, 1),
            maturity_level=maturity,
            maturity_color=color,
            key_strengths=parsed.get("key_strengths", []),
            key_gaps=parsed.get("key_gaps", []),
            evidence_excerpts=parsed.get("evidence_excerpts", []),
            recommendations=parsed.get("recommendations", []),
        )

    # ------------------------------------------------------------------
    # Step 2: Identify use cases
    # ------------------------------------------------------------------

    def identify_use_cases(
        self,
        dimension_scores: list[DimensionScore],
        session_id: str,
        additional_context: str = "",
    ) -> list[UseCaseCandidate]:
        logger.info("Identifying use case candidates...")

        # Retrieve broad context about business processes
        context_chunks = search_documents("business process operations workflow department", session_id)
        context = "\n\n".join(r["content"][:500] for r in context_chunks[:5])

        scores_summary = "\n".join(
            f"- {s.dimension.value}: {s.score}/10 ({s.maturity_level})"
            for s in dimension_scores
        )

        prompt = USE_CASE_PROMPT.format(
            context=context or "Limited process documentation available.",
            scores_summary=scores_summary,
            additional_context=additional_context or "General enterprise context.",
        )

        raw = self._call_claude(prompt)
        parsed = self._parse_json(raw)

        use_cases = []
        for i, uc in enumerate(parsed[:5]):
            use_cases.append(UseCaseCandidate(
                title=uc["title"],
                description=uc["description"],
                business_process=uc["business_process"],
                ai_approach=uc["ai_approach"],
                estimated_complexity=uc["estimated_complexity"],
                estimated_roi_impact=uc["estimated_roi_impact"],
                prerequisites=uc.get("prerequisites", []),
                priority_rank=uc.get("priority_rank", i + 1),
            ))

        return sorted(use_cases, key=lambda x: x.priority_rank)

    # ------------------------------------------------------------------
    # Step 3: Synthesise executive summary + blockers
    # ------------------------------------------------------------------

    def synthesise(
        self,
        org_name: str,
        overall_score: float,
        overall_maturity: str,
        dimension_scores: list[DimensionScore],
    ) -> dict:
        logger.info("Synthesising executive summary...")

        scores_summary = "\n".join(
            f"- {s.dimension.value}: {s.score}/10 — Strengths: {', '.join(s.key_strengths[:2])}. "
            f"Gaps: {', '.join(s.key_gaps[:2])}."
            for s in dimension_scores
        )

        prompt = SYNTHESIS_PROMPT.format(
            org_name=org_name,
            overall_score=overall_score,
            maturity=overall_maturity,
            scores_summary=scores_summary,
        )

        raw = self._call_claude(prompt)
        return self._parse_json(raw)

    # ------------------------------------------------------------------
    # Step 4: Build roadmap
    # ------------------------------------------------------------------

    def build_roadmap(
        self,
        org_name: str,
        overall_score: float,
        overall_maturity: str,
        dimension_scores: list[DimensionScore],
        use_cases: list[UseCaseCandidate],
        critical_blockers: list[str],
    ) -> list[RoadmapPhase]:
        logger.info("Building adoption roadmap...")

        scores_summary = "\n".join(
            f"- {s.dimension.value}: {s.score}/10 ({s.maturity_level})"
            for s in dimension_scores
        )
        use_cases_summary = "\n".join(
            f"- [{uc.priority_rank}] {uc.title} ({uc.estimated_complexity} complexity, {uc.estimated_roi_impact} ROI)"
            for uc in use_cases
        )
        blockers = "\n".join(f"- {b}" for b in critical_blockers)

        prompt = ROADMAP_PROMPT.format(
            org_name=org_name,
            overall_score=overall_score,
            maturity=overall_maturity,
            scores_summary=scores_summary,
            use_cases_summary=use_cases_summary,
            blockers=blockers,
        )

        raw = self._call_claude(prompt)
        parsed = self._parse_json(raw)

        return [
            RoadmapPhase(
                phase=p["phase"],
                title=p["title"],
                timeline=p["timeline"],
                focus_areas=p.get("focus_areas", []),
                key_initiatives=p.get("key_initiatives", []),
                success_metrics=p.get("success_metrics", []),
                dependencies=p.get("dependencies", []),
            )
            for p in parsed
        ]

    # ------------------------------------------------------------------
    # Full assessment orchestrator
    # ------------------------------------------------------------------

    def run_full_assessment(
        self,
        session_id: str,
        org_name: str,
        extracted_docs: list[ExtractedDocument],
        additional_context: str = "",
        progress_callback=None,
    ) -> AssessmentReport:
        """
        Runs the complete 4-step assessment pipeline.
        Returns a fully populated AssessmentReport.
        """
        report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"

        # Step 1: Score all 6 dimensions
        dimension_scores = []
        dimensions = list(Dimension)
        for i, dim in enumerate(dimensions):
            if progress_callback:
                pct = 45 + int((i / len(dimensions)) * 35)
                progress_callback(f"Analysing: {dim.value}...", pct)
            score = self.assess_dimension(dim, session_id, additional_context)
            dimension_scores.append(score)

        # Overall score = weighted average (equal weights for now)
        overall_score = round(sum(s.score for s in dimension_scores) / len(dimension_scores), 1)
        overall_maturity, overall_color, _ = get_maturity(overall_score)

        if progress_callback:
            progress_callback("Identifying AI use case candidates...", 82)

        # Step 2: Use cases
        use_cases = self.identify_use_cases(dimension_scores, session_id, additional_context)

        if progress_callback:
            progress_callback("Synthesising executive summary...", 88)

        # Step 3: Synthesis
        synthesis = self.synthesise(org_name, overall_score, overall_maturity, dimension_scores)

        if progress_callback:
            progress_callback("Building adoption roadmap...", 93)

        # Step 4: Roadmap
        roadmap = self.build_roadmap(
            org_name=org_name,
            overall_score=overall_score,
            overall_maturity=overall_maturity,
            dimension_scores=dimension_scores,
            use_cases=use_cases,
            critical_blockers=synthesis.get("critical_blockers", []),
        )

        if progress_callback:
            progress_callback("Finalising report...", 98)

        return AssessmentReport(
            report_id=report_id,
            organisation_name=org_name,
            documents_analysed=[doc.filename for doc in extracted_docs],
            total_pages_analysed=sum(doc.page_count for doc in extracted_docs),
            overall_score=overall_score,
            overall_maturity=overall_maturity,
            overall_maturity_color=overall_color,
            executive_summary=synthesis.get("executive_summary", ""),
            dimension_scores=dimension_scores,
            use_case_candidates=use_cases,
            roadmap_phases=roadmap,
            critical_blockers=synthesis.get("critical_blockers", []),
            quick_wins=synthesis.get("quick_wins", []),
        )
