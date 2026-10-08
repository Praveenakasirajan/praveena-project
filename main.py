"""
main.py - FastAPI application backend for AI Interview Coach.
Handles question generation, resume upload & parsing, speech-to-text (Whisper),
answer evaluation (Gemini), video/look-away analysis (OpenCV), and report generation.
"""

# PyAV 19+ compatibility patch for faster-whisper (removes deprecated metadata_errors arg)
try:
    import av
    _orig_av_open = av.open
    def _compat_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _compat_av_open
except Exception:
    pass

import asyncio
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import re
import shutil
import time
from typing import Dict, Optional, Tuple

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel
import numpy as np
from sqlalchemy.orm import Session

from ai_evaluator import evaluate_interview_complete
from question_generator import (
    generate_question,
    get_last_selection,
    SUPPORTED_MODES,
    SUPPORTED_ROLES,
    SUPPORTED_TECHNICAL_SUBJECTS,
)
import question_store
from report_generator import generate_interview_report, generate_session_pdf_report
from resume_analyzer import (
    extract_resume_text,
    parse_resume_content,
    generate_resume_question,
    generate_resume_insights,
)
from video_analyzer import analyze_video

import database
from database import get_db
import models
import auth
import interview_manager
import communication_analyzer
import readiness_scorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
VIDEO_UPLOADS_DIR = UPLOADS_DIR / "videos"
AUDIO_UPLOADS_DIR = UPLOADS_DIR / "audio"
RESUME_UPLOADS_DIR = UPLOADS_DIR / "resumes"
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"}

# -------------------
# WHISPER MODEL
# -------------------

# -------------------
# WHISPER MODEL & PROMPT CONDITIONING
# -------------------

_whisper_model: Optional[WhisperModel] = None

# Default domain vocabulary for technical interviews & Indian academic context
DEFAULT_PROMPT_KEYWORDS = [
    # Academic & Engineering context
    "Bachelor of Engineering", "Computer Science Engineering", "CSE",
    "B.E.", "B.Tech", "Anna University",
    # Technical Interview core concepts
    "data structures", "algorithms", "object-oriented programming",
    "DBMS", "SQL", "normalization", "deadlock", "ACID properties",
    "operating systems", "computer networks", "system design",
    "FastAPI", "Python", "Java", "Spring Boot", "React", "Docker",
]


def preserve_proper_nouns(text: str, candidate_name: Optional[str] = None, college_name: Optional[str] = None) -> str:
    """Normalize minor phonetic misspellings of candidate's verified name or college from their profile/resume."""
    if not text:
        return ""
    cleaned = text
    if candidate_name and candidate_name.strip():
        first_name = candidate_name.strip().split()[0]
        # Common phonetic trailing variations
        if len(first_name) >= 4:
            pattern = rf"\b{re.escape(first_name[:-2])}[a-z]+\b"
            # If word is close to candidate first name, align to candidate profile
            def _repl(m):
                word = m.group(0)
                if abs(len(word) - len(first_name)) <= 2:
                    return first_name
                return word
            cleaned = re.sub(pattern, _repl, cleaned, flags=re.IGNORECASE)

    if college_name and college_name.strip():
        # E.g. align phonetic variants of candidate's verified institution
        col_clean = college_name.strip()
        main_tokens = [w for w in col_clean.split() if len(w) >= 4 and w.lower() not in ["engineering", "college", "university", "institute", "technology"]]
        if main_tokens:
            primary_token = main_tokens[0]
            if len(primary_token) >= 5:
                phonetic_col_pattern = rf"\b[A-Za-z]{{3,8}}\s+(?:Engineering\s+College|University|Institute)\b"
                if re.search(phonetic_col_pattern, cleaned, re.IGNORECASE) and not re.search(rf"\b{re.escape(primary_token)}\b", cleaned, re.IGNORECASE):
                    cleaned = re.sub(phonetic_col_pattern, col_clean, cleaned, count=1, flags=re.IGNORECASE)
    return cleaned


