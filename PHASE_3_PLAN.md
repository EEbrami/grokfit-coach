# Phase 3 Plan — Intake-Driven Workout **and** Nutrition Coach with Longitudinal Tracking and Multi-LLM Support

> **Goal of Phase 3:** turn grokfit-coach from a single-shot local workout-plan generator into an app that (1) **interviews the user**, (2) stores a rich, versioned **profile**, (3) generates **both a workout plan and a nutrition plan** — the nutrition plan grounded in a real **open food→nutrient database**, respecting **food preferences and allergens**, (4) **tracks everything over time** with timestamps, and (5) lets the user **choose the LLM** (free local models *or* an optional API key), all configured in the profile.
>
> **Non-negotiables carried from Phase 1/2:** local-first & private by default; deterministic safety guardrails before/after the LLM; a deterministic fallback whenever structured output fails; every output carries a disclaimer.

This plan is the synthesis of: (a) the actual repo state, (b) the three open PRs, (c) the Phase 1/2 documented limitations, and (d) verified research (June 2026) on open nutrition datasets and the free local-LLM / multi-provider landscape (sources at the end).

---

## How to Execute This Plan

This is a developer-grade, multi-milestone roadmap — it is meant to be **implemented by a coding agent (e.g. Claude Code), not built by hand.** Recommended workflow:

1. **Confirm the Part B decisions** (and the Part G open questions) first — those choices change what gets built.
2. **Feed it to the agent one milestone at a time**, in order (M0 → M7). Each milestone is self-contained and ends with **acceptance criteria** — treat those as the gate: don't start the next milestone until the current one's criteria pass (`pytest -q` green + the stated behavior verified).
3. **Milestone 0 is mostly copy-paste git/gh commands** you can run yourself or hand to the agent.
4. Keep this file in the repo; update the backlog (Part C) and check off milestones as they land.

You don't need to understand the internals — but you do need to make the Part B/G calls and verify each milestone's acceptance criteria before moving on.

---

## 0. Current State (verified)

- **Code:** Python package (`src/grokfit_coach`), LangGraph single-agent + ReAct tool loop, FAISS RAG over a **10-exercise / 10-food** curated seed set, 3 LangChain tools, rule-based safety, Gradio UI + CLI, JSON persistence (`~/.grokfit/profile.json`, `last_plan.json`).
- **Plan generation today:** workout-only. `maybe_generate_plan` retrieves ≤10 exercises → filters by equipment/injury in Python → asks the LLM for a `WeeklyWorkoutPlan` via `with_structured_output` → post-validates against the retrieved whitelist → **deterministic fallback** if the LLM fails. **No nutrition plan object exists.**
- **Nutrition today:** two tools only — `lookup_nutrition` (10-food toy list) and `calculate_macros` (Mifflin–St Jeor TDEE). No food database, no meal plan.
- **LLM today:** hard-coded `ChatOllama(model="llama3.1")` in `agents/graph.py:34`; default model in `config/settings.py:20`.
- **Persistence today:** overwrite-single-file. **No history, no timestamps.**

---

## Part A — PR & Branch Resolution (do this first; ~30 min)

The three open PRs are a **linear stack**, confirmed by `git log` containment — the checked-out tip contains every commit from both lower PRs:

```
main
 └─ #3  feat/phase-1-foundation   → base main   (foundation)
     └─ #4  feat/phase-2-ui        → base main   (= #3 + UI/persistence/plans)
         └─ #5  fix/fallback-and-ui-bugs → base feat/phase-2-ui   ← tip = #3 + #4 + 2 fixes
```

**Recommended: fast-forward the tip onto `main` — consolidates the stack *and* preserves all 7 commits.**

Verified safe: `main` has **no unique commits** (`git log fix/fallback-and-ui-bugs..main` is empty), so the tip is a clean linear descendant and `main` fast-forwards with zero merge commits and zero history loss.

1. **Run tests on the tip** (the only gate — CI reports "no checks"):
   ```bash
   git checkout fix/fallback-and-ui-bugs
   python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
   pytest tests/unit -q
   ```
