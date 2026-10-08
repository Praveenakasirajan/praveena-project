"""
resume_analyzer.py - Generic, Resume-Agnostic Parsing & Question Generation.
Supports PDF and DOCX formats across arbitrary candidate layouts.
Extracts:
- Candidate Info (name, email, phone, location, links)
- Categorized Skills:
  1. Programming Languages
  2. Core Computer Science
  3. Frameworks & Libraries
  4. Databases
  5. Web Technologies
  6. Cloud / DevOps
  7. Development Tools
  8. Design Tools
  9. Other Technical Skills
- Projects (titles, technologies, descriptions, responsibilities)
- Internships & Experience (roles, companies, durations, technologies, responsibilities)
- Education (degree, branch, institution, duration, scores)
- Certifications & Achievements
- Dynamic Role-Aware Skill Gap Analysis ('Not detected in the uploaded resume.')
- Genuine Resume-Grounded Question Generation with source_type & source_reference.
"""

import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Maximum file size: 10 MB
MAX_RESUME_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def validate_resume_file(file_bytes: bytes, filename: str) -> None:
    """Validate file extension, size, and non-emptiness."""
    if not filename:
        raise ValueError("Filename is required.")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported resume format '{ext}'. Only PDF and DOCX files are supported."
        )

    if len(file_bytes) == 0:
        raise ValueError("The uploaded resume file is empty.")

    if len(file_bytes) > MAX_RESUME_SIZE:
        raise ValueError(
            f"Resume file size ({len(file_bytes) / (1024*1024):.1f} MB) exceeds the 10 MB limit."
        )


def normalize_resume_text(raw_text: str) -> str:
    """
    Clean and normalize raw extracted text from PDF or DOCX:
    - Replace private-use bullet glyphs (\uf0b7, \u2022, etc.) with standard dashes.
    - Normalize unicode spaces, quotes, and hyphens.
    - Trim trailing whitespace per line while preserving structural linebreaks.
    """
    if not raw_text:
        return ""

    text = raw_text

    # Bullet point symbols
    bullet_chars = [
        "\uf0b7", "\uf0a7", "\uf0d8", "\u2022", "\u2023", "\u25e6",
        "\u2043", "\u2219", "\u25aa", "\u25cf", "\u25cb", "\u25a0", ""
    ]
    for b in bullet_chars:
        text = text.replace(b, "\n• ")

    # Non-breaking spaces and invisible characters
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Normalize dashes and quotes
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")

    # Clean lines
    lines = [line.strip() for line in text.split("\n")]
    # Consolidate multiple empty lines
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                cleaned_lines.append("")
                prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False

    return "\n".join(cleaned_lines).strip()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from PDF using pypdf, with layout-aware preservation."""
    try:
        import pypdf
    except ImportError:
        raise RuntimeError("pypdf library is not installed.")

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        if len(reader.pages) == 0:
            raise ValueError("The PDF document contains no pages.")

        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(text.strip())

        full_text = "\n\n".join(pages_text).strip()
        if not full_text:
            raise ValueError(
                "Could not extract any readable text from the PDF. It may be scanned or image-based."
            )

        normalized = normalize_resume_text(full_text)
        logger.info("Extracted %d characters from PDF resume.", len(normalized))
        return normalized
    except ValueError:
        raise
    except Exception as e:
        logger.exception("Failed to read PDF file: %s", e)
        raise ValueError(f"Corrupted or invalid PDF file: {str(e)}")


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract plain text from DOCX, including paragraphs and tables."""
    try:
        import docx
    except ImportError:
        raise RuntimeError("python-docx library is not installed.")

    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

        # Extract table text preserving row structure
        table_texts = []
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    table_texts.append(" | ".join(cells))

        all_text = "\n".join(paragraphs + table_texts).strip()
        if not all_text:
            raise ValueError("The DOCX document contains no readable text.")

        normalized = normalize_resume_text(all_text)
        logger.info("Extracted %d characters from DOCX resume.", len(normalized))
        return normalized
    except ValueError:
        raise
    except Exception as e:
        logger.exception("Failed to read DOCX file: %s", e)
        raise ValueError(f"Corrupted or invalid DOCX file: {str(e)}")


def extract_resume_text(file_bytes: bytes, filename: str) -> str:
    """Validate and extract normalized text from an uploaded resume file."""
    validate_resume_file(file_bytes, filename)
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext == ".docx":
        return extract_text_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


# ============================================================================
# GENERIC SECTION DETECTION
# ============================================================================

SECTION_PATTERNS = {
    "SUMMARY": re.compile(
        r"^(?:professional\s+summary|executive\s+summary|career\s+objective|summary|objective|about\s+me|profile)$",
        re.I,
    ),
    "EDUCATION": re.compile(
        r"^(?:education|academic\s+background|educational\s+qualifications?|academic\s+qualifications?|academics)$",
        re.I,
    ),
    "SKILLS": re.compile(
        r"^(?:technical\s+skills|tools\s*(?:&|and)\s*technologies|technical\s+expertise|skills\s*(?:&|and)\s*tools|skills|key\s+skills|core\s+competencies|technical\s+proficiencies|it\s+skills)$",
        re.I,
    ),
    "EXPERIENCE": re.compile(
        r"^(?:internship\s+experience|internships?|work\s+experience|professional\s+experience|experience|employment\s+history|work\s+history|industry\s+experience)$",
        re.I,
    ),
    "PROJECTS": re.compile(
        r"^(?:academic\s+projects?|personal\s+projects?|key\s+projects?|technical\s+projects?|selected\s+projects?|capstone\s+projects?|projects?)$",
        re.I,
    ),
    "CERTIFICATIONS": re.compile(
        r"^(?:certifications?|certificates?|licenses\s*(?:&|and)\s*certifications?|online\s+courses?|courses?\s*(?:&|and)\s*certifications?|courses?)$",
        re.I,
    ),
    "ACHIEVEMENTS": re.compile(
        r"^(?:achievements?|awards?\s*(?:&|and)\s*honors?|honors?\s*(?:&|and)\s*awards?|awards?|accomplishments?|extracurricular\s+activities|co-curricular\s+activities)$",
        re.I,
    ),
    "PUBLICATIONS": re.compile(
        r"^(?:publications?|research\s+papers?)$",
        re.I,
    ),
}


