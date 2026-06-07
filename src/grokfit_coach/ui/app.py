"""Gradio UI for grokfit-coach (Phase 2).

Tabs:
- Profile: edit/save UserProfile (persisted)
- Coach Chat: interactive conversation with the agent (safety enforced)
- Plans: view/generate improved weekly workout plans

The UI is a thin, local-only layer on top of the Phase 1 agent (`invoke_coach`).
The terminal CLI (`grokfit-coach`) remains fully functional and unaffected.
"""

from __future__ import annotations

import gradio as gr

from grokfit_coach.agents.graph import invoke_coach
from grokfit_coach.models import UserProfile
from grokfit_coach.persistence import get_current_profile, load_plan, save_plan, save_profile
from grokfit_coach.safety.guardrails import DISCLAIMER


def _profile_to_form_values(profile: UserProfile) -> dict:
    """Convert profile to values suitable for Gradio components."""
    return {
        "name": profile.name,
        "age": profile.age,
        "gender": profile.gender,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "goal": profile.goal,
        "fitness_level": profile.fitness_level,
        "available_equipment": profile.available_equipment or [],
        "dietary_restrictions": profile.dietary_restrictions or [],
        "injuries_or_limitations": profile.injuries_or_limitations or [],
        "dietary_pattern": profile.dietary_pattern,
        "allergens": ", ".join(profile.allergens or []),
        "food_preferences": ", ".join(profile.food_preferences or []),
        "disliked_foods": ", ".join(profile.disliked_foods or []),
        "meals_per_day": profile.meals_per_day,
        "workout_days_per_week": profile.workout_days_per_week,
        "session_duration_min": profile.session_duration_min,
        "llm_provider": profile.llm_config.provider,
        "llm_model": profile.llm_config.model,
        "llm_api_key_ref": profile.llm_config.api_key_ref or "",
    }


def _form_values_to_profile(values: dict) -> UserProfile:
    """Build and validate a UserProfile from form values."""
    from grokfit_coach.models import LLMConfig

    llm_config = LLMConfig(
        provider=values.get("llm_provider") or "ollama",
        model=values.get("llm_model") or "llama3.1",
        api_key_ref=(values.get("llm_api_key_ref") or None),
    )
    return UserProfile(
        name=values.get("name", "User"),
        age=int(values.get("age", 30)),
        gender=values.get("gender", "prefer_not"),
        height_cm=float(values.get("height_cm", 170)),
        weight_kg=float(values.get("weight_kg", 70)),
        goal=values.get("goal", "general_health"),
        fitness_level=values.get("fitness_level", "novice"),
        available_equipment=values.get("available_equipment", []),
        dietary_restrictions=values.get("dietary_restrictions", []),
        injuries_or_limitations=values.get("injuries_or_limitations", []),
        dietary_pattern=values.get("dietary_pattern") or "omnivore",
        allergens=values.get("allergens") or [],
        food_preferences=values.get("food_preferences") or [],
        disliked_foods=values.get("disliked_foods") or [],
        meals_per_day=int(values.get("meals_per_day", 3)),
        workout_days_per_week=int(values.get("workout_days_per_week", 3)),
        session_duration_min=int(values.get("session_duration_min", 45)),
        llm_config=llm_config,
    )


def load_saved_profile() -> tuple[dict, str]:
    """Load persisted profile and return form values + status message."""
    profile = get_current_profile()
    return _profile_to_form_values(profile), f"Loaded profile for {profile.name} (persisted or default)."


def save_profile_from_form(*args) -> tuple[dict | None, str]:
    """Validate form, save to persistence, return profile state + status."""
    keys = [
        "name", "age", "gender", "height_cm", "weight_kg",
        "goal", "fitness_level", "available_equipment",
        "dietary_restrictions", "injuries_or_limitations",
        "dietary_pattern", "allergens", "food_preferences", "disliked_foods", "meals_per_day",
        "workout_days_per_week", "session_duration_min",
        "llm_provider", "llm_model", "llm_api_key_ref",
    ]
    values = dict(zip(keys, args))
    try:
        profile = _form_values_to_profile(values)
        save_profile(profile)
        from grokfit_coach.llm import egress_warning, plan_capability_warning

        extra = ""
        warn = egress_warning(profile.llm_config)
        if warn:
            extra += f"\n⚠️ {warn}"
        cap = plan_capability_warning(profile.llm_config)
        if cap:
            extra += f"\nNote: {cap}"
        return _profile_to_form_values(profile), f"✅ Profile saved for {profile.name}. Available in chat and plan generation.{extra}"
    except Exception as e:
        return None, f"❌ Failed to save profile: {e}"