def build_transcription_prompt(
    question: Optional[str] = None,
    candidate_name: Optional[str] = None,
    college_name: Optional[str] = None,
    resume_data: Optional[dict] = None,
) -> str:
    """
    Build context-conditioned prompt for Faster-Whisper using genuine candidate/session metadata.
    Does NOT hardcode static names or fabricated institutions.
    """
    sentences = []
    if candidate_name and college_name:
        sentences.append(f"Hello everyone, I am {candidate_name}, pursuing my engineering degree at {college_name}.")
    elif candidate_name:
        sentences.append(f"Hello everyone, I am {candidate_name}.")
    elif college_name:
        sentences.append(f"I am pursuing my engineering degree at {college_name}.")
    else:
        sentences.append("Hello everyone, I am a software engineering candidate.")

    if resume_data and isinstance(resume_data, dict):
        skills = resume_data.get("skills", [])
        if skills:
            clean_skills = [s.strip() for s in skills if isinstance(s, str) and s.strip()]
            if clean_skills:
                sentences.append(f"My technical skills include {', '.join(clean_skills[:6])}.")
        projects = resume_data.get("projects", [])
        if projects:
            clean_projects = [p.strip() for p in projects if isinstance(p, str) and p.strip()]
            if clean_projects:
                sentences.append(f"My projects include {', '.join(clean_projects[:3])}.")

    if question and isinstance(question, str) and question.strip():
        sentences.append(f"The interview question is: {question.strip()}")

    return " ".join(sentences)


def determine_spoken_language(text: str, detected_lang: str, prob: float) -> str:
    """
    Determine whether spoken language is English ('en'), Tamil ('ta'), or mixed Tanglish ('mixed').
    Preserves original spoken language identity without inventing classifications.
    """
    has_tamil_script = bool(re.search(r"[\u0B80-\u0BFF]", text))
    has_english_words = bool(re.search(r"[a-zA-Z]{3,}", text))

    tanglish_patterns = [
        r"\b(?:naan|nan|ennoda|unga|ungala|padikiren|padikiran|padikren|padikran)\b",
        r"\b(?:irukku|irukken|irundhu|solren|panninen|panna|solla|vandhen)\b",
        r"\b(?:vanakkam|vanakam|nandri|seri|aama|illa|illai)\b",
    ]
    has_tanglish_latin = any(re.search(pat, text, re.IGNORECASE) for pat in tanglish_patterns)

    # Mixed Tamil + English (script mixed or phonetic Tanglish + English words)
    if has_tamil_script and has_english_words:
        return "mixed"
    if has_tanglish_latin and has_english_words:
        return "mixed"

    # Pure Tamil script
    if has_tamil_script:
        return "ta"

    # Acoustic detector flagged Tamil with high confidence
    if detected_lang == "ta" and prob > 0.6:
        if has_english_words:
            return "mixed"
        return "ta"

    # Standard English
    if detected_lang == "en":
        return "en"

    return detected_lang or "en"


def get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        model_name = os.getenv("WHISPER_MODEL", "small").strip()
        logger.info("Initializing Whisper model (%s, cpu, int8)...", model_name)
        _whisper_model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
        )
    return _whisper_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MySQL database schema
    try:
        database.init_db()
        logger.info("MySQL database initialized successfully.")
    except Exception as e:
        logger.warning("Could not initialize MySQL database on startup: %s", e)

    # Pre-warm Whisper model in background at startup so first user request doesn't suffer cold-start lag
    def _warmup():
        try:
            get_whisper_model()
            logger.info("Whisper model pre-warmed successfully.")
        except Exception as e:
            logger.warning("Could not pre-warm Whisper model: %s", e)

    asyncio.create_task(asyncio.to_thread(_warmup))
    yield


app = FastAPI(title="AI Interview Coach", lifespan=lifespan)

# Mount static files
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Redirect the browser's default favicon request to the app icon."""
    return RedirectResponse(url="/static/favicon.svg")

templates_dir = BASE_DIR / "templates"