def segment_resume_sections(text: str) -> Dict[str, str]:
    """
    Segment resume into distinct semantic sections dynamically.
    Works for any section order or missing sections.
    """
    sections: Dict[str, List[str]] = {
        "HEADER": [],
        "SUMMARY": [],
        "EDUCATION": [],
        "SKILLS": [],
        "EXPERIENCE": [],
        "PROJECTS": [],
        "CERTIFICATIONS": [],
        "ACHIEVEMENTS": [],
        "PUBLICATIONS": [],
    }

    current_section = "HEADER"
    lines = text.split("\n")

    for line in lines:
        clean = line.strip()
        if not clean:
            continue

        # Prevent project / experience attributes from masquerading as top-level sections
        if current_section in ["PROJECTS", "EXPERIENCE"]:
            lower_clean = clean.lower()
            if any(lower_clean.startswith(attr) for attr in [
                "technologies:", "tech stack:", "tools:", "built with:",
                "role:", "duration:", "responsibilities:", "description:", "impact:"
            ]):
                sections[current_section].append(line)
                continue

        # 1. Check if the entire line is a section header (e.g. "TECHNICAL SKILLS" or "Projects:")
        clean_header = clean.strip(" :-\t")
        matched_sec = None
        remainder = ""

        if 2 <= len(clean_header) <= 45 and not clean.startswith("•") and not clean.endswith("."):
            for sec_name, pattern in SECTION_PATTERNS.items():
                if pattern.match(clean_header):
                    matched_sec = sec_name
                    break

        # 2. Check if line starts with a section header prefix followed by colon (e.g. "Projects: SecureBank Portal")
        if not matched_sec and ":" in clean and not clean.startswith("•"):
            parts = clean.split(":", 1)
            prefix = parts[0].strip(" :-\t")
            if 2 <= len(prefix) <= 45:
                for sec_name, pattern in SECTION_PATTERNS.items():
                    if pattern.match(prefix):
                        matched_sec = sec_name
                        remainder = parts[1].strip()
                        break

        if matched_sec:
            current_section = matched_sec
            if remainder:
                sections[current_section].append(remainder)
            continue

        sections[current_section].append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


# ============================================================================
# CANONICAL TECHNICAL SKILLS ONTOLOGY
# ============================================================================

# Exact Canonical Skills mapped to categories and search patterns
SKILLS_ONTOLOGY = {
    "languages": [
        ("Python", [r"\bpython\b"]),
        ("Java", [r"\bjava\b"]),
        ("C++", [r"\bc\+\+\b", r"\bcpp\b"]),
        ("C", [r"\bc\b"]),
        ("C#", [r"\bc#\b", r"\bcsharp\b"]),
        ("JavaScript", [r"\bjavascript\b", r"\bjs\b"]),
        ("TypeScript", [r"\btypescript\b", r"\bts\b"]),
        ("Go", [r"\bgolang\b", r"\bgo\b"]),
        ("Rust", [r"\brust\b"]),
        ("Kotlin", [r"\bkotlin\b"]),
        ("Swift", [r"\bswift\b"]),
        ("PHP", [r"\bphp\b"]),
        ("Ruby", [r"\bruby\b"]),
        ("SQL", [r"\bsql\b"]),
        ("R", [r"\br\b"]),
        ("Dart", [r"\bdart\b"]),
        ("Scala", [r"\bscala\b"]),
        ("Bash", [r"\bbash\b", r"\bshell\s+scripting\b"]),
    ],
    "core_cs": [
        ("Data Structures & Algorithms", [r"\bdata\s+structures\s*(?:&|and)\s*algorithms\b", r"\bdsa\b", r"\bdata\s+structures\b", r"\balgorithms\b"]),
        ("Object-Oriented Programming (OOP)", [r"\bobject[- ]oriented\s+programming\b", r"\boop\b", r"\boops\b"]),
        ("Database Management Systems (DBMS)", [r"\bdatabase\s+management\s+systems?\b", r"\bdbms\b"]),
        ("Operating Systems", [r"\boperating\s+systems?\b", r"\bos\b"]),
        ("Computer Networks", [r"\bcomputer\s+networks?\b", r"\bnetworking\b"]),
        ("System Design", [r"\bsystem\s+design\b"]),
        ("Compiler Design", [r"\bcompiler\s+design\b"]),
        ("Software Engineering Principles", [r"\bsoftware\s+engineering\b", r"\bsdlc\b", r"\bagile\b"]),
    ],
    "frameworks": [
        ("React", [r"\breact(?:\.js)?\b", r"\breactjs\b"]),
        ("Next.js", [r"\bnext(?:\.js)?\b", r"\bnextjs\b"]),
        ("Angular", [r"\bangular(?:\.js)?\b"]),
        ("Vue.js", [r"\bvue(?:\.js)?\b", r"\bvuejs\b"]),
        ("Node.js", [r"\bnode(?:\.js)?\b", r"\bnodejs\b"]),
        ("Express", [r"\bexpress(?:\.js)?\b"]),
        ("Django", [r"\bdjango\b"]),
        ("Flask", [r"\bflask\b"]),
        ("FastAPI", [r"\bfastapi\b"]),
        ("Spring Boot", [r"\bspring\s+boot\b", r"\bspringboot\b"]),
        ("Spring", [r"\bspring\s+framework\b", r"\bspring\b"]),
        ("Hibernate", [r"\bhibernate\b"]),
        (".NET", [r"\b\.net\b", r"\basp\.net\b"]),
        ("Redux", [r"\bredux\b"]),
        ("TensorFlow", [r"\btensorflow\b"]),
        ("PyTorch", [r"\bpytorch\b"]),
        ("Keras", [r"\bkeras\b"]),
        ("Scikit-learn", [r"\bscikit[- ]learn\b", r"\bsklearn\b"]),
        ("Pandas", [r"\bpandas\b"]),
        ("NumPy", [r"\bnumpy\b"]),
        ("OpenCV", [r"\bopencv\b"]),
        ("Flutter", [r"\bflutter\b"]),
    ],
    "databases": [
        ("PostgreSQL", [r"\bpostgresql\b", r"\bpostgres\b"]),
        ("MySQL", [r"\bmysql\b"]),
        ("MongoDB", [r"\bmongodb\b", r"\bmongo\b"]),
        ("Redis", [r"\bredis\b"]),
        ("SQLite", [r"\bsqlite\b"]),
        ("Oracle", [r"\boracle\s+db\b", r"\boracle\b"]),
        ("Cassandra", [r"\bcassandra\b"]),
        ("Elasticsearch", [r"\belasticsearch\b"]),
        ("DynamoDB", [r"\bdynamodb\b"]),
        ("Firebase", [r"\bfirebase\b"]),
        ("Prisma", [r"\bprisma\b"]),
        ("Neo4j", [r"\bneo4j\b"]),
        ("Supabase", [r"\bsupabase\b"]),
    ],
    "web": [
        ("HTML", [r"\bhtml(?:5)?\b"]),
        ("CSS", [r"\bcss(?:3)?\b"]),
        ("JavaScript", [r"\bjavascript\b"]),
        ("TypeScript", [r"\btypescript\b"]),
        ("Tailwind CSS", [r"\btailwind(?:\s+css)?\b"]),
        ("Bootstrap", [r"\bbootstrap\b"]),
        ("REST API", [r"\brest(?:ful)?\s+apis?\b", r"\brest\b"]),
        ("GraphQL", [r"\bgraphql\b"]),
        ("WebSockets", [r"\bwebsockets?\b"]),
    ],
    "cloud_devops": [
        ("AWS", [r"\baws\b", r"\bamazon\s+web\s+services\b"]),
        ("Azure", [r"\bazure\b", r"\bmicrosoft\s+azure\b"]),
        ("Google Cloud", [r"\bgoogle\s+cloud\b", r"\bgcp\b"]),
        ("Docker", [r"\bdocker\b"]),
        ("Kubernetes", [r"\bkubernetes\b", r"\bk8s\b"]),
        ("CI/CD", [r"\bci/cd\b", r"\bcontinuous\s+integration\b"]),
        ("Jenkins", [r"\bjenkins\b"]),
        ("Linux", [r"\blinux\b"]),
        ("Nginx", [r"\bnginx\b"]),
        ("Apache", [r"\bapache\b"]),
        ("Kafka", [r"\bkafka\b"]),
        ("RabbitMQ", [r"\brabbitmq\b"]),
    ],
    "tools": [
        ("Git", [r"\bgit\b"]),
        ("GitHub", [r"\bgithub\b"]),
        ("GitLab", [r"\bgitlab\b"]),
        ("Postman", [r"\bpostman\b"]),
        ("Android Studio", [r"\bandroid\s+studio\b"]),
        ("VS Code", [r"\bvs\s*code\b", r"\bvisual\s+studio\s+code\b"]),
        ("Jira", [r"\bjira\b"]),
        ("Maven", [r"\bmaven\b"]),
        ("Gradle", [r"\bgradle\b"]),
    ],
    "design": [
        ("Figma", [r"\bfigma\b"]),
        ("Canva", [r"\bcanva\b"]),
        ("Adobe XD", [r"\badobe\s+xd\b"]),
        ("Photoshop", [r"\bphotoshop\b"]),
        ("Illustrator", [r"\billustrator\b"]),
    ],
    "other": [
        ("PowerBI", [r"\bpower\s*bi\b"]),
        ("Tableau", [r"\btableau\b"]),
        ("Excel", [r"\bexcel\b"]),
        ("Machine Learning", [r"\bmachine\s+learning\b", r"\bml\b"]),
        ("Deep Learning", [r"\bdeep\s+learning\b"]),
        ("Artificial Intelligence", [r"\bartificial\s+intelligence\b", r"\bai\b"]),
        ("Computer Vision", [r"\bcomputer\s+vision\b"]),
        ("Natural Language Processing (NLP)", [r"\bnlp\b", r"\bnatural\s+language\s+processing\b"]),
    ],
}


