# resume-agent

An AI-powered CLI that generates a tailored, ATS-friendly 2-page PDF resume from a job description.
Paste a JD, and the agent selects the most relevant content from your profile, fills a LaTeX template,
and compiles a polished PDF — in one command.

---

## Features

- **JD-aware selection** — skills, experience bullets, and projects are all scored and ranked by
  keyword match against the job description
- **Two modes** — LLM-enhanced output via the Anthropic API, or a fully rule-based fallback that
  works with no API key
- **Automatic 2-page enforcement** — an overflow reduction loop trims bullets and projects until
  the PDF fits exactly two pages
- **Bullet compaction** — long bullets are shortened via LLM to stay within the 110-character line limit
- **Auto-archive** — accepted resumes are copied to `archive/` with a `Company_Role` suffix
  auto-derived from the JD
- **No-fabrication policy** — every skill and bullet must be grounded in your `profile/` files;
  the agent will never invent content

---

## Prerequisites

- **Python 3.9+**
- **pdflatex** — install a TeX distribution for your OS:
  - Windows: [MiKTeX](https://miktex.org/download)
  - macOS: `brew install --cask mactex`
  - Linux: `sudo apt-get install texlive-full`
- **Anthropic API key** — optional; the rule-based fallback runs without one

---

## Installation

```bash
git clone <repo-url>
cd resume-agent
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and replace the placeholder with your real API key:
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Building Your Profile

All candidate data lives in `profile/`. Replace the example content in each file with your own
information before running the agent. The files are standard JSON — the structure is fixed, the
content is yours.

### `profile/identity.json`

Top-level personal info and role-specific variants.

```json
{
  "name": "Your Name",
  "phone": "(+1) 555-000-0000",
  "email": "you@example.com",
  "linkedin_url": "https://linkedin.com/in/yourhandle",
  "github_url": "https://github.com/yourhandle",
  "google_scholar_url": "https://scholar.google.com/citations?user=...",
  "title_variants": {
    "ds":       "Data Scientist",
    "mle":      "ML Engineer",
    "research": "Research Scientist"
  },
  "summary_variants": {
    "ds":       "2–3 sentence summary emphasizing data science skills...",
    "mle":      "2–3 sentence summary emphasizing engineering skills...",
    "research": "2–3 sentence summary emphasizing research skills..."
  },
  "certifications": [
    { "year": 2023, "title": "Certification Name", "issuer": "Issuer" }
  ],
  "awards": [
    { "year": 2024, "title": "Award Name", "venue": "Venue" }
  ]
}
```

The agent selects `title_variants[role_type]` and uses `summary_variants[role_type]` as a
base that the LLM rewrites to match the specific JD.

### `profile/experience.json`

Work history, most recent position first. Each position has three bullet variants —
`ds`, `mle`, and `research` — so the most relevant bullets surface per role type.

```json
{
  "positions": [
    {
      "company": "Company Name",
      "location": "City, State",
      "title": "Job Title",
      "start": "Jan 2024",
      "end": "Present",
      "bullets": {
        "ds":       ["Bullet 1...", "Bullet 2..."],
        "mle":      ["Bullet 1...", "Bullet 2..."],
        "research": ["Bullet 1...", "Bullet 2..."]
      }
    }
  ]
}
```

**Important:** Escape `%` as `\\%` inside JSON string values — LaTeX requires it.

### `profile/projects.json`

A pool of projects the agent selects from. Each project is shown with exactly 3 bullets.
The top 4 projects by JD relevance score are candidates; `priority` breaks ties.

```json
{
  "projects": [
    {
      "id": "my-project",
      "title": "PROJECT NAME",
      "subtitle": "Full descriptive subtitle",
      "relevance_tags": ["nlp", "healthcare", "llm"],
      "priority": 1,
      "bullets": {
        "ds":       ["Bullet 1", "Bullet 2", "Bullet 3"],
        "mle":      ["Bullet 1", "Bullet 2", "Bullet 3"],
        "research": ["Bullet 1", "Bullet 2", "Bullet 3"],
        "short":    ["Bullet 1", "Bullet 2", "Bullet 3"]
      }
    }
  ]
}
```

### `profile/education.json`

```json
{
  "degrees": [
    {
      "institution": "University Name",
      "location": "City, State",
      "degree": "Ph.D. in Computer Science",
      "start": "Aug 2018",
      "end": "May 2023",
      "note": "Optional italic note shown under degree entry."
    }
  ]
}
```

### `profile/publications.json`

```json
{
  "publications": [
    {
      "authors": "A Smith; B Jones; et al.",
      "title": "Title of the Paper",
      "venue": "Journal or Conference Name",
      "year": 2024
    }
  ]
}
```

Your abbreviated name (`F LastName`, e.g. `J Smith`) is automatically bolded wherever
it appears in the author string.

### `profile/skills.json`

Four fixed categories: `engineering`, `ai_ml`, `analytics`, `collaboration`.
Each item has a list of `jd_tags` — lowercase aliases matched against the JD text to score
the item's relevance.

```json
{
  "categories": {
    "engineering": {
      "label": "Engineering",
      "all_items": ["Python", "SQL", "Docker", "AWS"],
      "jd_tags": {
        "Python": ["python", "programming"],
        "SQL":    ["sql", "database", "query"]
      }
    }
  }
}
```

See `profile/SKILLS_POLICY.md` for the rules governing skills not in this file.

### Rename the output filename

In `main.py`, the canonical output filename is set near the bottom. Change
`"Your_Name_Resume.pdf"` to match your own name before your first run:

```python
rename_dest = Path(pdf_path).parent / "Your_Name_Resume.pdf"
...
archive_name = f"Your_Name_Resume_{suffix}.pdf"
```

---

## Quick Start

```bash
# Save your job description as jd.txt in the project root, then:
python main.py

# Or point to any file:
python main.py --jd /path/to/job_description.txt
```

Expected output:

```
[JD Analysis]
  Company:       Acme Corp
  Job title:     ML Engineer
  Role type:     mle
  Tech keywords: pytorch, aws, llm, sql, docker
  Domain:        healthcare, clinical
  Soft skills:   cross-functional, stakeholder

[Content Selection]
  Title:    ML Engineer
  Projects: project-a, project-b, project-c, project-d
  Skills categories order: Engineering -> AI & ML -> Analytics -> Collaboration

[Skills Check]
  All JD keywords matched in profile.

[Bullet Compact]  8 bullet(s) shortened to <=110 chars

[Compiling]  pass 1... pass 2... pages: 2 OK
  -> output/resume_20260608_143022.pdf

Resume saved to output/resume_20260608_143022.pdf

Rename to Your_Name_Resume.pdf? (y/n): y
Archived  -> archive/Your_Name_Resume_AcmeCorp_MLEngineer.pdf
Renamed   -> output/Your_Name_Resume.pdf
```

---

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--jd FILE` | `jd.txt` | Path to a plain-text job description file. If omitted, falls back to `jd.txt` in the project root. If that also doesn't exist, reads from stdin (paste JD, then Ctrl+D / Ctrl+Z). |

---

## Running Without an API Key

If no valid `ANTHROPIC_API_KEY` is found, the agent prints:

```
[WARNING] No valid ANTHROPIC_API_KEY found (missing or placeholder).
Proceed with rule-based fallback? (y/n):
```

In fallback mode:
- The summary is used verbatim from `summary_variants[role_type]` (no LLM rewrite)
- Bullet compaction is skipped
- All other logic — JD scoring, skills selection, bullet ranking, project selection,
  overflow management — runs identically

---

## Skills Management

The agent scores every skill in `skills.json` against the JD and selects the most
relevant items per category.

**Adding a new skill manually:**
1. Add the skill name to the appropriate category's `all_items` list in `skills.json`
2. Add a `jd_tags` entry with a list of lowercase aliases the JD might use for it
3. Assign a reasonable position in `all_items` — items earlier in the list are used
   as defaults when no JD match occurs

**During generation, two prompts may appear:**

- `[SKILLS UPDATE] "skill" inferred from profile context. Consider adding to skills.json.`
  — The keyword was found in your experience or project bullets. It's included this run;
  add it to `skills.json` to make the match permanent.

- `[SKILLS MISSING] "skill" appears in JD but is not in your profile. Do you have experience with this? (y/n):`
  — If you answer `y`, the skill is added to `skills.json` automatically and included
  in this resume. If `n`, it is skipped entirely.

See `profile/SKILLS_POLICY.md` for the full no-fabrication policy.

---

## Output & Archive

| Folder | Contents | Lifecycle |
|--------|----------|-----------|
| `output/` | Current `.tex`, `.pdf`, and LaTeX side-files | Cleared at the start of every run |
| `archive/` | `Your_Name_Resume_Company_Role.pdf` copies | Never cleared; permanent record |

The archive suffix (`Company_Role`) is auto-derived from the JD — no prompt needed.

---

## Project Structure

```
resume-agent/
├── CLAUDE.md               <- Agent behavior specification (for Claude Code)
├── main.py                 <- Entry point: accepts JD, triggers full pipeline
├── agent.py                <- Core logic: JD analysis + content selection
├── renderer.py             <- LaTeX template filling + pdflatex compilation
│
├── profile/                <- Your data. Replace with your own information.
│   ├── identity.json       <- Name, contact info, title/summary variants, certs, awards
│   ├── skills.json         <- Full skill inventory with JD matching tags
│   ├── experience.json     <- Work history with bullet variants (ds / mle / research)
│   ├── projects.json       <- Project pool with relevance tags and bullet variants
│   ├── education.json      <- Education history (fixed)
│   ├── publications.json   <- Publications list (fixed)
│   └── SKILLS_POLICY.md    <- Rules for handling skills not in skills.json
│
├── templates/
│   ├── jakes_resume.tex    <- ATS-friendly LaTeX template (structure is fixed)
│   └── TEMPLATE_SPEC.md    <- Exact format required for each placeholder
│
├── output/                 <- Generated files land here (cleared before each run)
│   ├── resume_[timestamp].tex
│   ├── resume_[timestamp].pdf
│   └── Your_Name_Resume.pdf   <- canonical PDF after rename
│
└── archive/                <- Accepted resumes kept permanently
    └── Your_Name_Resume_[Company_Role].pdf
```

---

## License

MIT