def transcribe_audio(
    audio_path: str,
    question: Optional[str] = None,
    candidate_name: Optional[str] = None,
    college_name: Optional[str] = None,
    resume_data: Optional[dict] = None,
) -> Tuple[str, float, dict]:
    """
    Transcribe audio using Faster-Whisper with natural conversational prompt conditioning,
    beam search decoding, peak normalization, and language verification.
    Preserves original spoken language without forcing English translation when Tamil is spoken.
    """
    start_time = time.time()
    try:
        # Check if media container contains an audio stream
        try:
            import av
            with av.open(audio_path) as container:
                if len(container.streams.audio) == 0:
                    logger.info("File '%s' contains no audio stream; skipping transcription.", audio_path)
                    return "", 0.0, {
                        "language": "en",
                        "detected_language": "none",
                        "language_probability": 0.0,
                        "word_count": 0,
                        "duration": 0.0,
                        "transcription_time": round(time.time() - start_time, 2),
                        "status": "no_audio_stream",
                        "model": os.getenv("WHISPER_MODEL", "small").strip(),
                    }
        except Exception:
            pass

        model = get_whisper_model()
        initial_prompt = build_transcription_prompt(question, candidate_name, college_name, resume_data)

        # Audio preprocessing: decode to 16kHz float32 and apply peak normalization
        from faster_whisper.audio import decode_audio
        audio_data = decode_audio(audio_path, sampling_rate=16000)
        peak = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0
        if peak > 0:
            audio_data = (audio_data / peak) * 0.95

        # Detect spoken language: if confident Tamil (>= 0.85), preserve Tamil.
        # Otherwise target English to prevent Indian English prosody from drifting into Hindi/Marathi/Telugu.
        target_lang = "en"
        detected_lang = "en"
        lang_prob = 1.0
        try:
            detect_segment = audio_data[:480000] if len(audio_data) > 480000 else audio_data
            dl, dp, _ = model.detect_language(detect_segment)
            detected_lang = dl
            lang_prob = dp
            if dl == "ta" and dp >= 0.85:
                target_lang = "ta"
            else:
                target_lang = "en"
        except Exception as e:
            logger.warning("Language detection fallback to 'en': %s", e)

        # Transcribe without aggressive VAD to prevent clipping speech consonants and word boundaries
        segments, info = model.transcribe(
            audio_data,
            task="transcribe",
            language=target_lang,
            beam_size=5,
            best_of=5,
            patience=1.0,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
            initial_prompt=initial_prompt,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
            repetition_penalty=1.1,
        )

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)

        raw_text = " ".join(text_parts).strip()
        clean_text = preserve_proper_nouns(raw_text, candidate_name, college_name)

        duration = getattr(info, "duration", 0.0) or (len(audio_data) / 16000.0)
        final_lang = determine_spoken_language(clean_text, detected_lang, lang_prob)
        elapsed = time.time() - start_time
        words = len(clean_text.split())

        lang_info = {
            "language": final_lang,
            "detected_language": detected_lang,
            "language_probability": round(float(lang_prob), 3),
            "word_count": words,
            "duration": round(float(duration), 2),
            "transcription_time": round(elapsed, 2),
            "model": os.getenv("WHISPER_MODEL", "small").strip(),
        }

        logger.info(
            "Transcription complete: %d words in %.2fs (audio: %.1fs, lang: %s [prob: %.2f]) -> %s",
            words,
            elapsed,
            duration,
            final_lang,
            lang_prob,
            clean_text[:80] + ("..." if len(clean_text) > 80 else ""),
        )

        return clean_text, duration, lang_info

    except Exception as e:
        logger.exception("Transcription failed for %s: %s", audio_path, e)
        elapsed = time.time() - start_time
        empty_info = {
            "language": "en",
            "detected_language": "unknown",
            "language_probability": 0.0,
            "word_count": 0,
            "duration": 0.0,
            "transcription_time": round(elapsed, 2),
            "error": str(e),
            "model": os.getenv("WHISPER_MODEL", "small").strip(),
        }
        return "", 0.0, empty_info


fillers = ["um", "uh", "like", "actually", "you know"]


def count_fillers(text: str) -> dict:
    text_lower = text.lower()
    return {filler: text_lower.count(filler) for filler in fillers}


def calculate_wpm(text: str, duration_seconds: float) -> float:
    words = len(text.split())
    minutes = duration_seconds / 60.0
    if minutes <= 0:
        return 0.0
    return round(words / minutes, 1)


def score_interview(wpm: float, fillers_dict: dict, ai_eval: dict, word_count: int = 0) -> int:
    tech = ai_eval.get("technical_score", 0)
    comm = ai_eval.get("communication_score", 0)
    conf = ai_eval.get("confidence_score", 0)
    lead = ai_eval.get("leadership_score", 0)
    prob = ai_eval.get("problem_solving_score", 0)
    content_sum = tech + comm + conf + lead + prob

    # If answer was silent, empty, or scored 0 across all categories, score is 0
    if word_count < 3 or content_sum == 0:
        return 0

    total_fillers = sum(fillers_dict.values())
    speech_score = 100.0
    speech_score -= total_fillers * 2.0
    if wpm < 90.0:
        speech_score -= 10.0
    elif wpm > 190.0:
        speech_score -= 10.0
    speech_score = max(speech_score, 0.0)

    content_score = content_sum * 2.0
    final_score = (speech_score * 0.3) + (content_score * 0.7)
    return max(0, min(100, round(final_score)))


