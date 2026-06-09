import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROFILE_DIR = Path(__file__).parent / "profile"
DUMMY_KEY = "your-api-key-here"

USE_LLM: bool = False


# ---------------------------------------------------------------------------
# API key check & LLM mode initialisation
# ---------------------------------------------------------------------------

def _has_valid_api_key() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return bool(key) and key != DUMMY_KEY


def init_llm_mode() -> bool:
    """
    Determine whether to use the Anthropic API.
    Prompts user for fallback confirmation when the key is absent/placeholder.
    Returns False if the user declines to continue.
    """
    global USE_LLM
    if _has_valid_api_key():
        USE_LLM = True
        return True

    print("[WARNING] No valid ANTHROPIC_API_KEY found (missing or placeholder).")
    try:
        answer = input("Proceed with rule-based fallback? (y/n): ").strip().lower()
    except EOFError:
        answer = "y"
        print("Non-interactive mode — defaulting to rule-based fallback.")
    if answer == "y":
        USE_LLM = False
        return True

    print(
        "\nTo use the LLM path:\n"
        "  1. Open .env in the project root\n"
        "  2. Replace 'your-api-key-here' with your Anthropic API key\n"
        "  3. Re-run the script\n"
    )
    return False


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------

def load_profile() -> dict:
    files = ["identity", "skills", "experience", "projects", "education", "publications"]
    profile = {}
    for name in files:
        path = PROFILE_DIR / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing required profile file: {path}")
        with open(path, encoding="utf-8") as f:
            profile[name] = json.load(f)
    return profile


# ---------------------------------------------------------------------------
# JD parsing — LLM path
# ---------------------------------------------------------------------------