def extract_categorized_skills(sections: Dict[str, str], full_text: str) -> Dict[str, List[str]]:
    """
    Extract technical skills supported by the resume text and organize them into
    the 9 canonical categories. Normalizes equivalent wording.
    Never hallucinates unmentioned skills.
    """
    skills_text = sections.get("SKILLS", "")
    projects_text = sections.get("PROJECTS", "")
    exp_text = sections.get("EXPERIENCE", "")

    # Primary search text is skills section + projects + experience + full text
    combined_lower = f"{skills_text}\n{projects_text}\n{exp_text}\n{full_text}".lower()

    categorized: Dict[str, List[str]] = {
        "languages": [],
        "core_cs": [],
        "frameworks": [],
        "databases": [],
        "web": [],
        "cloud_devops": [],
        "tools": [],
        "design": [],
        "other": [],
    }

    # Step 1: Scan for canonical skills across all categories
    for cat_name, skill_defs in SKILLS_ONTOLOGY.items():
        found = []
        for canonical_name, patterns in skill_defs:
            for pattern in patterns:
                # Match against word boundaries
                if re.search(pattern, combined_lower):
                    if canonical_name not in found:
                        found.append(canonical_name)
                    break
        categorized[cat_name] = found

    # Step 2: Also parse direct lines in SKILLS section if candidate defined custom categories
    # E.g. "Programming Languages: Java, Python"
    for line in skills_text.split("\n"):
        line = line.strip(" •-\t")
        if ":" in line:
            cat_header, items = line.split(":", 1)
            cat_header = cat_header.strip().lower()
            item_tokens = [t.strip() for t in re.split(r"[,|;]", items) if t.strip()]

            target_cat = "other"
            if "language" in cat_header:
                target_cat = "languages"
            elif "core" in cat_header or "computer science" in cat_header:
                target_cat = "core_cs"
            elif "framework" in cat_header or "library" in cat_header:
                target_cat = "frameworks"
            elif "database" in cat_header:
                target_cat = "databases"
            elif "web" in cat_header:
                target_cat = "web"
            elif "cloud" in cat_header or "devops" in cat_header:
                target_cat = "cloud_devops"
            elif "tool" in cat_header or "developer" in cat_header:
                target_cat = "tools"
            elif "design" in cat_header:
                target_cat = "design"

            for token in item_tokens:
                # Clean up parenthetical details
                cleaned_token = re.sub(r"\(.*?\)", "", token).strip()
                if 2 <= len(cleaned_token) <= 30 and not any(w in cleaned_token.lower() for w in ["proficient", "basic", "knowledge"]):
                    # If not already present in the target category, add it
                    if cleaned_token not in categorized[target_cat]:
                        categorized[target_cat].append(cleaned_token)

    return categorized


