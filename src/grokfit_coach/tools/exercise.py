"""Exercise search tool (RAG-backed)."""

from __future__ import annotations

from langchain_core.tools import tool

from grokfit_coach.rag.retriever import retrieve_exercises


@tool("search_exercises", return_direct=False)
def search_exercises(
    query: str,
    equipment: str | None = None,
    muscle_group: str | None = None,
) -> str:
    """Search the curated exercise database for movements matching the query.

    Use this tool whenever the user asks for exercise recommendations, variations,
    or "what should I do for X muscle".

    You can optionally filter by equipment the user has (e.g. "dumbbells", "none")
    or target muscle group ("chest", "legs").

    Returns a short list of relevant exercises with key details.
    """
    filters = {}
    if equipment:
        filters["equipment"] = equipment
    if muscle_group:
        filters["muscle"] = muscle_group

    results = retrieve_exercises(query, k=5)
    if not results:
        return "No matching exercises found in the knowledge base."

    lines = []
    for ex in results:
        equip = ", ".join(ex.equipment) if ex.equipment else "bodyweight/none"
        lines.append(
            f"- {ex.name} (difficulty: {ex.difficulty}, equipment: {equip})\n"
            f"  Muscles: {', '.join(ex.muscle_groups)}\n"
            f"  {ex.description[:120]}{'...' if len(ex.description) > 120 else ''}"
        )
    return "Relevant exercises from the local knowledge base:\n" + "\n".join(lines)
