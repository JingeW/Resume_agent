import re
import subprocess
from datetime import datetime
from pathlib import Path


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain-text strings from profile JSON."""
    text = text.replace("&", r"\&")
    text = text.replace("%", r"\%")
    text = text.replace("#", r"\#")
    text = text.replace("_", r"\_")
    return text


def format_skills_lines(skills: list) -> str:
    """
    skills: list of (label, items_list) tuples in display order.
    Returns the SKILLS_LINES placeholder string.
    Last entry has no trailing \\.
    """
    lines = []
    for i, (label, items) in enumerate(skills):
        escaped_label = escape_latex(label)
        escaped_items = [escape_latex(item) for item in items]
        items_str = ", ".join(escaped_items)
        line = rf"\textbf{{{escaped_label}}}{{: {items_str}}}"
        if i < len(skills) - 1:
            line += r" \\"
        lines.append(line)
    return "\n     ".join(lines)


def format_exp_bullets(bullets: list) -> str:
    """
    Bullets are already LaTeX-escaped in the JSON source (e.g. 95\\% → 95\%).
    Do NOT apply escape_latex here.
    """
    return "\n        ".join(rf"\resumeItem{{{b}}}" for b in bullets)


def format_exp_dates(start: str, end: str) -> str:
    return f"{start} -- {end}"


def format_projects_block(projects: list) -> str:
    """Build the complete PROJECTS_BLOCK string for all selected projects."""
    blocks = []
    for proj in projects:
        escaped_title = escape_latex(proj["title"])
        escaped_subtitle = escape_latex(proj["subtitle"])
        url = proj.get("url", "").strip()
        if url:
            title_part = rf"\href{{{url}}}{{\textbf{{{escaped_title}}}}}"
        else:
            title_part = rf"\textbf{{{escaped_title}}}"
        heading = rf"{title_part} $|$ \emph{{{escaped_subtitle}}}"
        # Bullets are already LaTeX-escaped in JSON
        bullet_lines = "\n      ".join(rf"\resumeItem{{{b}}}" for b in proj["bullets"])
        block = (
            f"\\resumeProjectHeading\n"
            f"    {{{heading}}}\n"
            f"    \\resumeItemListStart\n"
            f"      {bullet_lines}\n"
            f"    \\resumeItemListEnd"
        )
        blocks.append(block)
    return "\n\n      ".join(blocks)


def format_education_block(degrees: list) -> str:
    blocks = []
    for deg in degrees:
        inst = escape_latex(deg["institution"])
        loc = escape_latex(deg["location"])
        degree = escape_latex(deg["degree"])
        dates = f"{deg['start']} -- {deg['end']}"
        block = (
            f"\\resumeSubheading\n"
            f"  {{{inst}}}{{{loc}}}\n"
            f"  {{{degree}}}{{{dates}}}"
        )
        note = deg.get("note", "").strip()
        if note:
            block += (
                f"\n\\vspace{{-3pt}}\\item[] "
                f"\\small\\textit{{{escape_latex(note)}}}"
            )
        blocks.append(block)
    return "\n    ".join(blocks)


def format_publications_list(pubs: list, author_name: str = None) -> str:
    lines = []
    for pub in pubs:
        authors = escape_latex(pub["authors"])
        if author_name:
            authors = authors.replace(author_name, f"\\textbf{{{author_name}}}")
        title = escape_latex(pub["title"])
        venue = escape_latex(pub["venue"])
        year = pub["year"]
        line = f"\\item \\small{{{authors} ``{title}'' \\textit{{{venue}}}. ({year})}}"
        lines.append(line)
    return "\n    ".join(lines)


def format_certifications_list(certs: list) -> str:
    lines = []
    for cert in certs:
        year = cert["year"]
        title = escape_latex(cert["title"])
        issuer = escape_latex(cert["issuer"])
        url = cert.get("url", "").strip()
        if url:
            title = f"\\href{{{url}}}{{{title}}}"
        line = f"\\item \\small{{{year} \\quad {title} --- {issuer}}}"
        lines.append(line)
    return "\n    ".join(lines)


def format_awards_list(awards: list) -> str:
    lines = []
    for award in awards:
        year = award["year"]
        title = escape_latex(award["title"])
        venue = escape_latex(award["venue"])
        line = f"\\item \\small{{{year} \\quad {title} --- {venue}}}"
        lines.append(line)
    return "\n    ".join(lines)


def build_placeholders(content: dict, no_links: bool = False) -> dict:
    """Map all <<PLACEHOLDER>> keys to their rendered string values."""
    identity = content["identity"]
    experience = content["experience"]

    if no_links:
        href_override = r"\hypersetup{draft=true}"
        scholar_entry = ""
    else:
        href_override = ""
        scholar_entry = (
            r" $|$ \href{" + identity["google_scholar_url"] + r"}{\underline{Google Scholar}}"
        )

    placeholders = {
        "NAME":          escape_latex(identity["name"]),
        "PHONE":         escape_latex(identity["phone"]),
        "EMAIL":         identity["email"],
        "WEBSITE_URL":   identity["website"],
        "LINKEDIN_URL":  identity["linkedin_url"],
        "GITHUB_URL":    identity["github_url"],
        "HREF_OVERRIDE": href_override,
        "SCHOLAR_ENTRY": scholar_entry,
        "SUMMARY":       escape_latex(content["summary"]),
        "SKILLS_LINES":  format_skills_lines(content["skills"]),
    }

    for i, pos in enumerate(experience, 1):
        n = str(i)
        placeholders[f"EXP{n}_COMPANY"]  = escape_latex(pos["company"])
        placeholders[f"EXP{n}_LOCATION"] = escape_latex(pos["location"])
        placeholders[f"EXP{n}_TITLE"]    = escape_latex(pos["title"])
        placeholders[f"EXP{n}_DATES"]    = format_exp_dates(pos["start"], pos["end"])
        placeholders[f"EXP{n}_BULLETS"]  = format_exp_bullets(pos["bullets"])

    placeholders["PROJECTS_BLOCK"]      = format_projects_block(content["projects"])
    placeholders["EDUCATION_BLOCK"]     = format_education_block(content["education"])
    name_parts = identity["name"].strip().split()
    author_abbrev = f"{name_parts[0][0]} {name_parts[-1]}" if len(name_parts) >= 2 else identity["name"]
    placeholders["PUBLICATIONS_LIST"]   = format_publications_list(content["publications"], author_abbrev)
    placeholders["CERTIFICATIONS_LIST"] = format_certifications_list(content["certifications"])
    placeholders["AWARDS_LIST"]         = format_awards_list(content["awards"])

    return placeholders


def fill_template(template_path: str, placeholders: dict) -> str:
    with open(template_path, encoding="utf-8") as f:
        text = f.read()
    for key, value in placeholders.items():
        text = text.replace(f"<<{key}>>", value)
    return text


def compile_pdf(tex_path: str, output_dir: str) -> tuple:
    """Run pdflatex once. Returns (returncode, combined output)."""
    cmd = [
        "pdflatex",
        "-interaction=nonstopmode",
        f"-output-directory={output_dir}",
        tex_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode, result.stdout + result.stderr
    except FileNotFoundError:
        raise RuntimeError(
            "pdflatex not found. Install a TeX distribution:\n"
            "  Windows: https://miktex.org/download\n"
            "  macOS:   brew install --cask mactex\n"
            "  Linux:   sudo apt-get install texlive-full"
        )


def get_page_count(pdf_path: str) -> int:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf not installed. Run: pip install pypdf")
    reader = PdfReader(pdf_path)
    return len(reader.pages)


def apply_next_overflow_fix(content: dict) -> bool:
    """
    Apply the next overflow reduction step from the CLAUDE.md priority table.
    Mutates content in place. Returns True if a fix was applied, False if exhausted.
    """
    projects = content["projects"]
    experience = content["experience"]

    # Priority 1: switch any project still on 4-bullet variant → short (3 bullets)
    for proj in projects:
        if len(proj["bullets"]) > 3 and "short" in proj["all_variants"]:
            proj["bullets"] = proj["all_variants"]["short"]
            return True

    # Priority 2: drop 4th project; restore remaining 3 to their preferred full variant
    if len(projects) >= 4:
        content["projects"] = projects[:3]
        role_type = content["role_type"]
        for proj in content["projects"]:
            avail = proj["all_variants"]
            if role_type in avail:
                proj["bullets"] = avail[role_type][:3]
            elif "full" in avail:
                proj["bullets"] = avail["full"][:3]
        return True

    # Priority 3: reduce PHA bullets by 1 (min 3)
    if len(experience[0]["bullets"]) > 3:
        experience[0]["bullets"] = experience[0]["bullets"][:-1]
        return True

    # Priority 4: reduce Postdoc bullets by 1 (min 2)
    if len(experience[1]["bullets"]) > 2:
        experience[1]["bullets"] = experience[1]["bullets"][:-1]
        return True

    # Priority 5: reduce PhD bullets by 1 (min 2)
    if len(experience[2]["bullets"]) > 2:
        experience[2]["bullets"] = experience[2]["bullets"][:-1]
        return True

    # Priority 6: remove last sentence from summary (min 2 sentences)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", content["summary"].strip()) if s]
    if len(sentences) > 2:
        content["summary"] = " ".join(sentences[:-1])
        return True

    return False


def render(content: dict, output_dir: str, template_path: str, no_links: bool = False) -> str:
    """
    Fill template, compile to PDF, enforce 2-page budget via overflow loop.
    Returns the path to the final PDF.
    """
    Path(output_dir).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "_nolinks" if no_links else ""
    tex_filename = f"resume_{timestamp}{suffix}.tex"
    pdf_filename = f"resume_{timestamp}{suffix}.pdf"
    tex_path = str(Path(output_dir).resolve() / tex_filename)
    pdf_path = str(Path(output_dir).resolve() / pdf_filename)
    output_dir_abs = str(Path(output_dir).resolve())

    final_pdf = pdf_path

    for attempt in range(12):
        placeholders = build_placeholders(content, no_links=no_links)
        tex_content = fill_template(template_path, placeholders)
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        if attempt == 0:
            print("[Compiling]  ", end="", flush=True)
        else:
            print("[Compiling]  (after overflow fix) ", end="", flush=True)

        compile_pdf(tex_path, output_dir_abs)
        print("pass 1... ", end="", flush=True)
        rc, log = compile_pdf(tex_path, output_dir_abs)
        print("pass 2... ", end="", flush=True)

        if rc != 0:
            print(f"\n[ERROR] pdflatex failed. Inspect: {tex_path}")
            raise RuntimeError(f"pdflatex error. Last log:\n{log[-2000:]}")

        if not Path(pdf_path).exists():
            print(f"\n[ERROR] PDF not produced. Inspect: {tex_path}")
            raise RuntimeError("PDF not created. Check LaTeX log.")

        pages = get_page_count(pdf_path)
        print(f"pages: {pages}", end="")

        if pages <= 2:
            print(" OK")
            break

        print(" (overflow)")
        if not apply_next_overflow_fix(content):
            print(f"[WARNING] Could not reduce to 2 pages. Saved .tex: {tex_path}")
            break

    print(f"  -> {final_pdf}")
    return final_pdf