2. **Fast-forward `main` to the tip** (keeps every phase-structured commit intact):
   ```bash
   git checkout main && git merge --ff-only fix/fallback-and-ui-bugs && git push origin main
   ```
   This auto-closes **PR #5** as merged (it targets `feat/phase-2-ui`, so optionally re-target first with `gh pr edit 5 --base main`; either way the commits land).
3. **Close #3 and #4 as superseded** (do *not* merge them — their commits are already on `main`):
   `gh pr close 3 --comment "Fully contained in the consolidated main."` (same for #4)
4. **Prune branches** and cut Phase 3 work from the fresh `main`:
   `git checkout -b feat/phase-3-foundation`

> **Why not squash?** `gh pr merge --squash` would collapse all 7 commits (Phase 1, Phase 2, the two fixes) into one — discarding the deliberate phase-structured history that pairs with the PHASE_1/PHASE_2 handoff docs. Fast-forward gives the same single clean `main` **without** that irreversible loss.
>
> *Alternatives:* (a) **squash** — only if you explicitly want a clean-slate single commit and don't value the granular history; (b) merge #3→main, then #4, then #5 in order — not recommended (one author's linear stack → redundant merge commits, no benefit).

---

## Part B — Decisions to Confirm (defaults chosen; override any)

These few choices drive the whole build. Defaults in **bold** are baked into this plan; tell me to change any.

| # | Decision | Recommended default | Why |
|---|---|---|---|
| 1 | Storage backend | **SQLite** (one local file) | Serves the food DB *and* timestamped tracking in one engine; keeps privacy-first/offline. |
| 2 | Cloud API egress | **Local by default; API strictly opt-in** with a blocking data-egress warning | Preserves the "100% local" identity; API is a real privacy departure. |
| 3 | Intake style | **Form/wizard = source of truth**, conversational as a convenience layer | Forms give reliable validation; small local LLMs are unreliable at structured intake. |
| 4 | Nutrition plan depth | **Daily targets + grounded food/meal suggestions** first; full meal-by-meal menus later | Safer, within guardrails, shippable sooner. |
| 5 | Allergens | **Safety-critical hard exclusions** (deterministic, fail-closed) — never a soft LLM preference | Recommending an allergen is a real-harm bug. |
| 6 | Nutrition source | **USDA FoodData Central (CC0)** bundled offline; Open Food Facts opt-in only | CC0 = redistributable with zero obligation; OFF is ODbL share-alike. |
| 7 | Default local model | **Switch default `llama3.1` → `qwen2.5` (7B)**, *but only with auto-detect of already-pulled models* | Qwen2.5 is the most reliable small model for structured output; auto-detect avoids forcing a re-pull. |
| 8 | API-key storage | **Env var / OS keyring — NOT `profile.json`** | Plaintext secrets on disk would be the biggest privacy regression. |

---

## Part C — Issue / Gap Backlog (the "issues, one by one")

There are no GitHub issues; these are the real gaps to resolve, prioritized. Each maps to a milestone in Part E.

| ID | Issue / gap | Severity | Milestone |
|----|-------------|----------|-----------|
| I-01 | Three stacked PRs unmerged; no CI | High | M0 |
| I-02 | No CI runs tests on PRs (silent regressions) | High | M0 |
| I-03 | Persistence is overwrite-only; no timestamps/history | High | M1 |
| I-04 | `UserProfile` lacks food preferences, allergens, LLM config | High | M1 |
| I-05 | LLM provider hard-coded; no model choice, no API option | High | M2 |
| I-06 | API keys would land in plaintext profile.json if naive | High (privacy) | M2 |
| I-07 | No food→nutrient database (10-food toy list only) | High | M3 |
| I-08 | No allergen data in USDA generic foods → safety gap | High (safety) | M3/M6 |
| I-09 | No nutrition plan generation at all | High | M4 |
| I-10 | No intake/questionnaire; profile is hand-edited | High | M4 |
| I-11 | No longitudinal tracking / progress over time | High | M5 |
| I-12 | Nutrition prescription collides with crash-diet guardrails | Med (safety) | M6 |
| I-13 | No disordered-eating safeguards for weight tracking | Med (safety) | M6 |
| I-14 | Weak/small models silently break structured output | Med | M2 |
| I-15 | Exercise/food seed sets tiny; workout variety capped | Med | M3/M7 |
| I-16 | Bundled dataset will go stale (no version/date shown) | Low | M3 |
| I-17 | No end-to-end/UI tests; plan quality not evaluated | Med | M7 |

