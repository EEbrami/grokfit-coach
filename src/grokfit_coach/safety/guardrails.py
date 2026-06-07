"""Rule-based safety guardrails for the coach agent.

Defense in depth:
- Pre-filter (is_unsafe_request) — called early in the graph, can short-circuit.
- Post-processing (apply_output_guardrails) — forces the disclaimer on every final answer.

These are intentionally simple and deterministic for Phase 1 (no LLM trust for safety).
"""

from __future__ import annotations

import re

DISCLAIMER: str = (
    "IMPORTANT DISCLAIMER: This is general educational information only and is NOT a "
    "substitute for professional medical, nutritional, or fitness advice. Consult a "
    "qualified healthcare provider or certified trainer before beginning any new "
    "exercise or diet program. Stop immediately if you experience pain or discomfort."
)

# Simple keyword / phrase patterns (case-insensitive). Expand conservatively.
_UNSAFE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(steroid|anabolic|clenbuterol|dnp|tren|testosterone cycle)\b", re.I),
    re.compile(r"lose\s*\d+\s*(lb|lbs|kg|kgs|pound|pounds)\s*(in|within)\s*\d+\s*(day|days|week|weeks)", re.I),
    re.compile(r"(starve|fast for|no food|only water)\s*(for|to lose)", re.I),
    re.compile(r"\b(push through (the )?pain|no pain no gain)\b", re.I),
    re.compile(r"(diagnos(e|is)|cure|treat|fix my (injury|condition|back|knee|shoulder))", re.I),
    re.compile(r"\b(how (much|to get) (steroids|clen|gear)|recommend (steroids|peds))\b", re.I),
    re.compile(r"\b(doctor said|ignore (my )?doctor|my physio said no but)\b", re.I),
]


def is_unsafe_request(text: str) -> str | None:
    """Return a short reason if the request looks unsafe, otherwise None."""
    if not text or not text.strip():
        return None
    lowered = text.lower()
    for pat in _UNSAFE_PATTERNS:
        if pat.search(lowered):
            return "Request appears to ask for unsafe or medical advice. I cannot assist with that."
    # Extra heuristic: injury/pain + training request. Catch both absence of pro language AND explicit dismissal ("no doctor needed").
    injury_words = any(w in lowered for w in ["injur", "hurt", "pain", "tendon", "shoulder", "knee", "back pain"])
    program_words = any(w in lowered for w in ["program", "plan", "exercise", "squat", "workout", "lift"])
    if injury_words and program_words:
        explicit_dismissal = any(phrase in lowered for phrase in ["no doctor", "don't need doctor", "no need for a doctor", "ignore doctor"])
        no_positive_pro = all(w not in lowered for w in ["consult", "see a doctor", "physio", "professional", "qualified", "medical clearance"])
        if explicit_dismissal or no_positive_pro:
            return "Injury-related advice requires a medical professional. I can only give very general information."
    return None


def apply_output_guardrails(text: str) -> str:
    """Ensure the standard disclaimer is present in the final output."""
    if not text:
        return DISCLAIMER
    if DISCLAIMER.lower() in text.lower():
        return text
    # Append cleanly
    separator = "\n\n" if not text.endswith("\n") else "\n"
    return text.rstrip() + separator + DISCLAIMER
