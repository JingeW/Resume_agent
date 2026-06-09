# Skills Policy

## Core Principle
The skills section must truthfully reflect the candidate's actual experience.
Do not fabricate skills, tools, or technologies not present in the profile files.

## How the Agent Handles JD Keywords

### Case 1: Skill is already in `skills.json`
Include it normally — no action needed.

### Case 2: Skill is not in `skills.json`, but evidence exists in `experience.json` or `projects.json`
(e.g., the technology appears in a bullet point)

Include the skill in this run's output. Print a terminal notice:
```
[SKILLS UPDATE] "{skill}" inferred from profile context. Consider adding to skills.json.
```

### Case 3: Skill is not in `skills.json` and no evidence exists in any profile file
Do not include it in the resume.

Print a prompt asking the candidate to confirm:
```
[SKILLS MISSING] "{skill}" appears in JD but is not in your profile. Do you have experience with this? (y/n)
```
- If **y**: add the skill to the appropriate category in `skills.json` (with reasonable
  `jd_tags`) and include it in this run's output.
- If **n**: skip entirely — do not include in the resume.

---

## Skills Layout Constraint
Each category line (label + items) must fit within approximately **110 characters**.
After selecting items, the agent estimates the line length and drops the lowest-scored
item, repeating until the line fits.

---

## `jd_tags` Format
Each skill in `skills.json` has a `jd_tags` list — lowercase keyword aliases that
the agent matches against the JD text (case-insensitive). When adding a new skill,
always include reasonable aliases:

```json
"Docker": ["docker", "container", "containerization"]
```
