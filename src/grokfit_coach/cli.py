"""Thin terminal interface for the GrokFit Coach agent.

This is the primary "runnable basic version" for Phase 1.

Usage examples:
    python -m grokfit_coach.cli
    python -m grokfit_coach.cli --query "Suggest chest exercises with dumbbells"
    grokfit-coach --profile data/seeds/example_profile.json --query "create a 3 day plan"

Profile is loaded from persisted ~/.grokfit/profile.json by default (or EXAMPLE if none).
Last generated plans are auto-saved to ~/.grokfit/last_plan.json for the Plans tab / --query flows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage

from grokfit_coach.agents.graph import build_coach_graph
from grokfit_coach.models import UserProfile
from grokfit_coach.persistence import get_current_profile, save_plan


def load_profile_from_path(path: str | None) -> UserProfile:
    """Load from explicit JSON path (for --profile override). Falls back to persisted or example."""
    if not path:
        return get_current_profile()
    p = Path(path)
    if not p.exists():
        print(f"Profile file not found: {path}. Falling back to persisted or example profile.", file=sys.stderr)
        return get_current_profile()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return UserProfile.model_validate(data)
    except Exception:
        print(f"Failed to load profile from {path}. Falling back.", file=sys.stderr)
        return get_current_profile()


def _apply_llm_overrides(profile: UserProfile, args) -> UserProfile:
    """Apply --provider/--model/--api-key-env overrides to the profile and warn as needed."""
    from grokfit_coach.llm import egress_warning, plan_capability_warning

    updates: dict = {}
    if getattr(args, "provider", None):
        updates["provider"] = args.provider
    if getattr(args, "model", None):
        updates["model"] = args.model
    if getattr(args, "api_key_env", None):
        updates["api_key_ref"] = args.api_key_env
    if updates:
        new_cfg = profile.llm_config.model_copy(update=updates)
        profile = profile.model_copy(update={"llm_config": new_cfg})

    warn = egress_warning(profile.llm_config)
    if warn:
        print(f"\n⚠️  {warn}\n", file=sys.stderr)
    cap = plan_capability_warning(profile.llm_config)
    if cap:
        print(f"Note: {cap}", file=sys.stderr)
    return profile


def format_plan(plan) -> str:
    if not plan:
        return ""
    lines = [f"\n=== Weekly Plan for {plan.athlete_name} (goal: {plan.goal}) ==="]
    for d in plan.days:
        lines.append(f"\n{d.day} — {d.focus}")
        for ex in d.exercises:
            sets = ex.sets or "3"
            reps = ex.reps or "8-12"
            note = f" — {ex.notes}" if ex.notes else ""
            lines.append(f"  • {ex.name}: {sets} × {reps}{note}")
    if plan.notes:
        lines.append(f"\nNotes: {plan.notes}")
    lines.append(f"\n{plan.disclaimer}")
    return "\n".join(lines)


def run_repl(graph, profile: UserProfile) -> None:
    print("GrokFit Coach (100% local via Ollama)")
    print(f"Profile: {profile.name} | Goal: {profile.goal} | Level: {profile.fitness_level}")
    print("Equipment:", profile.available_equipment or "minimal/bodyweight")
    print("Type your question. Type 'plan' for a weekly workout suggestion. Type 'quit' or Ctrl-D to exit.\n")

    state = {"messages": [], "profile": profile, "plan": None, "safety_refusal": None}

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break

        state["messages"].append(HumanMessage(content=user))
        try:
            state = graph.invoke(state)
        except Exception as e:
            print("Error talking to Ollama:", e)
            print("Make sure `ollama serve` is running and you have pulled the model (`ollama pull llama3.1`).")
            # pop the bad message so the loop can continue
            if state["messages"]:
                state["messages"].pop()
            continue

        last = state["messages"][-1] if state.get("messages") else None
        if last:
            print("Coach:", getattr(last, "content", str(last)))

        if state.get("plan"):
            print(format_plan(state["plan"]))
            try:
                save_plan(state["plan"])
            except Exception:
                pass
            # clear so we don't reprint on next turn unless newly generated
            state["plan"] = None


def main() -> None:
    parser = argparse.ArgumentParser(description="GrokFit Coach - local terminal agent")
    parser.add_argument("--profile", type=str, default=None, help="Path to a UserProfile JSON file")
    parser.add_argument("--query", type=str, default=None, help="Single query (non-interactive)")
    parser.add_argument("--model", type=str, default=None, help="Override the LLM model id (e.g. qwen2.5, llama3.1)")
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="LLM provider: ollama (default, local) | google_genai | groq | openai | anthropic | mistralai | openrouter",
    )
    parser.add_argument(
        "--api-key-env",
        type=str,
        default=None,
        dest="api_key_env",
        help="Name of the ENV VAR holding your API key (cloud providers only; the key is never stored)",
    )
    args = parser.parse_args()

    profile = load_profile_from_path(args.profile)
    profile = _apply_llm_overrides(profile, args)
    graph = build_coach_graph()

    if args.query:
        # One-shot mode (useful for demos and quick checks)
        init = {
            "messages": [HumanMessage(content=args.query)],
            "profile": profile,
            "plan": None,
            "safety_refusal": None,
        }
        try:
            out = graph.invoke(init)
        except Exception as e:
            print("Failed to reach Ollama:", e, file=sys.stderr)
            print("Start Ollama and pull a model, e.g. `ollama serve` and `ollama pull llama3.1`", file=sys.stderr)
            sys.exit(1)

        last = out["messages"][-1] if out.get("messages") else None
        if last:
            print(getattr(last, "content", str(last)))
        if out.get("plan"):
            print(format_plan(out["plan"]))
            try:
                save_plan(out["plan"])
            except Exception:
                pass  # non-fatal
        return

    # Interactive REPL (the main Phase 1 experience)
    run_repl(graph, profile)


if __name__ == "__main__":
    main()