def _parse_jd_llm(jd_text: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    prompt = (
        "Analyze the following job description and extract exactly these fields as valid JSON:\n"
        '- "role_type": one of "ds", "mle", or "research"\n'
        '  ds = Data Scientist / Analyst / Applied Scientist\n'
        '  mle = ML Engineer / AI Engineer / Software Engineer ML / MLOps\n'
        '  research = Research Scientist / AI Scientist\n'
        '- "company": the hiring company or organization name (empty string if not found)\n'
        '- "job_title": the exact job title from the posting (e.g. "AI Engineer", "Senior Data Scientist")\n'
        '- "tech_keywords": list of specific technical terms, lowercase '
        '(e.g. ["pytorch", "sql", "docker", "llm", "rag"])\n'
        '- "domain_keywords": domain context terms, lowercase '
        '(e.g. ["healthcare", "nlp", "clinical"])\n'
        '- "soft_keywords": soft-skill terms, lowercase '
        '(e.g. ["cross-functional", "stakeholder", "communication"])\n\n'
        "Job Description:\n"
        f"{jd_text}\n\n"
        "Respond with only valid JSON — no explanation, no markdown fences."
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    # Strip potential markdown fences in case model adds them
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# JD parsing — rule-based fallback
# ---------------------------------------------------------------------------

def _parse_jd_rule_based(jd_text: str, skills_data: dict) -> dict:
    text = jd_text.lower()

    # Role type: check for MLE and research signals; default to ds
    mle_signals = [
        "machine learning engineer", "ml engineer", "ai engineer",
        "mlops", "software engineer, ml", "software engineer ml",
        "software engineer, machine learning",
    ]
    research_signals = [
        "research scientist", "ai scientist", "applied research scientist",
        "research engineer",
    ]

    role_type = "ds"
    for sig in mle_signals:
        if sig in text:
            role_type = "mle"
            break
    if role_type == "ds":
        for sig in research_signals:
            if sig in text:
                role_type = "research"
                break

    # Extract tech keywords by matching known jd_tags against the JD text
    tech_keywords = []
    for cat in skills_data["categories"].values():
        for tags in cat["jd_tags"].values():
            for tag in tags:
                if tag in text and tag not in tech_keywords:
                    tech_keywords.append(tag)

    # Simple domain / soft extraction
    domain_signals = [
        "healthcare", "clinical", "medical", "nlp", "computer vision",
        "finance", "insurance", "bioinformatics", "genomics",
    ]
    soft_signals = [
        "cross-functional", "stakeholder", "communication",
        "collaboration", "mentoring", "leadership",
    ]

    domain_keywords = [s for s in domain_signals if s in text]
    soft_keywords = [s for s in soft_signals if s in text]

    # Best-effort company and job title extraction for rule-based path
    company = ""
    job_title = ""
    company_match = re.search(
        r"([A-Z][A-Za-z0-9&.,'\" -]{1,50})\s+is\s+(?:seeking|looking for|hiring)",
        jd_text,
    )
    if company_match:
        company = company_match.group(1).strip(" ,.")
    title_match = re.search(
        r"(?:seeking\s+a(?:n)?\s+(?:highly\s+\w+\s+)?|hiring\s+a(?:n)?\s+|for\s+(?:the\s+)?(?:role|position)\s+of\s+)"
        r"([A-Z][A-Za-z/ ,-]{2,50}?)(?:\s+to\b|\s+who\b|\s+that\b|\.|\n|$)",
        jd_text,
    )
    if title_match:
        job_title = title_match.group(1).strip()

    return {
        "role_type": role_type,
        "company": company,
        "job_title": job_title,
        "tech_keywords": tech_keywords,
        "domain_keywords": domain_keywords,
        "soft_keywords": soft_keywords,
    }


def parse_jd(jd_text: str, skills_data: dict) -> dict:
    if USE_LLM:
        try:
            return _parse_jd_llm(jd_text)
        except Exception as e:
            print(f"[WARNING] LLM JD parsing failed ({e}), using rule-based fallback.")
    return _parse_jd_rule_based(jd_text, skills_data)


# ---------------------------------------------------------------------------
# Summary rewriting — LLM path
# ---------------------------------------------------------------------------

def _rewrite_summary_llm(
    role_type: str, jd_data: dict, identity: dict, profile: dict
) -> str:
    import anthropic
    client = anthropic.Anthropic()
    base = identity["summary_variants"][role_type]
    word_count = len(base.split())
    min_w, max_w = int(word_count * 0.9), int(word_count * 1.1)

    # Brief experience context for grounding (truncated to keep prompt concise)
    exp_snippet = json.dumps(
        [
            {"title": p["title"], "company": p["company"],
             "highlights": p["bullets"][role_type][:2]}
            for p in profile["experience"]["positions"]
        ],
        indent=2,
    )[:1200]

    prompt = (
        f"Rewrite the resume summary below to better match the job description signals.\n\n"
        f"Rules:\n"
        f"1. Keep the same structure and length ({min_w}–{max_w} words).\n"
        f"2. Swap in JD-relevant domain/tech terms where natural.\n"
        f"3. Every factual claim must remain grounded in the candidate's actual experience.\n"
        f"4. Tighter is better — do not exceed the original word count.\n"
        f"5. Output only the rewritten paragraph, no explanation.\n\n"
        f"Base summary:\n{base}\n\n"
        f"JD signals:\n"
        f"  Tech:   {', '.join(jd_data.get('tech_keywords', []))}\n"
        f"  Domain: {', '.join(jd_data.get('domain_keywords', []))}\n"
        f"  Soft:   {', '.join(jd_data.get('soft_keywords', []))}\n\n"
        f"Candidate experience (for grounding):\n{exp_snippet}"
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _rewrite_summary_fallback(role_type: str, identity: dict) -> str:
    return identity["summary_variants"][role_type]


def rewrite_summary(
    role_type: str, jd_data: dict, identity: dict, profile: dict
) -> str:
    if USE_LLM:
        try:
            return _rewrite_summary_llm(role_type, jd_data, identity, profile)
        except Exception as e:
            print(f"[WARNING] LLM summary rewrite failed ({e}), using base summary.")
    return _rewrite_summary_fallback(role_type, identity)


# ---------------------------------------------------------------------------
# Title selection
# ---------------------------------------------------------------------------

def select_title(role_type: str, identity: dict) -> str:
    return identity["title_variants"][role_type]


# ---------------------------------------------------------------------------
# Skills building
# ---------------------------------------------------------------------------

CATEGORY_ORDER = {
    "mle":      ["engineering", "ai_ml", "analytics", "collaboration"],
    "ds":       ["analytics", "ai_ml", "engineering", "collaboration"],
    "research": ["ai_ml", "analytics", "engineering", "collaboration"],
}


def _score_item(item: str, cat_key: str, skills_data: dict, jd_lower: str) -> int:
    tags = skills_data["categories"][cat_key]["jd_tags"].get(item, [])
    return sum(1 for t in tags if t in jd_lower)


def build_skills(
    role_type: str, jd_text_lower: str, skills_data: dict
) -> list:
    """
    Returns list of (label, items_list) tuples in role-type priority order.
    Each line stays within ~110 chars (label + ": " + items).
    """
    result = []
    for cat_key in CATEGORY_ORDER[role_type]:
        cat = skills_data["categories"][cat_key]
        label = cat["label"]
        all_items = cat["all_items"]

        scored = [(item, _score_item(item, cat_key, skills_data, jd_text_lower))
                  for item in all_items]

        matched = sorted([(i, s) for i, s in scored if s > 0], key=lambda x: -x[1])
        unmatched = [(i, s) for i, s in scored if s == 0]
        ordered = [i for i, _ in matched] + [i for i, _ in unmatched]

        # Enforce ~110-char line limit (label + ": " = label_len + 2)
        max_items_chars = 110 - len(label) - 2
        selected = []
        for item in ordered:
            candidate = selected + [item]
            if len(", ".join(candidate)) <= max_items_chars:
                selected.append(item)
            else:
                break

        result.append((label, selected))

    return result


# ---------------------------------------------------------------------------
# Experience selection
# ---------------------------------------------------------------------------

def _rank_bullets_by_jd(bullets: list, jd_keywords: list) -> list:
    """Sort bullets by JD keyword match count (desc), preserving original order on ties."""
    def score(b):
        b_lower = b.lower()
        return sum(1 for kw in jd_keywords if kw in b_lower)
    indexed = [(score(b), i, b) for i, b in enumerate(bullets)]
    indexed.sort(key=lambda x: (-x[0], x[1]))
    return [b for _, _, b in indexed]


def select_experience(
    role_type: str, experience_data: dict, jd_keywords: list = None
) -> list:
    """Returns list of position dicts with JD-ranked bullets selected for role_type."""
    positions = experience_data["positions"]
    starting_counts = [6, 5, 3]  # PHA, Postdoc, PhD

    result = []
    for i, pos in enumerate(positions):
        all_bullets = pos["bullets"][role_type]
        ranked = _rank_bullets_by_jd(all_bullets, jd_keywords or [])
        count = min(starting_counts[i], len(ranked))
        result.append({
            "company":     pos["company"],
            "location":    pos["location"],
            "title":       pos["title"],
            "start":       pos["start"],
            "end":         pos["end"],
            "bullets":     ranked[:count],
            "all_bullets": ranked,
        })
    return result


# ---------------------------------------------------------------------------
# Project selection
# ---------------------------------------------------------------------------

def select_projects(role_type: str, jd_text_lower: str, projects_data: dict) -> list:
    """Score projects by relevance_tags match; return top 4 with role_type bullets."""
    scored = []
    for proj in projects_data["projects"]:
        score = sum(1 for tag in proj["relevance_tags"] if tag in jd_text_lower)
        scored.append((proj, score))

    scored.sort(key=lambda x: (-x[1], x[0]["priority"]))
    top4 = [p for p, _ in scored[:4]]

    result = []
    for proj in top4:
        avail = proj["bullets"]
        if role_type in avail:
            variant = role_type
            bullets = avail[role_type]
        else:
            variant = "short"
            bullets = avail["short"]
        bullets = bullets[:3]
        result.append({
            "id":           proj["id"],
            "title":        proj["title"],
            "subtitle":     proj["subtitle"],
            "bullets":      bullets,
            "all_variants": avail,
            "variant":      variant,
        })
    return result


# ---------------------------------------------------------------------------
# Bullet compaction (soft optimisation: shorten long bullets to ~1 line)
# ---------------------------------------------------------------------------

def _strip_latex(text: str) -> str:
    return text.replace(r'\%', '%').replace(r'\&', '&').replace(r'\#', '#').replace(r'\_', '_')


def _restore_latex(text: str) -> str:
    return (text.replace('&', r'\&').replace('%', r'\%')
                .replace('#', r'\#').replace('_', r'\_'))


def compact_bullets(content: dict, target_chars: int = 100) -> None:
    """
    Shorten bullets that exceed target_chars using one batched LLM call.
    Mutates content["experience"] and content["projects"] in place.
    No-op when USE_LLM is False or no long bullets exist.
    """
    if not USE_LLM:
        return

    # Collect (plain_text, location) for every over-limit bullet
    long: list[tuple[str, tuple]] = []
    for i, pos in enumerate(content["experience"]):
        for j, b in enumerate(pos["bullets"]):
            if len(_strip_latex(b)) > target_chars:
                long.append((_strip_latex(b), ("exp", i, j)))
    for i, proj in enumerate(content["projects"]):
        for j, b in enumerate(proj["bullets"]):
            if len(_strip_latex(b)) > target_chars:
                long.append((_strip_latex(b), ("proj", i, j)))

    if not long:
        return

    import anthropic
    client = anthropic.Anthropic()
    numbered = "\n".join(f"{k+1}. {b}" for k, (b, _) in enumerate(long))
    prompt = (
        f"Shorten each resume bullet to under {target_chars} characters. "
        "Keep the single most important metric or action verb phrase. "
        "Return ONLY a numbered list, one bullet per line, same order as input. "
        "Do not add any explanation.\n\n"
        f"{numbered}"
    )
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        lines = [l.strip() for l in response.content[0].text.strip().splitlines() if l.strip()]
        parsed = []
        for line in lines:
            m = re.match(r'^\d+[.)]\s*(.+)$', line)
            if m:
                parsed.append(m.group(1))

        if len(parsed) == len(long):
            for (_, loc), new_plain in zip(long, parsed):
                new_latex = _restore_latex(new_plain)
                kind, i, j = loc
                if kind == "exp":
                    content["experience"][i]["bullets"][j] = new_latex
                else:
                    content["projects"][i]["bullets"][j] = new_latex
            print(f"[Bullet Compact]  {len(parsed)} bullet(s) shortened to <={target_chars} chars")
        else:
            print(f"[WARNING] Bullet compaction: expected {len(long)} lines, got {len(parsed)}. Keeping originals.")
    except Exception as e:
        print(f"[WARNING] Bullet compaction failed ({e}). Keeping originals.")


# ---------------------------------------------------------------------------
# Skills policy check
# ---------------------------------------------------------------------------

def _all_known_tags(skills_data: dict) -> set:
    tags = set()
    for cat in skills_data["categories"].values():
        for tag_list in cat["jd_tags"].values():
            tags.update(t.lower() for t in tag_list)
    return tags


def _profile_text(experience_data: dict, projects_data: dict) -> str:
    parts = []
    for pos in experience_data["positions"]:
        for bullets in pos["bullets"].values():
            parts.extend(b.lower() for b in bullets)
    for proj in projects_data["projects"]:
        for variant in proj["bullets"].values():
            if isinstance(variant, list):
                parts.extend(b.lower() for b in variant)
    return " ".join(parts)


def handle_skills_policy(
    jd_data: dict,
    skills_data: dict,
    experience_data: dict,
    projects_data: dict,
) -> None:
    """
    Print [Skills Check] section.
    Prompt user for any JD tech keywords not matched in skills.json.
    Updates skills.json if user confirms a missing skill.
    """
    print("\n[Skills Check]")

    tech_terms = [t.lower() for t in jd_data.get("tech_keywords", [])]
    known_tags = _all_known_tags(skills_data)
    profile_txt = _profile_text(experience_data, projects_data)

    inferred = []
    missing = []
    for term in tech_terms:
        if term in known_tags:
            continue
        if term in profile_txt:
            inferred.append(term)
        else:
            missing.append(term)

    if not inferred and not missing:
        print("  All JD keywords matched in profile.")
        return

    for term in inferred:
        print(f'[SKILLS UPDATE] "{term}" inferred from profile context. '
              "Consider adding to skills.json.")

    for term in missing:
        try:
            answer = input(
                f'[SKILLS MISSING] "{term}" appears in JD but is not in your profile. '
                "Do you have experience with this? (y/n): "
            ).strip().lower()
        except EOFError:
            answer = "n"
            print(f'[SKILLS MISSING] "{term}" - skipping (non-interactive mode).')
        if answer == "y":
            _add_skill_to_json(term, skills_data)
            print(f'[SKILLS UPDATED] "{term}" added to skills.json.')


def _add_skill_to_json(skill: str, skills_data: dict) -> None:
    """Add a new skill to skills.json under the most appropriate category."""
    ai_hints = ["model", "learning", "neural", "bert", "gpt", "transformer",
                "llm", "nlp", "cv", "vision", "embedding"]
    cat_key = "ai_ml" if any(h in skill.lower() for h in ai_hints) else "engineering"

    skills_data["categories"][cat_key]["all_items"].append(skill)
    skills_data["categories"][cat_key]["jd_tags"][skill] = [skill.lower()]

    skills_path = PROFILE_DIR / "skills.json"
    with open(skills_path, "w", encoding="utf-8") as f:
        # Preserve the existing _comment key at top level
        json.dump(skills_data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_pipeline(jd_text: str) -> dict:
    """
    Execute the full content-selection pipeline.
    Prints [JD Analysis], [Content Selection], and [Skills Check] sections.
    Returns the assembled content dict for renderer.render().
    """
    profile = load_profile()
    identity       = profile["identity"]
    skills_data    = profile["skills"]
    experience_data = profile["experience"]
    projects_data  = profile["projects"]
    education_data = profile["education"]
    publications   = profile["publications"]

    jd_lower = jd_text.lower()

    # Step 1: Parse JD
    jd_data = parse_jd(jd_text, skills_data)
    role_type = jd_data["role_type"]

    print("\n[JD Analysis]")
    print(f"  Company:       {jd_data.get('company') or '(unknown)'}")
    print(f"  Job title:     {jd_data.get('job_title') or '(unknown)'}")
    print(f"  Role type:     {role_type}")
    print(f"  Tech keywords: {', '.join(jd_data.get('tech_keywords', [])) or '—'}")
    print(f"  Domain:        {', '.join(jd_data.get('domain_keywords', [])) or '—'}")
    print(f"  Soft skills:   {', '.join(jd_data.get('soft_keywords', [])) or '—'}")

    # Step 2: Title + Summary
    title   = select_title(role_type, identity)
    summary = rewrite_summary(role_type, jd_data, identity, profile)

    # Step 3: Skills
    skills = build_skills(role_type, jd_lower, skills_data)

    # Step 4: Experience bullets (JD-ranked)
    jd_keywords = jd_data.get("tech_keywords", []) + jd_data.get("domain_keywords", [])
    experience = select_experience(role_type, experience_data, jd_keywords)

    # Step 5: Projects
    projects = select_projects(role_type, jd_lower, projects_data)

    cat_labels = [label for label, _ in skills]
    cat_order_str = " -> ".join(cat_labels)

    print("\n[Content Selection]")
    print(f"  Title:    {title}")
    print(f"  Projects: {', '.join(p['id'] for p in projects)}")
    print(f"  Skills categories order: {cat_order_str}")

    # Step 6 / Skills policy check
    handle_skills_policy(jd_data, skills_data, experience_data, projects_data)

    content = {
        "role_type":    role_type,
        "company":      jd_data.get("company", ""),
        "job_title":    jd_data.get("job_title", ""),
        "identity":     identity,
        "title":        title,
        "summary":      summary,
        "skills":       skills,
        "experience":   experience,
        "projects":     projects,
        "education":    education_data["degrees"],
        "publications": publications["publications"],
        "certifications": identity["certifications"],
        "awards":       identity["awards"],
    }

    # Step 7: Compact long bullets (soft optimisation)
    compact_bullets(content, target_chars=110)

    return content
