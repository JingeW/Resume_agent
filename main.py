import argparse
import re
import shutil
import sys
from pathlib import Path

import agent
import renderer

TEMPLATE_PATH = str(Path(__file__).parent / "templates" / "jakes_resume.tex")
OUTPUT_DIR    = str(Path(__file__).parent / "output")
ARCHIVE_DIR   = Path(__file__).parent / "archive"
DEFAULT_JD    = Path(__file__).parent / "jd.txt"


def main():
    parser = argparse.ArgumentParser(
        description="Generate a JD-optimised PDF resume from your profile data."
    )
    parser.add_argument(
        "--jd",
        metavar="FILE",
        help="Path to a plain-text (.txt) file containing the job description. "
             "Defaults to jd.txt in the project root if it exists; reads from stdin otherwise.",
    )
    args = parser.parse_args()

    # Resolve JD source: explicit flag → default jd.txt → stdin
    if args.jd:
        jd_path = Path(args.jd)
    elif DEFAULT_JD.exists():
        jd_path = DEFAULT_JD
        print(f"[INFO] Using default JD file: {jd_path}")
    else:
        jd_path = None

    if jd_path:
        if not jd_path.exists():
            print(f"[ERROR] JD file not found: {jd_path}", file=sys.stderr)
            sys.exit(1)
        jd_text = jd_path.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            print("Paste the job description below, then press Ctrl+D (or Ctrl+Z on Windows):")
        jd_text = sys.stdin.read()

    if not jd_text.strip():
        print("[ERROR] Job description is empty.", file=sys.stderr)
        sys.exit(1)

    # Clear all output files before generation
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    for f in output_path.iterdir():
        if f.is_file():
            f.unlink()

    # Initialise LLM mode (checks API key, prompts fallback if needed)
    if not agent.init_llm_mode():
        sys.exit(0)

    # Run the full content-selection pipeline
    content = agent.run_pipeline(jd_text)

    # Compile to PDF
    print()
    pdf_path = renderer.render(content, OUTPUT_DIR, TEMPLATE_PATH)

    print(f"\nResume saved to {pdf_path}")

    # Derive canonical filename from profile name (e.g. "Alex Chen" -> "Alex_Chen_Resume.pdf")
    def _clean(s):
        return re.sub(r"[^A-Za-z0-9]", "_", s.strip()).strip("_")
    profile_name     = content.get("identity", {}).get("name", "Resume")
    canonical_stem   = _clean(profile_name)
    canonical_fname  = f"{canonical_stem}_Resume.pdf"

    # Offer to rename to the canonical filename and archive a copy
    rename_dest = Path(pdf_path).parent / canonical_fname
    try:
        answer = input(f"\nRename to {canonical_fname}? (y/n): ").strip().lower()
    except EOFError:
        answer = "n"
        print("Non-interactive mode - skipping rename.")
    if answer == "y":
        company   = _clean(content.get("company", ""))
        job_title = _clean(content.get("job_title", ""))
        suffix = "_".join(p for p in [company, job_title] if p)
        if suffix:
            ARCHIVE_DIR.mkdir(exist_ok=True)
            archive_name = f"{canonical_stem}_Resume_{suffix}.pdf"
            shutil.copy2(pdf_path, str(ARCHIVE_DIR / archive_name))
            print(f"Archived  -> archive/{archive_name}")
        Path(pdf_path).replace(rename_dest)
        print(f"Renamed   -> output/{canonical_fname}")


if __name__ == "__main__":
    main()