# -------------------
# FILE MANAGEMENT
# -------------------

def ensure_upload_directories():
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    RESUME_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def get_upload_path(filename: str) -> Path:
    safe_filename = Path(filename or "recorded_answer.webm").name
    stem = Path(safe_filename).stem
    file_ext = Path(safe_filename).suffix.lower()
    unique_filename = f"{int(time.time())}_{stem}{file_ext}"

    if file_ext in AUDIO_EXTENSIONS:
        upload_dir = AUDIO_UPLOADS_DIR
    elif file_ext in VIDEO_EXTENSIONS:
        upload_dir = VIDEO_UPLOADS_DIR
    else:
        upload_dir = UPLOADS_DIR

    return upload_dir / unique_filename


def save_uploaded_file(file: UploadFile) -> Path:
    ensure_upload_directories()
    file_path = get_upload_path(file.filename)
    logger.info("Saving uploaded file: %s -> %s", file.filename, file_path)

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


# -------------------
# ROUTES
# -------------------

@app.get("/")
async def root():
    """Serve the main HTML frontend."""
    template_file = templates_dir / "index.html"
    if template_file.exists():
        with open(template_file, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    return {"error": "Template index.html not found"}


@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Upload and parse candidate resume (PDF or DOCX).
    Extracts text, parses skills and projects, and stores resume in session context and MySQL.
    """
    try:
        file_bytes = await file.read()
        if not file_bytes:
            return JSONResponse(
                status_code=400,
                content={"error": "The uploaded resume file is empty."},
            )

        # Validate and extract text
        text = extract_resume_text(file_bytes, file.filename)
        parsed = parse_resume_content(text)
        insights = generate_resume_insights(parsed, target_role=None)

        # Save resume in session store
        question_store.set_resume(file.filename, text, parsed)

        # If user is logged in, also persist in MySQL resume_metadata table
        resume_record_id = None
        if request:
            token = auth.extract_token_from_request(request)
            if token:
                payload = auth.decode_access_token(token)
                if payload and "sub" in payload:
                    user_id = payload["sub"]
                    try:
                        # Save file to disk
                        save_dir = RESUME_UPLOADS_DIR
                        save_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = save_dir / f"{int(time.time())}_{Path(file.filename).name}"
                        with open(dest_path, "wb") as f_out:
                            f_out.write(file_bytes)

                        res_meta = models.ResumeMetadata(
                            user_id=user_id,
                            filename=file.filename,
                            file_path=str(dest_path),
                            candidate_name=parsed.get("candidate_name"),
                            skills=parsed.get("all_skills") or (parsed.get("skills") if isinstance(parsed.get("skills"), list) else []),
                            structured_skills=parsed.get("skills", {}) if isinstance(parsed.get("skills"), dict) else {},
                            projects=parsed.get("projects", []),
                            experience=parsed.get("experience", []),
                            certifications=parsed.get("certifications", []),
                            achievements=parsed.get("achievements", []),
                            education=parsed.get("education", []),
                            skill_gaps=insights.get("skill_gaps", []),
                            resume_strengths=insights.get("resume_strengths", []),
                            recommended_improvements=insights.get("recommended_improvements", []),
                        )
                        db.add(res_meta)
                        db.commit()
                        db.refresh(res_meta)
                        resume_record_id = res_meta.id
                    except Exception as dbe:
                        logger.warning("Could not persist resume metadata to MySQL: %s", dbe)

        logger.info(
            "Resume '%s' processed: %s skills, %s projects",
            file.filename,
            len(parsed.get("skills", [])),
            len(parsed.get("projects", [])),
        )

        return {
            "status": "success",
            "filename": file.filename,
            "resume_id": resume_record_id,
            "parsed": parsed,
            "insights": insights,
            "summary": f"Extracted {len(parsed.get('skills', []))} skills and {len(parsed.get('projects', []))} projects from {file.filename}",
        }
    except ValueError as ve:
        logger.warning("Resume validation failed: %s", ve)
        return JSONResponse(status_code=400, content={"error": str(ve)})
    except Exception as e:
        logger.exception("Failed to process resume: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process resume: {str(e)}"},
        )


@app.post("/clear-resume")
async def clear_resume():
    """Clear currently uploaded resume from session context."""
    question_store.clear_resume()
    return {"status": "success", "message": "Resume cleared from session."}


@app.get("/api/resume/latest")
async def api_latest_resume(
    target_role: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve candidate's latest uploaded resume and computed role-aware insights."""
    latest = db.query(models.ResumeMetadata).filter(
        models.ResumeMetadata.user_id == current_user.id
    ).order_by(models.ResumeMetadata.created_at.desc()).first()
    if not latest:
        return {"status": "none", "resume": None}

    clean_role = target_role if (target_role and target_role != "None") else None
    structured_skills = getattr(latest, "structured_skills", None) or {}
    all_skills = latest.skills or []

    parsed = {
        "candidate": {"name": latest.candidate_name or current_user.name},
        "candidate_name": latest.candidate_name or current_user.name,
        "skills": structured_skills,
        "all_skills": all_skills,
        "programming_languages": structured_skills.get("languages", []) if isinstance(structured_skills, dict) else [],
        "frameworks": structured_skills.get("frameworks", []) if isinstance(structured_skills, dict) else [],
        "databases_tools": list(dict.fromkeys(
            (structured_skills.get("databases", []) if isinstance(structured_skills, dict) else []) +
            (structured_skills.get("tools", []) if isinstance(structured_skills, dict) else [])
        )),
        "projects": latest.projects or [],
        "experience": latest.experience or [],
        "internships": [e for e in (latest.experience or []) if isinstance(e, dict) and "intern" in e.get("role", "").lower()],
        "certifications": latest.certifications or [],
        "achievements": getattr(latest, "achievements", []) or [],
        "education": latest.education or [],
    }
    insights = generate_resume_insights(parsed, target_role=clean_role)

    return {
        "status": "success",
        "resume": {
            "id": latest.id,
            "filename": latest.filename,
            "created_at": latest.created_at.strftime("%Y-%m-%d"),
            "candidate_name": latest.candidate_name or current_user.name,
            "skills": all_skills,
            "structured_skills": structured_skills,
            "projects": latest.projects or [],
            "experience": latest.experience or [],
            "internships": parsed["internships"],
            "certifications": latest.certifications or [],
            "achievements": getattr(latest, "achievements", []) or [],
            "education": latest.education or [],
            "insights": insights,
        }
    }


@app.post("/reset-session")
async def reset_session():
    """Reset all session state (question and resume)."""
    question_store.reset_session()
    return {"status": "success", "message": "Session reset."}


@app.api_route("/question", methods=["GET", "POST"])
async def get_question(request: Request):
    """
    Generate an interview question.
    Supports both standard category-based questions and personalized resume-based questions.
    """
    payload = {}
    if request.method == "POST":
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    category = payload.get("category") if isinstance(payload, dict) else None
    difficulty = payload.get("difficulty") if isinstance(payload, dict) else None
    use_resume = bool(payload.get("use_resume")) if isinstance(payload, dict) else False

    # Check if resume-based question is requested
    if category == "Resume-Based" or use_resume:
        if not question_store.current_resume_context:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "No resume uploaded. Please upload a PDF or DOCX resume to generate resume-based questions."
                },
            )

        diff = difficulty if difficulty in ("Easy", "Medium", "Hard") else "Medium"
        res = generate_resume_question(
            question_store.current_resume_context,
            question_store.current_parsed_resume,
            diff,
        )
        question = res["question"]
        question_store.set_question(
            question=question,
            category="Resume-Based",
            difficulty=diff,
            traceability=res.get("traceability", ""),
        )

        return {
            "question": question,
            "category": "Resume-Based",
            "difficulty": diff,
            "traceability": res.get("traceability", ""),
            "source_type": res.get("source_type", "project"),
            "resume_filename": question_store.current_resume_filename,
        }

    # Standard category question
    question = generate_question(category, difficulty)
    selection = get_last_selection()
    question_store.set_question(
        question=question,
        category=selection.get("category") or category or "General",
        difficulty=selection.get("difficulty") or difficulty or "Medium",
    )

    return {
        "question": question,
        "category": selection.get("category"),
        "difficulty": selection.get("difficulty"),
        "traceability": f"Standard {selection.get('category')} bank",
    }