def extract_candidate_info(header_text: str, full_text: str) -> Dict[str, Optional[str]]:
    """Extract candidate name, email, phone, location, and social profiles dynamically."""
    info: Dict[str, Optional[str]] = {
        "name": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin": None,
        "github": None,
    }

    # Search for email
    email_match = re.search(r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b", full_text)
    if email_match:
        info["email"] = email_match.group(1).strip()

    # Search for phone
    phone_match = re.search(r"(?:(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+91[\s-]?\d{10}|\b\d{10}\b)", full_text)
    if phone_match:
        info["phone"] = phone_match.group(0).strip()

    # Search for LinkedIn & GitHub
    li_match = re.search(r"(linkedin\.com/in/[a-zA-Z0-9_-]+)", full_text, re.I)
    if li_match:
        info["linkedin"] = li_match.group(1).strip()

    gh_match = re.search(r"(github\.com/[a-zA-Z0-9_-]+)", full_text, re.I)
    if gh_match:
        info["github"] = gh_match.group(1).strip()

    # Candidate Name: inspect top lines of HEADER
    header_lines = [l.strip() for l in header_text.split("\n") if l.strip()]
    if not header_lines:
        header_lines = [l.strip() for l in full_text.split("\n") if l.strip()][:5]

    stop_words = {
        "resume", "curriculum", "vitae", "cv", "profile", "contact",
        "email", "phone", "github", "linkedin", "summary", "objective"
    }

    for line in header_lines[:4]:
        # Strip phone/email if combined in same line
        clean_line = re.sub(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+|\+?\d[\d -]{8,}\d|https?://\S+)", "", line)
        clean_line = re.sub(r"[|•,-]", " ", clean_line).strip()
        words = clean_line.split()
        if 1 <= len(words) <= 4:
            if not any(w.lower() in stop_words for w in words):
                if not any(char.isdigit() for char in clean_line):
                    info["name"] = " ".join(w.title() for w in words)
                    break

    # Location heuristic (e.g. city mentioned near contact info)
    loc_match = re.search(r"(?:Tiruppur|Coimbatore|Chennai|Bangalore|Bengaluru|Hyderabad|Pune|Mumbai|Delhi|Noida|Kolkata|Madurai|Salem|Erode)\b", header_text, re.I)
    if loc_match:
        info["location"] = loc_match.group(0).capitalize()

    return info


def extract_projects(projects_text: str) -> List[Dict[str, Any]]:
    """
    Extract ALL projects present in the projects section.
    Robust against multi-line wrapped titles, technologies, and bullet points.
    Captures:
    - title
    - technologies
    - description
    - responsibilities
    - source_reference
    """
    if not projects_text or not projects_text.strip():
        return []

    projects = []
    current_proj: Optional[Dict[str, Any]] = None
    prev_was_tech = False
    lines = projects_text.split("\n")

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        # Check if line indicates technologies
        tech_match = re.match(r"^(?:Technologies|Tech\s+Stack|Tools|Built\s+with)\s*[:\-]\s*(.*)$", line_clean, re.I)
        if tech_match:
            if current_proj:
                raw_techs = [t.strip() for t in re.split(r"[,|;]", tech_match.group(1)) if t.strip()]
                current_proj["technologies"].extend(raw_techs)
                prev_was_tech = line_clean.endswith(",")
            continue

        # Multi-line continuation of technologies list
        if current_proj and prev_was_tech and not line_clean.startswith("•") and not line_clean.startswith("-"):
            raw_techs = [t.strip() for t in re.split(r"[,|;]", line_clean) if t.strip()]
            current_proj["technologies"].extend(raw_techs)
            prev_was_tech = line_clean.endswith(",")
            continue

        prev_was_tech = False

        # Check if line is a bullet point or description
        is_bullet = line_clean.startswith("•") or line_clean.startswith("-") or line_clean.startswith("*")

        if is_bullet:
            bullet_text = line_clean.lstrip("•-* \t").strip()
            if current_proj and bullet_text:
                current_proj["responsibilities"].append(bullet_text)
                if not current_proj["description"]:
                    current_proj["description"] = bullet_text
            continue

        # Check if line continues the previous bullet point
        if current_proj and current_proj["responsibilities"]:
            prev_resp = current_proj["responsibilities"][-1]
            if line_clean[0].islower() or not prev_resp.endswith("."):
                current_proj["responsibilities"][-1] = f"{prev_resp} {line_clean}"
                if current_proj["description"] == prev_resp:
                    current_proj["description"] = current_proj["responsibilities"][-1]
                continue

        # Check if line looks like a Project Title
        # Must start with uppercase or digit, not action verb, length between 3 and 75, not ending in period
        is_action_verb = any(line_clean.lower().startswith(w) for w in ["developed", "implemented", "designed", "built", "created", "engineered", "responsible for"])
        if (line_clean[0].isupper() or line_clean[0].isdigit()) and 3 <= len(line_clean) <= 75 and not line_clean.endswith(".") and not is_action_verb:
            # If line has subtitle e.g. "CollegeFinder - Web Application", separate it
            title_part = line_clean
            technologies_in_header = []

            if "|" in line_clean:
                parts = [p.strip() for p in line_clean.split("|")]
                title_part = parts[0]
                if len(parts) > 1:
                    technologies_in_header = [t.strip() for t in re.split(r"[,/]", parts[1])]

            # Finalize previous project
            if current_proj and current_proj["title"]:
                projects.append(current_proj)

            current_proj = {
                "title": title_part,
                "technologies": technologies_in_header,
                "description": "",
                "responsibilities": [],
                "source_reference": title_part,
            }
        else:
            # Descriptive line under project
            if current_proj:
                if not current_proj["description"]:
                    current_proj["description"] = line_clean
                else:
                    current_proj["responsibilities"].append(line_clean)

    if current_proj and current_proj["title"]:
        projects.append(current_proj)

    return projects


def extract_internships_and_experience(experience_text: str) -> List[Dict[str, Any]]:
    """
    Extract ALL internship and work experience entries.
    Robust against multi-line wrapped role titles, company names, and bullet points.
    Captures:
    - role
    - company
    - duration
    - technologies
    - responsibilities
    - source_reference
    """
    if not experience_text or not experience_text.strip():
        return []

    entries = []
    current_entry: Optional[Dict[str, Any]] = None
    lines = experience_text.split("\n")

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        is_bullet = line_clean.startswith("•") or line_clean.startswith("-") or line_clean.startswith("*")

        if is_bullet:
            bullet_text = line_clean.lstrip("•-* \t").strip()
            if current_entry and bullet_text:
                current_entry["responsibilities"].append(bullet_text)
                # Look for technologies mentioned in the bullet
                for cat, skill_defs in SKILLS_ONTOLOGY.items():
                    for name, patterns in skill_defs:
                        if any(re.search(p, bullet_text.lower()) for p in patterns):
                            if name not in current_entry["technologies"]:
                                current_entry["technologies"].append(name)
            continue

        # Check if line continues the previous bullet point
        if current_entry and current_entry["responsibilities"]:
            prev_resp = current_entry["responsibilities"][-1]
            if line_clean[0].islower() or not prev_resp.endswith("."):
                current_entry["responsibilities"][-1] = f"{prev_resp} {line_clean}"
                continue

        # Check if line continues the company/duration header line before any bullets
        if current_entry and not current_entry["responsibilities"]:
            is_company_or_date = any(w in line_clean.lower() for w in [
                "solutions", "technologies", "inc", "ltd", "corp", "software", "202", "201"
            ]) or line_clean.startswith("(") or line_clean.endswith(")")
            if is_company_or_date:
                # Extract date in parentheses if present
                d_match = re.search(r"\(([^)]+)\)", line_clean)
                if d_match:
                    current_entry["duration"] = d_match.group(1).strip()
                    clean_extra = line_clean.replace(f"({current_entry['duration']})", "").strip()
                else:
                    clean_extra = line_clean

                if clean_extra:
                    current_entry["company"] = f"{current_entry['company']} {clean_extra}".strip()
                    current_entry["source_reference"] = f"{current_entry['role']} at {current_entry['company']}"
                continue

        # Check if line looks like an entry header:
        # e.g. "MERN Stack Intern | MIST Solutions (June 2026)"
        # or "Software Engineer at Google, 2023 - Present"
        is_header = any(w in line_clean.lower() for w in [
            "intern", "developer", "engineer", "trainee", "associate",
            "analyst", "consultant", "lead", "manager"
        ]) or ("|" in line_clean and any(w in line_clean.lower() for w in ["solutions", "technologies", "inc", "ltd", "corp", "software"]))

        if is_header and len(line_clean) <= 100:
            if current_entry:
                entries.append(current_entry)

            role = line_clean
            company = ""
            duration = ""
            technologies = []

            # Extract duration in parentheses e.g. "(June 2026)"
            date_match = re.search(r"\(([^)]+)\)", line_clean)
            if date_match:
                duration = date_match.group(1).strip()
                line_without_date = line_clean.replace(f"({duration})", "").strip()
            else:
                line_without_date = line_clean

            # Split role and company by | or ' at ' or ' - '
            if "|" in line_without_date:
                parts = [p.strip() for p in line_without_date.split("|")]
                role = parts[0]
                company = parts[1] if len(parts) > 1 else ""
            elif " at " in line_without_date.lower():
                parts = re.split(r"\s+at\s+", line_without_date, flags=re.I)
                role = parts[0].strip()
                company = parts[1].strip() if len(parts) > 1 else ""
            elif " - " in line_without_date:
                parts = [p.strip() for p in line_without_date.split(" - ")]
                role = parts[0]
                company = parts[1] if len(parts) > 1 else ""

            # Check technologies in role
            for cat, skill_defs in SKILLS_ONTOLOGY.items():
                for name, patterns in skill_defs:
                    if any(re.search(p, role.lower()) for p in patterns):
                        if name not in technologies:
                            technologies.append(name)

            ref = f"{role} at {company}" if company else role

            current_entry = {
                "role": role,
                "company": company,
                "duration": duration,
                "technologies": technologies,
                "responsibilities": [],
                "source_reference": ref,
            }
        else:
            if current_entry and line_clean:
                current_entry["responsibilities"].append(line_clean)

    if current_entry:
        entries.append(current_entry)

    return entries


def extract_education(education_text: str) -> List[Dict[str, Any]]:
    """
    Extract education credentials: degree, branch, institution, duration, CGPA/percentage.
    Never confuses institution names with technical skills.
    """
    if not education_text or not education_text.strip():
        return []

    entries = []
    current_edu: Optional[Dict[str, Any]] = None
    lines = education_text.split("\n")

    for line in lines:
        line_clean = line.strip(" •-\t")
        if not line_clean:
            continue

        # Check for degree lines
        is_degree = any(d in line_clean.lower() for d in [
            "bachelor", "master", "b.e", "b.tech", "m.e", "m.tech",
            "b.sc", "m.sc", "bca", "mca", "diploma", "higher secondary", "hsc", "sslc"
        ])

        if is_degree:
            if current_edu:
                entries.append(current_edu)

            degree = line_clean
            duration = ""
            branch = ""

            # Extract duration if separated by |
            if "|" in line_clean:
                parts = [p.strip() for p in line_clean.split("|")]
                degree = parts[0]
                if len(parts) > 1:
                    duration = parts[1]

            # Branch detection
            if " in " in degree.lower():
                branch = re.split(r"\s+in\s+", degree, flags=re.I)[-1].strip()

            current_edu = {
                "degree": degree,
                "branch": branch,
                "institution": "",
                "duration": duration,
                "score": "",
            }
            continue

        # Check for institution
        is_institution = any(i in line_clean.lower() for i in [
            "college", "university", "institute", "school", "vidyalaya", "academy"
        ])
        if is_institution and current_edu:
            if not current_edu["institution"]:
                current_edu["institution"] = line_clean
            continue

        # Check for CGPA / Percentage
        score_match = re.search(r"(?:cgpa|percentage|score|marks|gpa|hsc|sslc)\s*[:\-]?\s*([0-9.]+(?:%|/10)?)", line_clean, re.I)
        if score_match and current_edu:
            current_edu["score"] = line_clean
            continue

    if current_edu:
        entries.append(current_edu)

    return entries


def extract_certifications(cert_text: str) -> List[str]:
    """Extract certifications separately from technical skills."""
    if not cert_text or not cert_text.strip():
        return []

    certs = []
    lines = cert_text.split("\n")
    current_cert = ""

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        is_bullet = line_clean.startswith("•") or line_clean.startswith("-") or line_clean.startswith("*")
        content = line_clean.lstrip("•-* \t").strip()

        if is_bullet or not current_cert:
            if current_cert and len(current_cert) > 3:
                certs.append(current_cert)
            current_cert = content
        else:
            # Wrapped continuation line
            current_cert = f"{current_cert} {content}"

    if current_cert and len(current_cert) > 3:
        certs.append(current_cert)

    return certs


def extract_achievements(achieve_text: str) -> List[str]:
    """Extract achievements and awards separately from projects/experience."""
    if not achieve_text or not achieve_text.strip():
        return []

    achievements = []
    lines = achieve_text.split("\n")
    current_ach = ""

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        is_bullet = line_clean.startswith("•") or line_clean.startswith("-") or line_clean.startswith("*")
        content = line_clean.lstrip("•-* \t").strip()

        if is_bullet or not current_ach:
            if current_ach and len(current_ach) > 3:
                achievements.append(current_ach)
            current_ach = content
        else:
            current_ach = f"{current_ach} {content}"

    if current_ach and len(current_ach) > 3:
        achievements.append(current_ach)

    return achievements


# ============================================================================
# STRUCTURED RESUME PARSING (SINGLE SOURCE OF TRUTH)
# ============================================================================

def parse_resume_content(text: str) -> Dict[str, Any]:
    """
    Parse resume into an exhaustive, structured representation.
    Single Source of Truth for Resume Analysis, Role-Aware Skill Gaps, and Questions.
    """
    normalized_text = normalize_resume_text(text)
    sections = segment_resume_sections(normalized_text)

    # 1. Candidate Info
    candidate = extract_candidate_info(sections.get("HEADER", ""), normalized_text)

    # 2. Categorized Skills
    categorized_skills = extract_categorized_skills(sections, normalized_text)

    # Flattened unique skills list
    all_skills = []
    for cat, slist in categorized_skills.items():
        for s in slist:
            if s not in all_skills:
                all_skills.append(s)

    # 3. Projects
    projects = extract_projects(sections.get("PROJECTS", ""))

    # 4. Internships & Experience
    internships_and_exp = extract_internships_and_experience(sections.get("EXPERIENCE", ""))

    # 5. Education
    education = extract_education(sections.get("EDUCATION", ""))

    # 6. Certifications & Achievements
    certifications = extract_certifications(sections.get("CERTIFICATIONS", ""))
    achievements = extract_achievements(sections.get("ACHIEVEMENTS", ""))

    # Construct complete structured resume object
    structured = {
        "candidate": candidate,
        "summary": sections.get("SUMMARY", ""),
        "education": education,
        "skills": categorized_skills,
        "all_skills": all_skills,
        "projects": projects,
        "experience": internships_and_exp,
        "internships": [e for e in internships_and_exp if "intern" in e.get("role", "").lower()],
        "certifications": certifications,
        "achievements": achievements,
        "sections_found": [k for k, v in sections.items() if v],
        "raw_length": len(normalized_text),
    }

    # For seamless backwards compatibility with existing UI / DB models:
    structured["candidate_name"] = candidate.get("name")
    structured["programming_languages"] = categorized_skills.get("languages", [])
    structured["frameworks"] = categorized_skills.get("frameworks", [])
    structured["databases_tools"] = list(dict.fromkeys(
        categorized_skills.get("databases", []) +
        categorized_skills.get("tools", [])
    ))

    # Project titles list for simple views
    project_titles = [p["title"] for p in projects if isinstance(p, dict)]
    structured["projects_list"] = project_titles if project_titles else []

    # Experience titles list for simple views
    exp_titles = [e["source_reference"] for e in internships_and_exp if isinstance(e, dict)]
    structured["experience_list"] = exp_titles if exp_titles else []

    logger.info(
        "Structured resume parsed for '%s': %d skills, %d projects, %d internships, %d certs",
        candidate.get("name") or "Candidate",
        len(all_skills),
        len(projects),
        len(structured["internships"]),
        len(certifications),
    )

    return structured


# ============================================================================
# ROLE-AWARE SKILL GAP ANALYSIS
# ============================================================================

ROLE_SKILL_REQUIREMENTS = {
    "Java Developer": [
        "Java", "Spring Boot", "MySQL", "Hibernate", "REST API", "Git", "OOP", "DBMS"
    ],
    "Backend Developer": [
        "Python", "Java", "SQL", "REST API", "Docker", "Git", "DBMS", "PostgreSQL", "Microservices"
    ],
    "Full Stack Developer": [
        "JavaScript", "TypeScript", "React", "Node.js", "SQL", "HTML", "CSS", "Git", "REST API"
    ],
    "Software Engineer": [
        "Data Structures & Algorithms", "OOP", "DBMS", "Git", "System Design", "Operating Systems", "Computer Networks"
    ],
    "Data Analyst": [
        "Python", "SQL", "Pandas", "NumPy", "PowerBI", "Tableau", "Excel", "DBMS"
    ],
    "QA Engineer": [
        "Selenium", "Automation Testing", "Java", "Python", "Test Cases", "Postman", "Git", "API Testing"
    ],
}


def generate_resume_insights(parsed_data: Dict[str, Any], target_role: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate dynamic, evidence-based resume insights:
    - All detected skills organized into categories
    - Verified strengths
    - Role-aware skill gaps with phrasing: 'Not detected in the uploaded resume.'
    - Practical recommended improvements
    """
    all_skills = parsed_data.get("all_skills") or parsed_data.get("skills", [])
    if isinstance(all_skills, dict):
        # Flatten if dictionary
        flat_skills = []
        for v in all_skills.values():
            if isinstance(v, list):
                flat_skills.extend(v)
        all_skills = list(dict.fromkeys(flat_skills))

    skills_lower = set(s.lower() for s in all_skills)

    projects = parsed_data.get("projects", [])
    internships = parsed_data.get("internships", [])
    certs = parsed_data.get("certifications", [])
    achievements = parsed_data.get("achievements", [])
    education = parsed_data.get("education", [])

    # 1. Strengths
    strengths = []
    if len(projects) >= 2:
        p_name = projects[0]["title"] if isinstance(projects[0], dict) else str(projects[0])
        strengths.append(f"Demonstrated project portfolio with {len(projects)} distinct practical projects (e.g., '{p_name}').")
    elif len(projects) == 1:
        p_name = projects[0]["title"] if isinstance(projects[0], dict) else str(projects[0])
        strengths.append(f"Hands-on project experience with '{p_name}'.")

    if internships:
        first_role = internships[0]["role"] if isinstance(internships[0], dict) else str(internships[0])
        strengths.append(f"Real-world industry exposure through internship: {first_role}.")

    prog_langs = parsed_data.get("skills", {}).get("languages", []) if isinstance(parsed_data.get("skills"), dict) else parsed_data.get("programming_languages", [])
    if len(prog_langs) >= 2:
        strengths.append(f"Multi-language programming foundation in {', '.join(prog_langs[:3])}.")
    elif prog_langs:
        strengths.append(f"Core programming knowledge in {prog_langs[0]}.")

    fw = parsed_data.get("skills", {}).get("frameworks", []) if isinstance(parsed_data.get("skills"), dict) else parsed_data.get("frameworks", [])
    if fw:
        strengths.append(f"Modern framework familiarity including {', '.join(fw[:3])}.")

    dbs = parsed_data.get("skills", {}).get("databases", []) if isinstance(parsed_data.get("skills"), dict) else []
    if dbs:
        strengths.append(f"Database engineering foundation with {', '.join(dbs[:2])}.")

    if certs:
        strengths.append(f"Verified certifications: {certs[0]}.")

    if achievements:
        strengths.append(f"Recognized extracurricular/technical achievement: {achievements[0]}.")

    if not strengths:
        strengths.append("Foundational academic background in computer science and engineering.")

    # 2. Dynamic Skill Gaps (Role-Aware)
    role_to_check = target_role if (target_role and target_role != "None") else "Software Engineer"
    expected = ROLE_SKILL_REQUIREMENTS.get(role_to_check, ROLE_SKILL_REQUIREMENTS["Software Engineer"])

    skill_gaps = []
    detected_role_skills = []

    for req in expected:
        req_clean = req.lower()
        # Check if matched directly or via alias
        is_detected = req_clean in skills_lower
        if not is_detected:
            # Check partial or substring matching e.g. "DSA" vs "Data Structures & Algorithms"
            if req_clean == "dsa" and any("data structures" in s for s in skills_lower):
                is_detected = True
            elif req_clean == "oop" and any("object" in s for s in skills_lower):
                is_detected = True
            elif req_clean == "dbms" and any("database" in s for s in skills_lower):
                is_detected = True

        if is_detected:
            detected_role_skills.append(req)
        else:
            skill_gaps.append({
                "skill": req,
                "status": "Not detected in the uploaded resume.",
                "importance": f"Recommended for {role_to_check}",
            })

    # 3. Recommended Improvements
    recommendations = []
    if skill_gaps:
        missing_names = [g["skill"] for g in skill_gaps[:3]]
        recommendations.append(
            f"Consider demonstrating hands-on experience or coursework with {', '.join(missing_names)} to strengthen alignment for {role_to_check} positions."
        )

    if projects:
        recommendations.append(
            "Quantify project outcomes in your resume (e.g., latency reduction, user load, query optimization) to stand out in technical evaluations."
        )
    else:
        recommendations.append(
            "Add at least 1-2 end-to-end projects detailing your architectural choices, database schema, and challenges solved."
        )

    if not internships:
        recommendations.append(
            "Highlight open-source contributions or academic team projects to showcase collaborative engineering practice."
        )

    recommendations.append(
        "Be prepared to explain design decisions, tradeoffs, and debugging strategies for your highlighted projects."
    )

    return {
        "candidate_name": parsed_data.get("candidate", {}).get("name") or parsed_data.get("candidate_name"),
        "detected_skills": all_skills,
        "programming_languages": prog_langs,
        "frameworks": fw,
        "databases_tools": list(dict.fromkeys(
            (parsed_data.get("skills", {}).get("databases", []) if isinstance(parsed_data.get("skills"), dict) else []) +
            (parsed_data.get("skills", {}).get("tools", []) if isinstance(parsed_data.get("skills"), dict) else [])
        )),
        "all_categorized_skills": parsed_data.get("skills") if isinstance(parsed_data.get("skills"), dict) else {},
        "projects": projects,
        "experience": internships,
        "education": education,
        "certifications": certs,
        "achievements": achievements,
        "resume_strengths": strengths,
        "skill_gaps": skill_gaps,
        "detected_role_skills": detected_role_skills,
        "recommended_improvements": recommendations,
        "target_role": target_role or "None",
    }


# ============================================================================
# RESUME-GROUNDED INTERVIEW QUESTION GENERATION
# ============================================================================

def generate_resume_question(
    resume_or_parsed: Any,
    parsed_data: Optional[Dict[str, Any]] = None,
    difficulty: str = "Medium",
    question_index: int = 1,
    role: Optional[str] = None,
    target_role: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Generate an authentic technical interview question strictly grounded in the candidate's actual resume.
    Prioritizes:
    1. Candidate Projects (architecture, database, tradeoffs)
    2. Internships (responsibilities, tools, challenges)
    3. Stated Skills & Practical Application
    4. Certifications / Achievements
    Stores source_type and source_reference for absolute traceability.
    """
    from ai_evaluator import _call_gemini, _parse_json

    if isinstance(resume_or_parsed, dict) and parsed_data is None:
        parsed_data = resume_or_parsed
    elif isinstance(resume_or_parsed, str):
        if parsed_data is None:
            parsed_data = parse_resume_content(resume_or_parsed)
    else:
        parsed_data = parsed_data or {}

    active_role = role or target_role or kwargs.get("role") or ""

    projects = parsed_data.get("projects", [])
    internships = parsed_data.get("internships") or parsed_data.get("experience", [])
    all_skills = parsed_data.get("all_skills") or parsed_data.get("skills", [])
    if isinstance(all_skills, dict):
        flat_skills = []
        for v in all_skills.values():
            if isinstance(v, list):
                flat_skills.extend(v)
        all_skills = flat_skills

    certifications = parsed_data.get("certifications", [])

    # Format concise project summaries for Gemini prompt
    project_summaries = []
    for p in projects:
        if isinstance(p, dict):
            p_title = p.get("title", "Project")
            p_techs = ", ".join(p.get("technologies", []))
            p_desc = p.get("description", "")
            project_summaries.append(f"- {p_title} (Tech: {p_techs}): {p_desc}")
        else:
            project_summaries.append(f"- {str(p)}")

    intern_summaries = []
    for e in internships:
        if isinstance(e, dict):
            i_role = e.get("role", "Intern")
            i_comp = e.get("company", "")
            i_resp = "; ".join(e.get("responsibilities", [])[:2])
            intern_summaries.append(f"- {i_role} at {i_comp}: {i_resp}")
        else:
            intern_summaries.append(f"- {str(e)}")

    role_clause = f"Target Role Context: {active_role}\n" if active_role else ""
    prompt = f"""You are a senior technical interviewer conducting an authentic job interview.
Here is verified information extracted directly from the candidate's uploaded resume:

{role_clause}Projects:
{chr(10).join(project_summaries) if project_summaries else 'None specified'}

Internships / Experience:
{chr(10).join(intern_summaries) if intern_summaries else 'None specified'}

Technical Skills:
{', '.join(all_skills[:15]) if all_skills else 'None specified'}

Certifications:
{', '.join(certifications[:4]) if certifications else 'None specified'}

Target Difficulty: {difficulty}
Question Number: {question_index}

TASK:
Generate ONE technical interview question based on the candidate's actual projects, internships, or skills listed above.

CRITICAL RULES:
1. If projects exist, PRIORITIZE asking about a specific project by name, its database schema, architecture, or technical tradeoffs.
2. If internships exist, ask about their practical role, technical challenges, or tools used during that experience.
3. If asking about a skill, connect it to how they applied it in their practical project work.
4. Do NOT invent or hallucinate technologies or companies that do NOT appear above.
5. In 'source_reference', give the EXACT project name, company name, or skill name from the resume.

Return ONLY valid JSON with this exact structure:
{{
    "question": "The interview question text",
    "category": "Resume-Based",
    "difficulty": "{difficulty}",
    "source_type": "project" | "internship" | "skill" | "certification",
    "source_reference": "Name of project, company, or skill",
    "traceability": "Based on [item] from your resume"
}}
"""

    try:
        response_text = _call_gemini(prompt)
        data = _parse_json(response_text)
        if isinstance(data, dict) and data.get("question"):
            st = str(data.get("source_type", "project"))
            ref = str(data.get("source_reference", "Resume Content"))
            return {
                "question": str(data["question"]).strip(),
                "category": "Resume-Based",
                "difficulty": difficulty,
                "source_type": st,
                "source_reference": ref,
                "traceability": str(data.get("traceability", f"Based on {ref} from your resume")),
            }
    except Exception as e:
        logger.warning("Gemini resume question generation fallback: %s", e)

    # Deterministic Fallback Generator strictly grounded in extracted resume items:
    if projects:
        idx = (question_index - 1) % len(projects)
        proj = projects[idx]
        if isinstance(proj, dict):
            p_title = proj.get("title", "Project")
            techs = proj.get("technologies") or []
            tech_str = ", ".join(techs[:3]) if techs else "the specified stack"
            if difficulty == "Easy":
                q = f"In your project '{p_title}', could you walk me through the overall workflow and why you chose to use {tech_str}?"
            elif difficulty == "Hard":
                q = f"In your project '{p_title}', what were the most significant scalability, data management, or query optimization challenges you faced with {tech_str}?"
            else:
                q = f"In your project '{p_title}', can you walk me through the system architecture and how you integrated {tech_str} to solve the core problem?"
            return {
                "question": q,
                "category": "Resume-Based",
                "difficulty": difficulty,
                "source_type": "project",
                "source_reference": p_title,
                "traceability": f"Based on project '{p_title}' from your resume",
            }
        else:
            p_str = str(proj)
            return {
                "question": f"In your project '{p_str}', could you walk me through the system architecture and key technical decisions you made?",
                "category": "Resume-Based",
                "difficulty": difficulty,
                "source_type": "project",
                "source_reference": p_str,
                "traceability": f"Based on project '{p_str}' from your resume",
            }

    elif internships:
        idx = (question_index - 1) % len(internships)
        entry = internships[idx]
        if isinstance(entry, dict):
            i_role = entry.get("role", "Intern")
            i_comp = entry.get("company", "your organization")
            q = f"During your experience as {i_role} at {i_comp}, what was a key technical challenge you encountered and how did you resolve it?"
            return {
                "question": q,
                "category": "Resume-Based",
                "difficulty": difficulty,
                "source_type": "internship",
                "source_reference": f"{i_role} at {i_comp}" if i_comp else i_role,
                "traceability": f"Based on internship at {i_comp} from your resume",
            }
        else:
            return {
                "question": f"During your experience in '{str(entry)}', what were your primary responsibilities and key technical takeaways?",
                "category": "Resume-Based",
                "difficulty": difficulty,
                "source_type": "internship",
                "source_reference": str(entry),
                "traceability": f"Based on experience '{str(entry)}' from your resume",
            }

    elif all_skills:
        idx = (question_index - 1) % len(all_skills)
        skill = all_skills[idx]
        if difficulty == "Easy":
            q = f"You listed {skill} on your resume. Could you explain how you have applied {skill} in your practical development work?"
        elif difficulty == "Hard":
            q = f"Given your experience with {skill}, how do you troubleshoot concurrency, resource bottlenecks, or performance degradation in production?"
        else:
            q = f"Based on your background in {skill}, how do you structure your code and what best practices or design patterns do you follow?"
        return {
            "question": q,
            "category": "Resume-Based",
            "difficulty": difficulty,
            "source_type": "skill",
            "source_reference": skill,
            "traceability": f"Based on skill '{skill}' from your resume",
        }

    elif certifications:
        idx = (question_index - 1) % len(certifications)
        cert = certifications[idx]
        return {
            "question": f"You completed the certification '{cert}'. How has that learning influenced your practical engineering mindset and problem-solving?",
            "category": "Resume-Based",
            "difficulty": difficulty,
            "source_type": "certification",
            "source_reference": cert,
            "traceability": f"Based on certification '{cert}' from your resume",
        }

    return {
        "question": "Based on your uploaded resume, could you describe the most technically demanding software project you have built and the architectural decisions you made?",
        "category": "Resume-Based",
        "difficulty": difficulty,
        "source_type": "project",
        "source_reference": "Resume Projects",
        "traceability": "Based on projects section from your resume",
    }
