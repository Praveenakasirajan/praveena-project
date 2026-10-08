"""
communication_analyzer.py - Objective, measurable communication metrics for candidate answers.
Calculates words per minute, speech duration, filler-word frequency, and cadence feedback.
Strictly objective: NO accent scoring or subjective phonetic penalties.
"""

import re
from typing import Dict, Any, List, Optional

# Standard filler words and phrases observed in spoken English interviews
COMMON_FILLER_WORDS = [
    r"\bum+\b",
    r"\buh+\b",
    r"\bah+\b",
    r"\blike\b",
    r"\byou know\b",
    r"\bactually\b",
    r"\bbasically\b",
    r"\bso yeah\b",
    r"\bsort of\b",
    r"\bkind of\b",
    r"\bi mean\b",
    r"\bliterally\b",
    r"\bright\b",
]

COMPILED_FILLER_PATTERNS = [re.compile(p, re.IGNORECASE) for p in COMMON_FILLER_WORDS]


def analyze_communication(
    transcript: str,
    duration_seconds: float,
    filler_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """
    Compute objective, verifiable communication metrics from transcript and audio duration.
    
    Metrics:
    - duration_seconds: total spoken duration
    - word_count: total words in transcript
    - words_per_minute (WPM): words / (duration / 60)
    - filler_words_count: occurrences of verbal fillers
    - filler_rate_percent: (filler_count / word_count) * 100
    - pacing_rating: 'Optimal', 'Slightly Slow', 'Too Slow', 'Slightly Fast', 'Too Fast'
    - filler_control_rating: 'Excellent', 'Good', 'Moderate', 'High Filler Usage'
    """
    clean_text = (transcript or "").strip()
    words = re.findall(r"\b[A-Za-z0-9+#.-]+\b", clean_text)
    word_count = len(words)
    dur = max(float(duration_seconds or 0.0), 0.5)

    # Words Per Minute
    minutes = dur / 60.0
    wpm = round(word_count / minutes, 1) if minutes > 0 else 0.0

    # Filler words detection
    filler_occurrences = []
    total_fillers = 0
    for pat in COMPILED_FILLER_PATTERNS:
        matches = pat.findall(clean_text)
        if matches:
            total_fillers += len(matches)
            filler_occurrences.append({
                "filler": matches[0].lower(),
                "count": len(matches)
            })

    filler_rate = round((total_fillers / word_count * 100), 1) if word_count > 0 else 0.0

    # Pacing assessment based on standard presentation guidelines (120 - 160 WPM optimal)
    if word_count < 5:
        pacing_rating = "Insufficient Speech"
        pacing_feedback = "Answer was too brief to measure speech cadence accurately."
    elif 120 <= wpm <= 165:
        pacing_rating = "Optimal"
        pacing_feedback = f"Ideal interview speaking pace ({wpm:.0f} WPM). Clear and easy to follow."
    elif 100 <= wpm < 120:
        pacing_rating = "Slightly Deliberate"
        pacing_feedback = f"Pace is slightly deliberate ({wpm:.0f} WPM), which can aid clarity for technical answers."
    elif wpm < 100:
        pacing_rating = "Slow"
        pacing_feedback = f"Speaking pace is slow ({wpm:.0f} WPM). Aim for a slightly faster flow between 120-150 WPM."
    elif 165 < wpm <= 185:
        pacing_rating = "Slightly Fast"
        pacing_feedback = f"Pace is brisk ({wpm:.0f} WPM). Ensure key technical explanations are given adequate emphasis."
    else:
        pacing_rating = "Too Fast"
        pacing_feedback = f"Speaking pace is rapid ({wpm:.0f} WPM). Slow down slightly to maintain clarity and composure."

    # Filler word rating
    if total_fillers == 0 or filler_rate < 2.0:
        filler_control_rating = "Excellent"
        filler_feedback = "Minimal or no verbal fillers detected. Highly articulate."
    elif filler_rate < 4.5:
        filler_control_rating = "Good"
        filler_feedback = f"Low filler usage ({total_fillers} detected, {filler_rate:.1f}%). Very natural delivery."
    elif filler_rate < 8.0:
        filler_control_rating = "Moderate"
        filler_feedback = f"Moderate filler usage ({total_fillers} detected, {filler_rate:.1f}%). Pause silently instead of using filler words."
    else:
        filler_control_rating = "Needs Attention"
        filler_feedback = f"Frequent filler usage ({total_fillers} detected, {filler_rate:.1f}%). Practice replacing 'like/um' with brief thoughtful pauses."

    return {
        "duration_seconds": round(dur, 1),
        "word_count": word_count,
        "words_per_minute": wpm,
        "filler_words_count": total_fillers,
        "filler_rate_percent": filler_rate,
        "filler_breakdown": sorted(filler_occurrences, key=lambda x: x["count"], reverse=True),
        "pacing_rating": pacing_rating,
        "pacing_feedback": pacing_feedback,
        "filler_control_rating": filler_control_rating,
        "filler_feedback": filler_feedback,
    }
