# CLAUDE.md — Resume Optimization Agent

## Project Overview

This project generates a JD-optimized, ATS-friendly PDF resume for [Your Name].

**Input:** A job description (JD) as plain text  
**Output:** A compiled PDF resume tailored to that JD, saved to `output/`

The agent reads your profile data, selects the most relevant content for the JD,
fills a fixed LaTeX template, and compiles it to PDF.

---

## Directory Structure

```
resume-agent/
├── CLAUDE.md               ← This file
├── main.py                 ← Entry point: accepts JD, triggers full pipeline
├── agent.py                ← Core logic: JD analysis + content selection
├── renderer.py             ← LaTeX template filling + pdflatex compilation
│
├── profile/                ← Your data. Read-only during generation (except skills.json).
│   ├── identity.json       ← Name, contact info, title/summary variants, certs, awards
│   ├── skills.json         ← Full skill inventory with JD matching tags
│   ├── experience.json     ← Work history with bullet variants (ds / mle / research)
│   ├── projects.json       ← Project pool with relevance tags and bullet variants
│   ├── education.json      ← Education history (fixed)
│   ├── publications.json   ← Publications list (fixed)
│   └── SKILLS_POLICY.md    ← Rules for handling skills not in skills.json
│
├── templates/
│   ├── jakes_resume.tex    ← ATS-friendly LaTeX template (structure is fixed)
│   └── TEMPLATE_SPEC.md    ← Exact format required for each <<PLACEHOLDER>>
│
├── output/                 ← Generated files land here (cleared before each run)
│   ├── resume_[timestamp].tex
│   ├── resume_[timestamp].pdf
│   └── [YourName]_Resume.pdf   ← canonical PDF after rename
│
└── archive/                ← Accepted resumes kept permanently
    └── [YourName]_Resume_[Company_Role].pdf
```

---

## Absolute Constraints (Never Violate)

1. **No fabrication.** Every piece of content must come from the `profile/` directory.
   Do not invent skills, metrics, or experiences not present in the source files.

2. **Two pages maximum.** The final PDF must be exactly two pages.
   Page 1: Header + Summary + Skills + Experience + Projects
   Page 2: Education + Publications + Certifications + Awards

3. **Template structure is fixed.** Only fill in content. Do not modify LaTeX
   structural commands, section order, fonts, or layout.

4. **Skills must fit on one line per category.** Each category label + items must
   stay within approximately 110 characters. Drop lowest-priority items if needed.

5. **Skills must be truthful.** Follow `profile/SKILLS_POLICY.md` exactly when a
   JD keyword is not found in `skills.json`.

---

## Agent Workflow

### Step 1 — Parse the JD

Extract the following from the JD text:
- `role_type`: one of `ds` | `mle` | `research`
  - ds: titles like Data Scientist, Analyst, Applied Scientist
  - mle: titles like ML Engineer, AI Engineer, Software Engineer ML, MLOps
  - research: titles like Research Scientist, AI Scientist, Scientist
- `tech_keywords`: list of technical terms (lowercase), e.g. `["pytorch", "rag", "sql"]`
- `domain_keywords`: domain context, e.g. `["healthcare", "clinical", "nlp"]`
- `soft_keywords`: e.g. `["cross-functional", "stakeholder", "communication"]`

---

### Step 2 — Select Title and Summary

From `identity.json`, select `title_variants[role_type]`.

For the summary, use `summary_variants[role_type]` as a **base template**, then rewrite
it to reflect the specific emphasis of this JD. Rules:

- Keep the same overall structure and length (±10% of the original word count)
- Swap in JD-relevant domain terms where natural (e.g. replace "healthcare data" with
  "payer analytics" if the JD is insurance-focused)
- If the JD has a strong signal not in any variant (e.g. "bioinformatics", "insurance",
  "real-world evidence"), weave it into an existing sentence rather than appending new ones
- Every claim in the rewritten summary must be grounded in profile content
- Do not make the summary longer than the original variant — tighter is better