---

## Part D — The Data-Model Spine (the shared backbone)

Everything new couples through `UserProfile` + storage, so this is fixed first (Milestone 1) and all later work builds on it.

### D.1 Expanded `UserProfile` (Pydantic v2)
Add to existing fields:
- `food_preferences: list[str]` — liked foods/cuisines
- `disliked_foods: list[str]` — soft exclusions
- `allergens: list[str]` — **hard, safety-critical exclusions** (separate from preferences and from `dietary_restrictions`)
- `dietary_pattern: Literal["omnivore","vegetarian","vegan","pescatarian","keto","halal","kosher",...]`
- `meals_per_day: int`, `cooking_effort: Literal["minimal","moderate","involved"]`
- `llm_config: LLMConfig` (nested — see D.4)
- `activity_level: Literal["sedentary","light","moderate","active","very"]` (feeds `calculate_macros`)
- `profile_version: int` (for migrations)

### D.2 New / changed Pydantic models
- `NutritionPlan` — mirrors `WeeklyWorkoutPlan`: `daily_targets` (kcal + protein/carb/fat from Mifflin–St Jeor), `days → meals → FoodChoice` where `FoodChoice = {fdc_id, name, grams, computed_macros}`; `notes`, `disclaimer`.
- `LLMConfig` — `provider`, `model`, `api_key_ref` (env-var name, **never** the raw key), `temperature`.
- `TrackingEvent` — `ts: datetime`, `type: Literal["intake","plan_generated","weight","measurement","adherence","note"]`, `payload: dict`.
- `FoodItem` — extend with numeric `grams`, `fdc_id`, `diet_flags`, `allergen_flags` (keep current fields for back-compat).
- `Exercise` — unchanged (room to grow seed set in M7).

### D.3 SQLite storage (replaces overwrite-JSON)
One file (e.g. `~/.grokfit/grokfit.sqlite`); add paths to `config/settings.py`.
- `profiles(version, json, created_ts)` — versioned current profile
- `events(id, ts, type, payload_json)` — **append-only** longitudinal log (the "track over time" core)
- `plans(id, ts, kind['workout'|'nutrition'], json)` — versioned, timestamped (replaces `last_plan.json`)
- `foods`, `food_nutrient`, `nutrient`, `food_portion` — local nutrition DB (M3)
- **Migration step:** on first run, import existing `~/.grokfit/profile.json` + `last_plan.json` into SQLite, then leave the JSON in place as a backup. No data loss.

### D.4 Multi-LLM provider seam
Replace hard-coded `_get_llm()` (`agents/graph.py:32`) with `get_chat_model(profile, settings)`:
- **Local (default):** `ChatOllama(model=profile.llm_config.model, base_url=settings.ollama_host)`
- **Cloud (opt-in):** `init_chat_model(model, model_provider=provider, api_key=...)` → dispatches to `ChatGoogleGenerativeAI` / `ChatGroq` / `ChatOpenAI` / `ChatAnthropic` / `ChatMistralAI`; OpenRouter via `ChatOpenAI(base_url="https://openrouter.ai/api/v1", ...)`.
- **Lazy-import** each `langchain-<provider>` inside its branch (friendly "pip install …" on ImportError).
- Cloud SDKs live in `pyproject [project.optional-dependencies].cloud` — base install stays Ollama-only.

---

## Part E — Phased Roadmap (milestones, tasks, acceptance criteria)

