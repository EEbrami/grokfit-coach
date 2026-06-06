"""Tools package for grokfit-coach.

The agent binds these LangChain tools.
"""

from .exercise import search_exercises
from .nutrition import calculate_macros, lookup_nutrition

# The exact list the agent will bind (order matters less)
TOOLS = [search_exercises, lookup_nutrition, calculate_macros]

__all__ = ["TOOLS", "search_exercises", "lookup_nutrition", "calculate_macros"]