---

### Step 3 — Build Skills Section

**Category selection and ordering:**
- Always include all four categories (Engineering, AI & ML, Analytics, Collaboration)
- Order categories by relevance to `role_type`:
  - `mle`:      Engineering → AI & ML → Analytics → Collaboration
  - `ds`:       Analytics → AI & ML → Engineering → Collaboration
  - `research`: AI & ML → Analytics → Engineering → Collaboration
- If a category scores 0 matched items from the JD, it still appears but is populated
  with the most role-type-relevant defaults from `all_items`

**Item selection per category:**
1. Score each item: +1 for each matched `jd_tag` found in JD text (lowercase match)
2. Always include items with score > 0
3. Fill remaining line space with highest-priority defaults for this `role_type`
4. Enforce line length: label + items must stay within ~110 characters.
   Drop the lowest-scored item and recheck until it fits.
5. For any important JD keyword not matched in `skills.json`, follow `SKILLS_POLICY.md`

---

### Step 4 — Select Experience Bullets

For each position, select `bullets[role_type]`.

**JD-based ranking:** Before selecting the top N bullets, rank all bullets in
`bullets[role_type]` by JD relevance — count how many items from
`tech_keywords + domain_keywords` appear in each bullet (case-insensitive).
Sort descending by score, preserving original order on ties. Select the top N
from the ranked list so the most JD-relevant bullets always appear.

**Starting bullet counts** (before any page budget adjustment):
- PHA (most recent):   6 bullets
- Postdoc:             5 bullets  
- PhD/GRA:             3 bullets

These are starting points, not fixed values. The page budget system in Step 7
may reduce them. The ordering principle is always: PHA ≥ Postdoc ≥ PhD.
PhD minimum is 2 bullets and should only be reduced as a last resort.

---

### Step 5 — Select and Order Projects

From `projects.json`:
1. Score each project: count how many `relevance_tags` appear in JD text
2. Sort by score descending, break ties using `priority` field (lower = higher priority)
3. Select top 4 projects as candidates

**Bullet variant selection per project:**
- All projects are always shown with exactly 3 bullets.
- Use `bullets[role_type][:3]` if the role_type variant exists; otherwise `short`
  (already 3 bullets) or `full[:3]`.
- The page budget system in Step 7 may drop the 4th project entirely if needed,
  but never expands individual projects beyond 3 bullets.

---

### Step 6 — Assemble Page 2 (Fixed)

Page 2 content is always identical regardless of JD. Do not modify.

From `education.json`: all degrees, in order  
From `publications.json`: all publications, in order  
From `identity.json`:
- `certifications`: all entries
- `awards`: all entries

---

### Step 7 — Compile and Enforce Page Budget

**Before generating, clear the output directory:**
Delete all files in `output/` (including any previous `[YourName]_Resume.pdf`). This
prevents stale `.tex`, `.aux`, `.log`, and old timestamped `.pdf` files from accumulating.
A fresh canonical PDF is created by renaming after successful generation.

**Before filling the template:**
- Read `templates/TEMPLATE_SPEC.md` for the exact LaTeX format required for each `<<PLACEHOLDER>>`
- Escape all special characters in strings sourced from profile JSON:
  `%` → `\%`, `&` → `\&`, `#` → `\#`, `_` → `\_`
- Apply escaping before any string is inserted into the template

**Bullet compaction (before filling template):**
After content selection, shorten any bullet that exceeds 110 characters using a
single batched LLM call. Collect all over-limit bullets from experience and projects,
send them numbered, ask for rewrites ≤110 chars each (keep the most important
metric or action verb phrase). Replace originals only if the response count matches.
Bullets at or under 110 chars pass through unchanged. Skipped when LLM mode is off.

**First compile:**
1. Fill `templates/jakes_resume.tex` with selected content
2. Save as `output/resume_YYYYMMDD_HHMMSS.tex`
3. Run pdflatex twice (required for correct layout):
   ```
   pdflatex -interaction=nonstopmode -output-directory=output output/resume_[timestamp].tex
   pdflatex -interaction=nonstopmode -output-directory=output output/resume_[timestamp].tex
   ```