### Milestone 0 — Consolidate & harden the repo
**Tasks:** Part A PR consolidation; add GitHub Actions CI (`pytest` + `ruff` + `pyright` on PRs); confirm `pytest -q` green on a clean `main`.
**Acceptance:** one clean `main` containing all prior work; CI green on every PR; branches pruned.

### Milestone 1 — Foundation: data-model spine + SQLite + migration
**Tasks:** implement D.1–D.3; write `storage/db.py` (SQLite layer: profile CRUD, append `events`, save/load `plans`); migrate existing JSON; keep `persistence.py` functions working as thin wrappers (non-breaking CLI/UI).
**Acceptance:** existing CLI/UI run unchanged against SQLite; saving a profile writes a versioned row + an `intake`/`note` event; generating a plan appends a timestamped `plans` row; old JSON auto-imported; new unit tests for the storage layer pass.

### Milestone 2 — Multi-LLM provider layer (local menu + API opt-in)
**Tasks:** implement D.4 factory; **TOOL_RELIABLE allowlist** gate for the plan path; curated local menu surfaced in profile setup ordered by structured-output reliability:
- **Default `qwen2.5` (7B, ~5 GB)** → `qwen2.5:14b` (stronger) → `llama3.1` (8B, broad compat) → opt-in upgrades `qwen3` / `qwen3.5` / `gemma4` → `mistral-nemo`.
- **Block from plan path** (weak at tools): `gemma2`, `gemma3`, `phi3`, `phi4`, `llama3.2:1b/3b`, any sub-7B, any Q2/Q3 quant — show "this model can't reliably build plans, pick from the recommended list."
- **Note on Gemma (you asked about it specifically):** Gemma 2 and Gemma 3 are **chat-only for our purposes** — too weak at structured/tool output for plan generation, so they're blocked from the plan path (still fine for free-text chat). **Gemma 4 (Apache-2.0) is the version that works** — it added native function-calling — so it's the Gemma to pull if you want to use Gemma. Llama 3.1 (8B) and Qwen2.5 (7B/14B) remain the most reliable picks.
- **Default-change safety (required):** before defaulting to `qwen2.5`, ping Ollama `/api/tags` and pick the best **already-pulled** tool-reliable model; only suggest pulling `qwen2.5` if nothing suitable is installed (avoids "model not found" for existing users).
- **API opt-in:** `cloud` optional extra; **API keys from env/keyring, never persisted in profile.json**; a **blocking data-egress warning** before the first cloud call (names the provider; for Gemini free tier, state data may be used for training); cloud-active banner in CLI/UI sessions.
- Disable "thinking" mode on qwen3.x/gemma4 for the structured path; wrap `with_structured_output` in validate-and-retry-once before falling back.
**Acceptance:** user selects provider/model in profile; default install never imports cloud SDKs; choosing cloud triggers the warning and reads the key from env/keyring; selecting a weak model is blocked from plan generation with a clear message; plan generation still produces a valid plan (or deterministic fallback) on the default local model.

### Milestone 3 — Nutrition data backbone (USDA FDC → SQLite)
**Tasks:**
- `nutrition/ingest_fdc.py`: download/parse **USDA FoodData Central — Foundation Foods + SR Legacy + FNDDS** into the SQLite tables (D.3). Canonical storage **per 100g** (`food_nutrient.amount`); use `food_portion.gram_weight` for serving conversions (FNDDS has the best "as eaten" portions). **Use SR Legacy CSV** (its JSON is larger) and **FNDDS JSON** (its CSV is 1.6 GB). Recommended subset is tens of MB total.
- Map FDC nutrient IDs → `FoodItem` macros (Energy→kcal, Protein, Carbohydrate-by-difference, Total fat).
- Build a **curated allergen map** (food-group → allergen: dairy→milk, etc.) populating `allergen_flags`, plus `diet_flags`. **Fail-closed:** unknown allergen status = exclude from an allergy-restricted plan.
- Upgrade `lookup_nutrition` to query SQLite (FAISS/FTS5 for fuzzy name match → deterministic SQL for macros/diet/allergen). Keep the `FoodItem` return shape (tools unchanged).
- Store dataset **version/date** (e.g. "FDC April 2026") in an about screen for reproducibility + CC0 citation hygiene.
- *(Optional, deferred)* Open Food Facts as a **user-initiated** download for branded/barcode + allergen tags — kept opt-in so we never redistribute an ODbL database.
**Acceptance:** local food DB queryable offline; `lookup_nutrition` returns real USDA macros; allergen/diet filters are pure SQL and fail-closed; ingest is idempotent and version-stamped.