@app.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    question: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    difficulty: Optional[str] = Form(None),
    traceability: Optional[str] = Form(None),
):
    """
    Receive recorded audio/video answer, transcribe with Whisper,
    analyze video with OpenCV (concurrently), and evaluate with Gemini.
    """
    try:
        file_path = save_uploaded_file(file)
    except Exception as e:
        logger.exception("Failed to save uploaded file: %s", file.filename)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to save uploaded file",
                "details": str(e),
            },
        )

    file_path_str = str(file_path)

    try:
        # Determine current interview question
        if question and question.strip():
            current_q = question.strip()
            question_store.current_question = current_q
        else:
            current_q = question_store.current_question or "Interview question"

        current_cat = category or question_store.current_category or "General"
        current_diff = difficulty or question_store.current_difficulty or "Medium"
        current_trace = traceability or question_store.current_traceability or ""

        # Run speech transcription and video analysis concurrently for high performance
        transcribe_task = asyncio.to_thread(
            transcribe_audio,
            file_path_str,
            current_q,
            question_store.current_parsed_resume or None,
        )
        video_task = asyncio.to_thread(analyze_video, file_path_str)

        (transcript, duration, lang_info), video_analysis = await asyncio.gather(
            transcribe_task,
            video_task,
        )

        # Filler analysis
        filler_stats = count_fillers(transcript)

        # Speech rate (WPM)
        wpm = calculate_wpm(transcript, duration)

        # Unified AI evaluation: scoring, feedback, gap analysis, and ideal answer in ONE call
        ai_evaluation = await asyncio.to_thread(
            evaluate_interview_complete,
            current_q,
            transcript,
            question_store.current_resume_context or None,
        )

        # Final score
        score = score_interview(wpm, filler_stats, ai_evaluation, len(transcript.split()))

        feedback_text = (
            ai_evaluation.get("feedback")
            or ai_evaluation.get("summary")
            or ""
        )

        return {
            "transcript": transcript,
            "language": lang_info.get("language", "en"),
            "transcript_debug": lang_info,
            "duration_seconds": duration,
            "question": current_q,
            "category": current_cat,
            "difficulty": current_diff,
            "traceability": current_trace,
            "wpm": wpm,
            "fillers": filler_stats,
            "score": score,
            "ai_evaluation": ai_evaluation,
            "feedback": feedback_text,
            "ideal_answer": ai_evaluation.get("ideal_answer", ""),
            "missing_points": ai_evaluation.get("missing_points", []),
            "improvement_suggestions": ai_evaluation.get("improvement_suggestions", []),
            "strengths": ai_evaluation.get("strengths", []),
            "weaknesses": ai_evaluation.get("weaknesses", []),
            "video_analysis": video_analysis,
        }

    except Exception as e:
        logger.exception("Failed to process interview answer: %s", e)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to process interview answer",
                "details": str(e),
            },
        )