4. Check page count of output PDF

**If page 1 content overflows (total pages > 2), apply in this order:**

| Priority | Action                                              | Min limit          |
|----------|-----------------------------------------------------|--------------------|
| 1        | (Safety) Switch any project with >3 bullets → `short` — normally inactive since projects start at 3 | — |
| 2        | Drop 4th project, restore remaining 3 to 3-bullet variants | 3 projects minimum |
| 3        | Reduce PHA bullets by 1                             | 3 bullets minimum  |
| 4        | Reduce Postdoc bullets by 1                         | 2 bullets minimum  |
| 5        | Reduce PhD/GRA bullets by 1                         | 2 bullets minimum  |
| 6        | Shorten Summary by removing least-relevant sentence | 2 sentences min    |

After each adjustment, recompile and recheck. Stop as soon as page count = 2.
If still overflowing after all steps: save the .tex file and warn the user.

**Print to terminal after successful compile:**
```
Resume saved to output/resume_[timestamp].pdf
```

---

### Expected Terminal Output

```
[JD Analysis]
  Role type:     mle
  Tech keywords: pytorch, aws, llm, sql, docker
  Domain:        healthcare, clinical
  Soft skills:   cross-functional, stakeholder

[Content Selection]
  Title:    AI/ML Engineer - LLM & DNN
  Projects: magic, dermoscopy, vaccine_vibes, critical_period
  Skills categories order: Engineering -> AI & ML -> Analytics -> Collaboration

[Skills Check]
  All JD keywords matched in profile.

[Bullet Compact]  8 bullet(s) shortened to <=110 chars

[Compiling]  pass 1... pass 2... pages: 2 OK
  -> output/resume_20260608_143022.pdf

Resume saved to output/resume_20260608_143022.pdf
```

---

## Post-Generation: Rename and Archive

After a successful PDF compile, the script prompts:
```
Rename to [YourName]_Resume.pdf? (y/n):
```
- If **y**: the archive suffix is auto-derived from the JD as `Company_JobTitle`
  (spaces and special characters replaced with underscores, e.g. `NBME_AI_Engineer`).
  - Copies the PDF to `archive/[YourName]_Resume_Company_Role.pdf`
  - The timestamped PDF is then replaced by `output/[YourName]_Resume.pdf`
  - Since `output/` is cleared at the start of each run, the canonical PDF is always
    the one from the most recent accepted generation.
  - No user prompt needed — company and job title are extracted during JD analysis.
- If **n**: the timestamped file is kept as-is in `output/`.
- In non-interactive mode (e.g. `conda run`): defaults to **n**, skips silently.

The `archive/` folder is never cleared — it is a permanent record of every accepted resume.

---

## Skills Update Protocol

When Step 3 triggers a missing-skill prompt and the user confirms (y):
1. Add the skill to the appropriate category in `skills.json` under `all_items`
2. Add reasonable `jd_tags` for the new skill
3. Print: `[SKILLS UPDATED] "{skill}" added to skills.json under "{category}"`

---

## Error Handling

- If `pdflatex` is not installed: print clear install instructions and exit gracefully
- If a profile JSON file is missing: raise a descriptive error naming the file
- If page count check fails after all overflow adjustments: warn the user,
  save the .tex file so they can inspect and fix manually
- Never silently fail — always print what went wrong and where

---

## What Claude Code Should NOT Do

- Do not modify any file in `profile/` except `skills.json` (only when user confirms)
- Do not modify `templates/jakes_resume.tex`
- Do not add content not grounded in `profile/`
- Do not skip the two-pass pdflatex compilation
- Do not hardcode content — everything must be read from `profile/` at runtime
- Do not remove Publications, Certifications, or Awards from page 2
- Do not use any external resume skill.md or docx skill.md — follow this file only
