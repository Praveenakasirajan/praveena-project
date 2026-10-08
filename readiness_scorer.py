"""
readiness_scorer.py - Deterministic, explainable Interview Readiness Score calculation.
Aggregates technical mastery, communication clarity, problem-solving, delivery confidence,
and multi-question consistency into an authoritative 0-100 readiness benchmark.
"""

from typing import Dict, Any, List, Optional
import numpy as np


def calculate_interview_readiness(
    question_evaluations: List[Dict[str, Any]],
    video_metrics_list: Optional[List[Dict[str, Any]]] = None,
    communication_metrics_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Calculate an explainable Interview Readiness Score (0 - 100) based on verified performance metrics.

    Formula / Weighting:
    --------------------
    1. Technical Competence (35%):
       Average technical scores (0-10 scaled to 0-100) across domain & resume questions.
    2. Communication & Articulation (25%):
       Average communication scores (0-10) factoring in WPM cadence and filler-word control.
    3. Problem Solving & Structural Rigor (20%):
       Average problem-solving / STAR structure scores (0-10).
    4. Delivery Confidence & Presence (10%):
       Eye contact, head stability, and camera engagement from video analysis (0-10).
    5. Multi-Question Consistency (10%):
       Penalizes wild variances across questions (std deviation), rewarding steady performance.

    Levels:
    - 85 - 100: "Strong" (Ready for top-tier corporate & engineering rounds)
    - 70 - 84 : "Good" (Solid core skills; ready for technical screens with minor polish)
    - 50 - 69 : "Developing" (Developing competence; needs deeper domain clarity)
    - 0  - 49 : "Needs Improvement" (Requires foundational review before interviews)
    """
    if not question_evaluations:
        return {
            "readiness_score": 0.0,
            "readiness_level": "Needs Improvement",
            "readiness_summary": "No answers evaluated yet in this session.",
            "components": {
                "technical": 0.0,
                "communication": 0.0,
                "problem_solving": 0.0,
                "confidence": 0.0,
                "consistency": 0.0,
            },
            "formula_explanation": "Technical (35%) + Communication (25%) + Problem Solving (20%) + Confidence (10%) + Consistency (10%)"
        }

    # Extract component scores from evaluations
    tech_scores = [float(e.get("technical_score", 0.0)) * 10 for e in question_evaluations]
    comm_scores = [float(e.get("communication_score", 0.0)) * 10 for e in question_evaluations]
    ps_scores = [float(e.get("problem_solving_score", 0.0)) * 10 for e in question_evaluations]
    conf_scores = [float(e.get("confidence_score", 7.0)) * 10 for e in question_evaluations]
    overall_scores = [float(e.get("overall_score", 0.0)) for e in question_evaluations]

    avg_tech = float(np.mean(tech_scores)) if tech_scores else 0.0
    avg_comm = float(np.mean(comm_scores)) if comm_scores else 0.0
    avg_ps = float(np.mean(ps_scores)) if ps_scores else 0.0
    avg_conf = float(np.mean(conf_scores)) if conf_scores else 70.0

    # Consistency factor: standard deviation penalty
    if len(overall_scores) > 1:
        score_std = float(np.std(overall_scores))
        # Std dev between 0 and 25 maps to consistency 100 down to 50
        consistency_score = max(50.0, min(100.0, 100.0 - (score_std * 2.0)))
    else:
        consistency_score = 85.0  # Neutral baseline for single question

    # Factor in video metrics if available
    if video_metrics_list:
        eye_contacts = [float(v.get("eye_contact_score", 7.0)) * 10 for v in video_metrics_list if v]
        if eye_contacts:
            avg_conf = float(np.mean(eye_contacts))

    # Factor in communication metrics (WPM and fillers)
    if communication_metrics_list:
        wpm_penalties = 0.0
        for c in communication_metrics_list:
            if not c:
                continue
            rate = float(c.get("filler_rate_percent", 0.0))
            if rate > 6.0:
                wpm_penalties += 5.0
        avg_comm = max(0.0, avg_comm - (wpm_penalties / max(1, len(communication_metrics_list))))

    # Weighted calculation
    weighted_score = (
        (avg_tech * 0.35) +
        (avg_comm * 0.25) +
        (avg_ps * 0.20) +
        (avg_conf * 0.10) +
        (consistency_score * 0.10)
    )

    final_score = round(max(0.0, min(100.0, weighted_score)), 1)

    # Classification
    if final_score >= 85.0:
        level = "Strong"
        summary = "Interview-ready with strong technical accuracy, structured articulation, and confident presence."
    elif final_score >= 70.0:
        level = "Good"
        summary = "Competitive interview performance. Demonstrates solid core concepts with room for sharper structure and deeper technical examples."
    elif final_score >= 50.0:
        level = "Developing"
        summary = "Foundational knowledge is present, but responses lack depth, clarity, or consistent pacing across questions."
    else:
        level = "Needs Improvement"
        summary = "Significant preparation needed. Focus on reviewing core computer science concepts, structured STAR answering, and reducing hesitation."

    return {
        "readiness_score": final_score,
        "readiness_level": level,
        "readiness_summary": summary,
        "components": {
            "technical": round(avg_tech, 1),
            "communication": round(avg_comm, 1),
            "problem_solving": round(avg_ps, 1),
            "confidence": round(avg_conf, 1),
            "consistency": round(consistency_score, 1),
        },
        "formula_explanation": "Technical (35%) + Communication (25%) + Problem Solving (20%) + Delivery Confidence (10%) + Consistency (10%)",
    }