def chat_response(message: str, history: list, profile_state: dict | None):
    """Handle a chat turn using the Phase 1 agent."""
    if not message or not message.strip():
        return history, profile_state

    # Load current profile (prefer state, fall back to persistence)
    if profile_state:
        try:
            profile = _form_values_to_profile(profile_state)
        except Exception:
            profile = get_current_profile()
    else:
        profile = get_current_profile()

    try:
        result = invoke_coach(profile, message.strip())
        assistant_msg = ""
        if result.get("messages"):
            last = result["messages"][-1]
            assistant_msg = getattr(last, "content", str(last)) or ""
        if result.get("plan"):
            assistant_msg += "\n\n" + _format_plan_for_chat(result["plan"])

        # Always ensure disclaimer is visible (guardrails already add it, but be defensive)
        if DISCLAIMER not in assistant_msg:
            assistant_msg = assistant_msg.rstrip() + "\n\n" + DISCLAIMER

        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": assistant_msg},
        ]
    except Exception as e:
        error_msg = f"Error contacting the local agent: {e}. Is Ollama running with the right model?"
        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": error_msg},
        ]

    return history, profile_state


def _format_plan_for_chat(plan) -> str:
    if not plan or not getattr(plan, "days", None):
        return ""
    lines = [f"**Generated Plan for {plan.athlete_name} ({plan.goal})**"]
    for d in plan.days:
        lines.append(f"\n**{d.day} — {d.focus}**")
        for ex in d.exercises:
            sets = getattr(ex, "sets", "3") or "3"
            reps = getattr(ex, "reps", "8-12") or "8-12"
            note = f" — {getattr(ex, 'notes', '')}" if getattr(ex, "notes", None) else ""
            lines.append(f"- {ex.name}: {sets} × {reps}{note}")
    if getattr(plan, "notes", None):
        lines.append(f"\n_Notes: {plan.notes}_")
    lines.append(f"\n{plan.disclaimer}")
    return "\n".join(lines)


def _format_nutrition_plan_for_display(plan) -> str:
    if not plan or not getattr(plan, "days", None):
        return ""
    lines = []
    t = getattr(plan, "daily_targets", None)
    if t:
        lines.append(
            f"**Daily target:** ~{round(t.calories)} kcal · "
            f"P {round(t.protein_g)}g / C {round(t.carbs_g)}g / F {round(t.fat_g)}g"
        )
    for d in plan.days:
        lines.append(f"\n**{d.day}**")
        for meal in d.meals:
            lines.append(f"\n_{meal.name}_")
            for it in meal.items:
                grams = f"{round(it.grams)}g " if it.grams else ""
                macro = (
                    f" — {round(it.calories or 0)} kcal (P{round(it.protein_g or 0)}/C{round(it.carbs_g or 0)}/F{round(it.fat_g or 0)})"
                    if it.calories is not None
                    else ""
                )
                lines.append(f"- {grams}{it.name}{macro}")
    if getattr(plan, "notes", None):
        lines.append(f"\n_{plan.notes}_")
    return "\n".join(lines)