@app.post("/download-report")
async def download_report(report_data: dict = Body(default_factory=dict)):
    """Generate and return comprehensive PDF interview report."""
    try:
        pdf_bytes = generate_interview_report(report_data or {})
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="ai-interview-report.pdf"'
            },
        )
    except Exception as e:
        logger.exception("Failed to generate PDF report: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to generate PDF report: {str(e)}"},
        )


# ============================================================================
# AUTHENTICATION API ROUTES (PBKDF2 HASHING & USER ISOLATION)
# ============================================================================

@app.post("/api/auth/register")
async def api_register(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Register a new user account with secure PBKDF2 password hashing."""
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    confirm_password = payload.get("confirm_password") or ""

    if not name:
        return JSONResponse(status_code=400, content={"error": "Full name is required."})
    if not email or "@" not in email:
        return JSONResponse(status_code=400, content={"error": "Valid email address is required."})
    if len(password) < 6:
        return JSONResponse(status_code=400, content={"error": "Password must be at least 6 characters long."})
    if confirm_password and password != confirm_password:
        return JSONResponse(status_code=400, content={"error": "Passwords do not match."})

    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return JSONResponse(status_code=400, content={"error": "An account with this email already exists."})

    pwd_hash = auth.hash_password(password)
    user = models.User(name=name, email=email, password_hash=pwd_hash)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth.create_access_token(user.id, user.email, user.name)
    res = JSONResponse(content={
        "status": "success",
        "message": "Account created successfully.",
        "user": {"id": user.id, "name": user.name, "email": user.email},
        "token": token,
    })
    res.set_cookie(key="session_token", value=token, httponly=True, max_age=86400 * 7, samesite="lax")
    return res


@app.post("/api/auth/login")
async def api_login(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Authenticate existing user credentials and return signed session token."""
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return JSONResponse(status_code=400, content={"error": "Email and password are required."})

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(password, user.password_hash):
        return JSONResponse(status_code=401, content={"error": "Invalid email or password."})

    token = auth.create_access_token(user.id, user.email, user.name)
    res = JSONResponse(content={
        "status": "success",
        "message": "Logged in successfully.",
        "user": {"id": user.id, "name": user.name, "email": user.email},
        "token": token,
    })
    res.set_cookie(key="session_token", value=token, httponly=True, max_age=86400 * 7, samesite="lax")
    return res


@app.get("/api/auth/me")
async def api_me(current_user: models.User = Depends(auth.get_current_user)):
    """Fetch profile of currently authenticated user."""
    return {
        "status": "success",
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
        }
    }


