# Plan contract — how to write slices so an implementer can run without guessing

This document is **normative** for any work tracked in `docs/IMPLEMENTATION_PLAN_EMAIL_SUMMARIES.md` (or a sibling plan). If the plan omits a required heading, the slice is **underspecified**.

---

## 1. Vocabulary (use exactly these words)

| Term | Meaning |
|------|--------|
| **MUST** / **MUST NOT** | Hard requirement; violating it is a failed implementation. |
| **SHOULD** | Default; deviate only if the plan explicitly records why. |
| **MAY** | Optional optimization. |
| **Invariant** | A fact that was true before the slice and MUST remain true after (API shape, exit codes, file locations, sorting, user-visible numbers). |
| **Coupling** | “If you change X, you MUST also change Y” — list both sides. |
| **Slice** | One reviewable unit: one PR-sized vertical, one commit message theme, tests green before starting the next slice. |

Avoid vague verbs (“clean up”, “improve”, “handle edge cases”). Replace with observable outcomes.

---

## 2. Mandatory sections (every named slice / milestone)

Copy the **template in §10** into the implementation plan for each slice. Do not merge slices in one heading unless the heading explicitly lists multiple **independent** acceptance blocks.

Each slice **MUST** include:

1. **Goal** — One sentence: user-visible or contract outcome.
2. **Non-goals** — What this slice MUST NOT change (prevents scope creep).
3. **Invariants** — Bullets; include data, CLI exit codes, JSON keys, and “MUST NOT change unless listed below”.
4. **Coupling** — Files, tests, docs, env vars that must move together.
5. **Preconditions** — Branch, Python env (`mamba` env name), `pip install -e ".[dev]"`, any secrets **names only** (not values).
6. **Permissions & environment** — What the implementer is allowed to assume (see §3).
7. **Caveats & footguns** — What breaks silently if ignored (see §4).
8. **Procedure** — Ordered steps (numbered). Prefer “edit file X: add function Y” over prose.
9. **Acceptance** — Exact `pytest` / CLI commands and expected exit codes; optional manual check with **expected** observation.
10. **Follow-ups** — Deferred work (see §5); MUST NOT block merging this slice unless marked **BLOCKER**.

---

## 3. How to phrase **permissions & environment**

Use a **small table** the implementer can copy into a runbook:

| Class | State explicitly |
|--------|-------------------|
| **Network** | MUST / MUST NOT call live APIs (Gmail, LLM). If MUST, mark `@pytest.mark.e2e` and skip in CI. |
| **Filesystem** | Paths MAY write (e.g. `tmp_path`, `cache/`, `output/`). Paths MUST NOT touch. |
| **Git** | Whether commit/push is in scope; **MUST NOT** add trailers (`--trailer`, hook-injected `Co-authored-by`); if hooks inject trailers, use empty `core.hooksPath` for that commit (see repo README / user rules). |
| **Shell** | `mamba run -n <env>` vs system `python`; `PYTHONPATH=src` only if documented. |
| **Credentials** | Env var **names** required; never paste tokens into the plan. |

**Bad:** “Run tests when convenient.”  
**Good:** “MUST: `mamba run -n email-digest python -m pytest tests/ -q` exits 0 before merge.”

---

## 4. How to phrase **caveats & footguns**

Each caveat gets **four** short lines (same shape every time):

1. **Symptom** — What you observe (test failure, wrong JSON, silent data loss).
2. **Cause** — One technical reason (hook, default arg, import path, ordering).
3. **Wrong fix** — What not to do (so the LLM doesn’t cargo-cult).
4. **Right fix** — The approved mitigation or invariant to restore.

**Bad:** “Be careful with Gmail.”  
**Good:** “**Caveat:** `digest run` loads Gmail after `--since` parse. **Wrong fix:** reordering without tests. **Right fix:** assert `from_env` not called on invalid `--since` in `tests/test_digest_cli.py`.”

---

## 5. How to phrase **follow-ups**

Follow-ups are **out of scope for the current slice** but MUST NOT be forgotten. Use a table:

| ID | Item | Type | Blocker for next slice? |
|----|------|------|-------------------------|
| F1 | … | tech debt / product | yes / no |

**MUST NOT** hide scope in follow-ups: if the slice needs it to be correct, it belongs in **Procedure**, not F1.

---

## 6. Definition of done (global)

A slice is **done** when:

- All **Acceptance** commands pass.
- **Invariants** are satisfied or the plan is updated in the **same** change (with reviewer note).
- **Coupling** entries are satisfied (tests/docs/env updated in one commit unless plan says otherwise).
- No new **caveat** without the §4 four-line form.

---

## 7. Template — paste under each slice heading

```markdown
### Slice: <short name>

- **Goal:** …
- **Non-goals:** …
- **Invariants:** …
- **Coupling:** …
- **Preconditions:** branch `…`, env `…`
- **Permissions & environment:** (table)
- **Caveats & footguns:** (§4 bullets)
- **Procedure:** 1. … 2. …
- **Acceptance:** `…` → exit …
- **Follow-ups:** (table or “none”)
```

---

## 8. Where this ties in

- **Project intent / product:** `docs/PROJECT_BRIEF_EMAIL_SUMMARIES.md`
- **Milestones & file map:** `docs/IMPLEMENTATION_PLAN_EMAIL_SUMMARIES.md` — each milestone SHOULD use the §7 template per slice.
- **What exists:** `docs/INVENTORY.md`

If the brief and the plan disagree, **stop** and reconcile in the plan with a dated note before implementing.