def generate_plan(profile_state: dict | None):
    """Generate BOTH a workout plan and a nutrition plan from the current profile."""
    if profile_state:
        try:
            profile = _form_values_to_profile(profile_state)
        except Exception:
            profile = get_current_profile()
    else:
        profile = get_current_profile()

    sections: list[str] = []
    done: list[str] = []

    # --- Workout plan (robust assembly via the agent graph) ---
    try:
        result = invoke_coach(profile, "Please create a weekly workout plan for me based on my profile.")
        wplan = result.get("plan")
        if wplan:
            save_plan(wplan)
            sections.append("## 🏋️ Workout Plan\n" + _format_plan_for_chat(wplan))
            done.append("workout ✓")
    except Exception as e:
        sections.append(f"## 🏋️ Workout Plan\n_Error: {e} (is Ollama running?)_")

    # --- Nutrition plan (deterministic, allergen-safe, grounded in the food DB) ---
    try:
        from grokfit_coach.nutrition.meal_planner import generate_nutrition_plan
        from grokfit_coach.persistence import save_nutrition_plan

        nplan = generate_nutrition_plan(profile)
        save_nutrition_plan(nplan)
        sections.append("\n\n---\n\n## 🥗 Nutrition Plan\n" + _format_nutrition_plan_for_display(nplan))
        done.append("nutrition ✓")
    except Exception as e:
        sections.append(f"\n\n---\n\n## 🥗 Nutrition Plan\n_Error: {e}_")

    if not sections:
        return "No plan produced. Check your profile and that Ollama is running.", "Nothing generated."
    status = f"Generated for {profile.name}: {', '.join(done)}." if done else "Generation had errors (see above)."
    return "\n".join(sections), status