### Milestone 4 — Generation: intake → workout + nutrition plans
**Tasks:**
- **Intake wizard** (CLI prompts + Gradio form) collecting all D.1 fields incl. food preferences & allergens; validates via Pydantic; writes profile + an `intake` event (timestamped).
- **Nutrition plan generator** (new graph node / helper, mirroring `maybe_generate_plan`): compute daily targets via `calculate_macros`; retrieve candidate foods from SQLite **filtered by allergens (hard), dietary_pattern, dislikes (soft), preferences (boost)**; ask the chosen LLM for a structured `NutritionPlan`; **post-validate** every food against the allowed/filtered set (anti-hallucination, same pattern as workouts); **deterministic fallback** that assembles a compliant day from filtered foods if the LLM fails.
- **Unified "Generate my plans"** action returning both `WeeklyWorkoutPlan` + `NutritionPlan`, both saved as timestamped `plans` rows.
**Acceptance:** from a fresh intake the app produces both plans; no plan ever contains an allergen the user listed; foods respect dietary pattern; macros sum to ~daily target; fallback works on a weak/local model; both plans timestamped in SQLite.

### Milestone 5 — Longitudinal tracking
**Tasks:** log every intake answer, generated plan, weight/measurement, and adherence check-in as timestamped `events`; add a **History/Progress** UI tab + CLI command (weight trend, plan history, adherence over time); let regeneration **read recent history** so plans adapt over time (e.g. progress/intensity hints).
**Acceptance:** inputs are timestamped and queryable; progress view renders a trend; regenerated plans reference prior history.

### Milestone 6 — Safety hardening (reconcile nutrition with guardrails)
**Tasks:**
- Reconcile nutrition prescription with existing crash-diet guardrails: enforce **calorie floors**, cap deficit aggressiveness, no rapid-loss language; allergen hard-exclude wired into both the filter *and* `safety/guardrails.py`.
- **Disordered-eating safeguards** for weight tracking: healthy-range checks, no obsessive-loss encouragement, supportive copy, escalate-to-professional language.
- Egress warning + cloud banner finalized; redact profile PII from any cloud prompt where feasible.
- Disclaimer on every workout **and** nutrition output.
**Acceptance:** crash-diet/unsafe nutrition requests still blocked; allergen never recommended even if the LLM hallucinates it; weight-tracking copy passes an ED-sensitivity review; cloud path always warns.

### Milestone 7 — Testing, evaluation, docs, release
**Tasks:** expand exercise/food seeds; golden-set eval for **both** plan types (incl. an allergen-exclusion test that must never fail); UI smoke tests; multi-model structured-output check (run `with_structured_output(NutritionPlan)` against the golden set per recommended model before promoting any to default); update README + `PHASE_3_HANDOFF.md` + CHANGELOG; tag a release.
**Acceptance:** all tests green incl. the safety/allergen tests; docs describe intake, dual plans, model selection, API opt-in, and tracking; clean release tag.

---