@app.post("/api/auth/logout")
async def api_logout():
    """Clear session token cookie."""
    res = JSONResponse(content={"status": "success", "message": "Logged out successfully."})
    res.delete_cookie(key="session_token")
    return res


# ============================================================================
# MULTI-QUESTION INTERVIEW SESSION API ROUTES (MYSQL PERSISTENCE & ISOLATION)
# ============================================================================

@app.get("/api/interview/config")
async def api_interview_config():
    """Return available interview modes, job roles, technical subjects, and question counts."""
    return {
        "modes": SUPPORTED_MODES,
        "roles": [r for r in SUPPORTED_ROLES if r != "None"],
        "technical_subjects": SUPPORTED_TECHNICAL_SUBJECTS,
        "question_counts": [1, 3, 5, 7],
        "difficulties": ["Easy", "Medium", "Hard"],
        "default_questions": 5,
    }


@app.post("/api/interview/start")
async def api_start_session(
    payload: dict = Body(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initialize a new multi-question interview session in MySQL.
    Strictly isolated to current_user.id.
    """
    try:
        mode = payload.get("mode") or "Technical"
        role = payload.get("role")
        if role in ["None", "none", "", None]:
            role = None
        technical_subject = payload.get("technical_subject")
        if technical_subject in ["None", "none", "", None]:
            technical_subject = None

        difficulty = payload.get("difficulty") or "Medium"
        total_q = int(payload.get("total_questions") or 5)
        if total_q not in [1, 3, 5, 7]:
            total_q = 5
        resume_id = payload.get("resume_id")

        session_data = interview_manager.create_interview_session(
            db=db,
            user=current_user,
            mode=mode,
            role=role,
            technical_subject=technical_subject,
            difficulty=difficulty,
            total_questions=total_q,
            resume_id=resume_id,
        )
        return {"status": "success", "session": session_data}
    except Exception as e:
        logger.exception("Failed to start interview session: %s", e)
        return JSONResponse(status_code=500, content={"error": f"Failed to start interview session: {str(e)}"})


@app.get("/api/interview/session/{session_id}")
async def api_get_session(
    session_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details and current active question for a session owned by current_user."""
    details = interview_manager.get_session_details(db, session_id, current_user.id)
    if not details:
        return JSONResponse(status_code=404, content={"error": "Interview session not found or access denied."})
    return {"status": "success", "session": details}


@app.post("/api/interview/submit-answer")
async def api_submit_answer(
    file: UploadFile = File(...),
    session_id: int = Form(...),
    question_id: int = Form(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process candidate answer in a multi-question session:
    1. Save audio/video
    2. Faster-Whisper transcription
    3. OpenCV video/look-away analysis concurrently
    4. Objective communication metrics (WPM, fillers - no accent bias)
    5. Mode-aware AI evaluation (STAR analysis for Behavioral mode)
    6. Record into MySQL tables
    7. Generate dynamic contextual follow-up if warranted or advance to next question
    """
    try:
        file_path = save_uploaded_file(file)
    except Exception as e:
        logger.exception("Failed to save answer media: %s", e)
        return JSONResponse(status_code=500, content={"error": "Failed to save media file", "details": str(e)})

    file_path_str = str(file_path)
    try:
        # Verify session ownership
        session = db.query(models.InterviewSession).filter(
            models.InterviewSession.id == session_id,
            models.InterviewSession.user_id == current_user.id,
        ).first()
        if not session:
            return JSONResponse(status_code=404, content={"error": "Interview session not found or access denied."})

        question = db.query(models.SessionQuestion).filter(
            models.SessionQuestion.id == question_id,
            models.SessionQuestion.session_id == session.id,
        ).first()
        if not question:
            return JSONResponse(status_code=404, content={"error": "Question not found in session."})

        # Fetch resume context if session mode is Resume-Based or Mixed
        resume_context = None
        college_name = None
        if session.mode in ["Resume-Based", "Mixed"]:
            latest_res = db.query(models.ResumeMetadata).filter(
                models.ResumeMetadata.user_id == current_user.id
            ).order_by(models.ResumeMetadata.created_at.desc()).first()
            if latest_res:
                resume_context = f"Skills: {latest_res.skills}\nProjects: {latest_res.projects}\nExperience: {latest_res.experience}"
                if latest_res.education:
                    for ed in latest_res.education:
                        if isinstance(ed, dict) and ed.get("institution"):
                            college_name = ed["institution"]
                            break
                        elif isinstance(ed, str) and any(kw in ed.lower() for kw in ["college", "university", "institute"]):
                            college_name = ed.strip()
                            break
            elif question_store.current_resume_context:
                resume_context = question_store.current_resume_context

        # Concurrently run speech transcription and video analysis
        transcribe_task = asyncio.to_thread(
            transcribe_audio,
            file_path_str,
            question.question_text,
            current_user.name,
            college_name,
            question_store.current_parsed_resume or None,
        )
        video_task = asyncio.to_thread(analyze_video, file_path_str)

        (transcript, duration, lang_info), video_analysis = await asyncio.gather(
            transcribe_task,
            video_task,
        )

        # Objective communication analysis
        filler_stats = count_fillers(transcript)
        comm_metrics = communication_analyzer.analyze_communication(
            transcript=transcript,
            duration_seconds=duration,
            filler_counts=filler_stats,
        )

        # AI evaluation (mode-aware)
        eval_result = await asyncio.to_thread(
            evaluate_interview_complete,
            question.question_text,
            transcript,
            resume_context,
            session.mode,
        )

        # Record answer and progression in MySQL
        progress_result = interview_manager.record_answer_and_progress(
            db=db,
            session_id=session.id,
            question_id=question.id,
            user_id=current_user.id,
            audio_path=file_path_str,
            video_path=file_path_str,
            transcript=transcript,
            duration=duration,
            evaluation=eval_result,
            video_metrics=video_analysis,
            comm_metrics=comm_metrics,
        )

        progress_result["transcript"] = transcript
        progress_result["video_analysis"] = video_analysis
        progress_result["communication_analysis"] = comm_metrics

        # If session completed, attach final session result details
        if progress_result.get("is_completed"):
            full_details = interview_manager.get_session_details(db, session.id, current_user.id)
            progress_result["final_summary"] = full_details.get("result")

        return {"status": "success", "data": progress_result}

    except Exception as e:
        logger.exception("Failed to process session answer: %s", e)
        return JSONResponse(status_code=500, content={"error": f"Failed to process answer: {str(e)}"})


@app.get("/api/interview/history")
async def api_interview_history(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch persistent interview history for current_user only."""
    history = interview_manager.get_user_interview_history(db, current_user.id)
    return {"status": "success", "history": history}


@app.get("/api/interview/details/{session_id}")
async def api_interview_details(
    session_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed breakdown for an interview session owned by current_user."""
    details = interview_manager.get_session_details(db, session_id, current_user.id)
    if not details:
        return JSONResponse(status_code=404, content={"error": "Session details not found or access denied."})
    return {"status": "success", "session": details}


@app.get("/api/interview/pdf/{session_id}")
async def api_session_pdf(
    session_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Generate and return PDF report for an interview session owned by current_user."""
    details = interview_manager.get_session_details(db, session_id, current_user.id)
    if not details:
        return JSONResponse(status_code=404, content={"error": "Session not found or access denied."})

    try:
        pdf_bytes = generate_session_pdf_report(details)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="interview_session_{session_id}.pdf"'
            },
        )
    except Exception as e:
        logger.exception("Failed to generate multi-question PDF report: %s", e)
        return JSONResponse(status_code=500, content={"error": f"Failed to generate PDF report: {str(e)}"})