def launch():
    """Launch the Gradio UI. Call this from console script or `python -m ...`."""
    with gr.Blocks(title="GrokFit Coach (Local)", theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            "# 🏋️ GrokFit Coach\n"
            "**100% local • Ollama + LangGraph • Privacy-first**\n\n"
            f"**{DISCLAIMER}**"
        )

        # Shared state
        profile_state = gr.State(value=None)

        with gr.Tab("Profile"):
            gr.Markdown("### Edit & Save Your Profile\nChanges are persisted locally and used by Chat and Plans.")
            with gr.Row():
                name = gr.Textbox(label="Name", value="Abraham")
                age = gr.Number(label="Age", value=30, precision=0)
                gender = gr.Dropdown(["male", "female", "other", "prefer_not"], label="Gender", value="male")
            with gr.Row():
                height = gr.Number(label="Height (cm)", value=178)
                weight = gr.Number(label="Weight (kg)", value=93)
            goal = gr.Dropdown(
                ["fat_loss", "muscle_gain", "strength", "general_health", "endurance", "body_recomposition"],
                label="Primary Goal",
                value="fat_loss",
            )
            fitness = gr.Dropdown(
                ["beginner", "novice", "intermediate", "advanced"],
                label="Fitness Level",
                value="intermediate",
            )
            equipment = gr.CheckboxGroup(
                ["dumbbells", "none", "resistance_bands", "barbells", "pullup_bar", "full_gym", "cardio_machine"],
                label="Available Equipment",
                value=["dumbbells", "none", "resistance_bands"],
            )
            restrictions = gr.Textbox(label="Dietary Restrictions (comma-separated)", value="")
            injuries = gr.Textbox(label="Injuries / Limitations (comma-separated)", value="")

            gr.Markdown("### Nutrition (used for your meal plan)")
            with gr.Row():
                dietary_pattern = gr.Dropdown(
                    ["omnivore", "vegetarian", "vegan", "pescatarian", "keto", "paleo", "halal", "kosher", "other"],
                    label="Dietary Pattern",
                    value="omnivore",
                )
                meals = gr.Slider(1, 6, step=1, label="Meals / Day", value=3)
            allergens = gr.Textbox(
                label="⚠️ Allergens (comma-separated) — ALWAYS excluded from your meal plan",
                placeholder="e.g. peanut, shellfish, milk, gluten",
                value="",
            )
            food_prefs = gr.Textbox(label="Preferred Foods (comma-separated)", value="")
            disliked = gr.Textbox(label="Disliked Foods (comma-separated)", value="")

            with gr.Row():
                days = gr.Slider(1, 7, step=1, label="Training Days / Week", value=4)
                duration = gr.Slider(20, 120, step=5, label="Typical Session (minutes)", value=50)

            gr.Markdown("### Model (LLM) — local by default")
            with gr.Row():
                llm_provider = gr.Dropdown(
                    ["ollama", "google_genai", "groq", "openai", "anthropic", "mistralai", "openrouter"],
                    label="Provider (ollama = 100% local)",
                    value="ollama",
                )
                llm_model = gr.Dropdown(
                    ["qwen2.5", "qwen2.5:14b", "llama3.1", "qwen3", "qwen3.5", "gemma4", "mistral-nemo"],
                    label="Model",
                    value="llama3.1",
                    allow_custom_value=True,
                )
            llm_api_key_ref = gr.Textbox(
                label="API key ENV VAR name (cloud only; the key itself is never stored)",
                placeholder="e.g. GEMINI_API_KEY",
                value="",
            )
            gr.Markdown(
                "_Local **ollama** keeps everything on your device. Choosing a **cloud** provider sends your "
                "messages (profile, injuries, dietary info) off-device — opt-in only. Recommended local models for "
                "reliable plans: **qwen2.5**, **llama3.1**, **gemma4** (Gemma 2/3 are too weak for plans)._"
            )

            with gr.Row():
                load_btn = gr.Button("Load Saved Profile")
                save_btn = gr.Button("Save Profile", variant="primary")
            status = gr.Textbox(label="Status", interactive=False)

            # Wire profile tab
            load_btn.click(
                load_saved_profile,
                outputs=[profile_state, status],
            ).then(
                lambda p: (p or {}),
                inputs=[profile_state],
                outputs=[profile_state],  # keep state in sync
            )

            save_btn.click(
                save_profile_from_form,
                inputs=[name, age, gender, height, weight, goal, fitness, equipment, restrictions, injuries, dietary_pattern, allergens, food_prefs, disliked, meals, days, duration, llm_provider, llm_model, llm_api_key_ref],
                outputs=[profile_state, status],
            )

            # Initialize on load
            demo.load(load_saved_profile, outputs=[profile_state, status])

        with gr.Tab("Coach Chat"):
            gr.Markdown("### Chat with the Local Agent\nYour current profile (from Profile tab or persisted) is used automatically. Safety guardrails are always active.")
            chatbot = gr.Chatbot(height=400)
            msg = gr.Textbox(placeholder="Ask about exercises, nutrition, or say 'create a 4-day plan for fat loss with dumbbells'", label="Your message")
            gr.ClearButton([chatbot, msg])

            def _submit_and_update(message, history, pstate):
                new_hist, _ = chat_response(message, history, pstate)
                return new_hist, ""

            msg.submit(
                _submit_and_update,
                inputs=[msg, chatbot, profile_state],
                outputs=[chatbot, msg],
            )

        with gr.Tab("Plans"):
            gr.Markdown(
                "### Your Workout + Nutrition Plans\n"
                "Generates **both** a weekly workout plan (full days, your equipment, injury-aware) and a "
                "**nutrition plan** (macro targets + meals built only from foods that respect your allergens & "
                "dietary pattern). Set your profile first, then click below."
            )
            plan_display = gr.Markdown("No plan generated yet. Click the button below.")
            gen_btn = gr.Button("Generate / Regenerate My Plans", variant="primary")
            plan_status = gr.Textbox(label="Status", interactive=False)

            gen_btn.click(
                generate_plan,
                inputs=[profile_state],
                outputs=[plan_display, plan_status],
            )

            # Load last saved plans (workout + nutrition) on tab load
            def _load_last_plan():
                from grokfit_coach.persistence import load_nutrition_plan

                parts = []
                wplan = load_plan()
                if wplan:
                    parts.append("## 🏋️ Workout Plan\n" + _format_plan_for_chat(wplan))
                nplan = load_nutrition_plan()
                if nplan:
                    parts.append("\n\n---\n\n## 🥗 Nutrition Plan\n" + _format_nutrition_plan_for_display(nplan))
                if parts:
                    return "\n".join(parts), "Loaded your last saved plans."
                return "No saved plan found. Click Generate to create one.", ""

            demo.load(_load_last_plan, outputs=[plan_display, plan_status], queue=False)

        gr.Markdown("---\n*Everything runs locally with Ollama. Your data never leaves your machine.*")

    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, inbrowser=False)


if __name__ == "__main__":
    launch()