## Part F — Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Small local models break structured output | TOOL_RELIABLE allowlist + validate-retry-once + deterministic fallback (already the project's pattern) |
| Allergen data missing in USDA generic foods | Curated allergen map + **fail-closed** exclusion; OFF tags only as opt-in supplement (never trust tag absence as "free of") |
| API keys leak to disk | Env var / OS keyring only; never written to profile.json |
| Cloud egress contradicts "local-first" identity | Opt-in only, blocking warning, off by default, cloud SDKs as optional extras |
| Bundled food DB goes stale | Version/date stamped; re-ingest path documented; FDC refreshes ~quarterly |
| Default-model change breaks existing users | Auto-detect already-pulled models via `/api/tags`; only prompt to pull if nothing suitable |
| Nutrition advice → disordered eating | Calorie floors, ED-sensitive copy, healthy-range checks, escalate-to-pro |
| ODbL copyleft from Open Food Facts | Keep OFF strictly user-downloaded; bundle only CC0 USDA |

## Part G — Open Questions for You

1. **Branded foods:** bundle USDA Branded Foods (public domain, ~2.9 GB) for barcode coverage, keep Open Food Facts as opt-in, or **stick to generic whole foods only** (smallest, cleanest — my default)?
2. **Allergen map depth:** food-group-level (fast, coarse) vs per-food review (safer, labor-intensive)? Given fail-closed, group-level + fail-closed is my default.
3. **Cloud providers to support first:** my default menu is **Gemini Flash (best free), Groq (fastest), Mistral, OpenRouter**; OpenAI/Anthropic as paid extras. Trim or extend?
4. **Default model switch** to `qwen2.5` (with auto-detect) — OK, or keep `llama3.1` as default?
5. **Nutrition plan depth** for v1: targets + food suggestions (my default) vs full meal-by-meal menus now?

---

## Sources (verified June 2026)

**Nutrition data**
- USDA FoodData Central — license (CC0/public domain) & FAQ: https://fdc.nal.usda.gov/faq/ ; Ag Data Commons CC0: https://agdatacommons.nal.usda.gov/articles/dataset/FoodData_Central/24668133
- FDC downloads & sizes (refreshed **April 2026**): https://fdc.nal.usda.gov/download-datasets/
- FDC API guide & rate limits (1,000/hr signed; DEMO_KEY 30/hr, 50/day): https://fdc.nal.usda.gov/api-guide/
- FDC field descriptions (schema, per-100g, portions): https://fdc.nal.usda.gov/docs/Download_Field_Descriptions_Oct2020.pdf
- Open Food Facts data & ODbL/DbCL license: https://world.openfoodfacts.org/data ; Parquet (7.53 GB, 4.52M rows, allergen/label tags): https://huggingface.co/datasets/openfoodfacts/product-database
- Nutritionix (commercial, not open): https://www.nutritionix.com/database

**LLM providers**
- Ollama tool-calling docs: https://docs.ollama.com/capabilities/tool-calling ; library (sizes): https://ollama.com/library ; tools filter: https://ollama.com/search?c=tools
- Qwen3.5 (tools, 256K ctx): https://ollama.com/library/qwen3.5 ; Gemma 4 (native function-calling, **Apache-2.0**): https://ai.google.dev/gemma/docs/core/model_card_4
- Tool-calling model guidance: https://localaimaster.com/blog/ollama-tool-calling-guide ; https://www.promptquorum.com/power-local-llm/best-local-models-tool-calling-2026 ; RAM table: https://localaimaster.com/blog/ollama-model-ram-vram-table
- LangChain `with_structured_output` (default `json_schema`): https://reference.langchain.com/python/langchain-ollama/chat_models/ChatOllama/with_structured_output ; `init_chat_model`: https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model
- Free-tier landscape (verify live; Gemini numbers gated): https://tokenmix.ai/blog/free-llm-apis-2026-every-provider-free-tier-tested ; https://ai.google.dev/gemini-api/docs/rate-limits ; OpenAI deprecations: https://platform.openai.com/docs/deprecations

> **Verification caveats baked into the plan:** FDC refreshed to **April 2026** (Foundation/Branded), so version-stamp any bundle. **Gemma 4 is Apache-2.0** (Gemma 2/3 are not — and are weak at tools). Cloud free-tier numbers drift and Gemini's are not published in primary docs — **link out, never hardcode**. Groq's binding free limit is **tokens-per-day**, not requests. Qwen2.5 is battle-tested but two generations old — re-evaluate the default periodically.
