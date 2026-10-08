# AI Interview Coach — Intelligent Multi-Modal Mock Interview & Readiness Platform

An end-to-end, database-backed mock interview platform that simulates realistic technical, HR, behavioral, and resume-grounded interviews. Powered by **FastAPI**, **Faster-Whisper** speech transcription, **OpenCV** facial gaze tracking, **Google Gemini** generative evaluation, and **MySQL** persistent storage with strict user data isolation.

---

## 1. Project Title
**AI Interview Coach: Intelligent Multi-Modal Mock Interview & Readiness Platform**

---

## 2. Project Overview
AI Interview Coach enables students and software engineering job seekers to practice job interviews in an authentic, structured simulation environment. Rather than evaluating isolated questions with synthetic metrics, the platform conducts sequential sessions tailored to primary interview modes and optional technical subjects or job roles, generates dynamic follow-up questions from the candidate's actual answers, records objective speech pacing and verbal filler metrics without accent bias, visualizes gaze stability using computer vision, and computes a deterministic Interview Readiness Score backed by a persistent MySQL relational database.

---

## 3. Problem Statement
Job candidates preparing for modern engineering and software roles face significant preparation obstacles:
1. **Lack of realistic practice sessions:** Most online tools ask one-off questions without follow-up questions, multi-question pacing, or interview flow.
2. **Subjective or biased feedback:** Candidates frequently receive vague feedback or unfair penalties based on regional accents or pronunciation.
3. **Absence of non-verbal awareness:** Candidates are unaware of look-away habits, gaze drift, or head instability that affect presentation confidence.
4. **Fabricated or inaccurate computer vision results:** Many mock interview platforms return arbitrary 95% scores even when no human face is present on camera.
5. **No persistent readiness tracking:** Without persistent history and explainable metrics, candidates cannot measure concrete improvement over time.

---

## 4. Main Objectives
- Provide realistic interview sessions (1, 3, 5, or 7 questions) driven by **Interview Mode** as the primary selection.
- Support deep technical subjects (Java, Python, C, C++, DSA, DBMS / SQL, OS, CN, OOP, System Design, General) that produce authentic domain-specific questions.
- Treat Job Role as an **optional context** that complements, but never overrides, the technical domain or interview mode.
- Ground interview questions directly in candidate resumes with explicit source traceability (`source_type`, `source_reference`).
- Deliver evidence-based video analysis with **zero false positives**: report look-away event start/end timestamps, durations, and directions, or state "Insufficient visual evidence" when visual data is lacking.
- Transcribe spoken answers reliably using Faster-Whisper with dynamic user context and without crude replacement dictionaries.
- Deliver objective, non-biased speech communication metrics (WPM, filler-word counts) with **zero accent discrimination**.
- Persist all sessions, evaluations, and transcripts in a relational MySQL database with strict user data isolation.
- Compute a deterministic, explainable Interview Readiness Score (0–100) to gauge mock interview preparedness.

---

## 5. Key Architecture & Tech Stack
- **Backend:** FastAPI, Uvicorn, Python 3.12/3.13
- **Database:** MySQL 8.0+ via SQLAlchemy 2.0 ORM & PyMySQL
- **Speech-to-Text:** Faster-Whisper (`small` model, int8 CPU/CUDA, dynamic prompt conditioning)
- **Computer Vision:** OpenCV Haar Cascade facial detection, pupil/eye region tracking, and temporal gaze state machine
- **AI Evaluation & Follow-ups:** Google Gemini API (`gemini-flash-lite-latest`) with structured JSON schema and deterministic rule-based fallbacks
- **PDF Generation:** ReportLab
- **Frontend:** Vanilla HTML5, CSS3 (White `#FFFFFF`, Primary Violet `#6C3AED`, Light Violet `#EDE9FE`), and JavaScript (ES6+ modular state)

---

## 6. Interview Modes (Primary Selection)
The platform establishes **Interview Mode** as the primary interview context:

| Mode | Focus & Purpose | Example Question |
| :--- | :--- | :--- |
| **Technical** | Core domain depth, algorithmic trade-offs, language internals, and systems architecture. Can be paired with a Technical Subject. | "What is the difference between String, StringBuilder, and StringBuffer in Java regarding immutability and thread safety?" |
| **HR** | Self-introduction, career aspirations, strengths, weaknesses, conflict handling, and adaptability. | "Where do you see yourself in three to five years in your software engineering career?" |
| **Behavioral** | Situation-based scenarios evaluated via the **STAR methodology** (Situation, Task, Action, Result). | "Tell me about a time you had to explain a complex technical concept to a non-technical peer or stakeholder. How did you ensure clarity?" |
| **Resume-Based** | Questions dynamically grounded in the candidate's uploaded PDF/DOCX resume projects, skills, and internships. | "In your CollegeFinder project, you built a university recommendation portal using Java and Spring Boot with a MySQL backend. Can you walk me through the database schema design you used?" |
| **Mixed** | A comprehensive full-mock simulation blending HR, Technical, Resume-grounded, and Behavioral questions. | Balanced interview simulating a multi-round hiring process. |

---

## 7. Technical Domain / Subject Selection
When **Technical Mode** is selected, candidates can choose a specific technical domain:
- **Java** (JVM memory model, Garbage Collection, Collections, HashMap, multithreading, Exception handling, Streams, Spring Boot)
- **Python** (GIL, generators, decorators, memory management, asyncio)
- **C** (Pointers, manual memory allocation, stack vs heap, structs)
- **C++** (RAII, virtual functions, smart pointers, templates, STL)
- **DSA** (Time/space complexity, Linked Lists, Trees, Graphs, BFS/DFS, Sorting, Dynamic Programming)
- **DBMS / SQL** (Indexing, B+ Trees, ACID, Transactions, Normalization 1NF–3NF, Window functions, Joins)
- **Operating Systems** (Process vs Thread, Paging, Page Faults, Virtual Memory, Deadlocks)
- **Computer Networks** (TCP 3-way handshake, OSI layers, DNS, HTTP/HTTPS, WebSockets)
- **OOP** (Encapsulation, Inheritance, Polymorphism, Abstraction, SOLID principles)
- **System Design** (Microservices, Load Balancing, Rate Limiting, Caching, CAP theorem)
- **General Technical** (Balanced multi-domain engineering interview)

Questions generated are guaranteed to test the selected domain directly.

---

## 8. Optional Job Role Context
Job Role is **optional** and never forced. The UI provides:
`Job Role: [ None / Select Job Role ▼ ]`

Available Roles:
- Java Developer
- Backend Developer
- Full Stack Developer
- Software Engineer
- Data Analyst
- QA Engineer

### Interaction Matrix:
- **Case A (Technical + Java + Role=None):** Generates pure Java technical questions (e.g., JVM memory model, HashMap collisions).
- **Case B (Technical + Java + Role=Java Developer):** Generates Java questions with Java Developer role relevance (e.g., Spring Boot, concurrency).
- **Case C (Technical + No Subject + Role=Backend Developer):** Generates backend-oriented questions (e.g., API rate limiting, zero-downtime database migrations).
- **Case D (Technical + No Subject + Role=None):** Generates general core technical questions.
- **HR Mode + Role:** The questions remain HR-oriented (e.g., career goals, teamwork); Job Role never converts an HR interview into a coding test.

---

## 9. Question Count & Single-Question Practice
The system supports:
- **1 Question** (Instant Single-Question Practice)
- **3 Questions**
- **5 Questions**
- **7 Questions**

The selected count is strictly respected. Single-question practice allows candidates to immediately record one answer, receive full speech and video analysis, view AI evaluation, and complete the session.
Follow-up questions do **not** inflate the displayed main question count.

---

## 10. Dynamic Contextual Follow-Up Questions
- After a candidate submits an answer, the session manager checks if a follow-up question is warranted based on what the candidate actually said.
- **Contextual Trigger:** If the candidate mentions a specific project, makes a technical assertion, or gives an incomplete explanation, a relevant deeper question is generated.
- **Gating & Safety:** Limited to a maximum of 1 follow-up per main question to keep sessions focused. If Gemini fails or times out, the system continues safely without crashing or fabricating text.

---

## 11. Resume Analysis & Skill Gap Reporting
When a candidate uploads a PDF or DOCX resume:
1. **Information Extraction:**
   - Candidate Name (extracted dynamically, never hardcoded)
   - Categorized Technical Skills (Programming Languages, Frameworks, Databases & Tools)
   - Projects (Titles, technologies used, architectures)
   - Experience & Internships
   - Education & Degrees (e.g., *Jayshriram Engineering College*)
   - Certifications
2. **Resume Strengths:** Summarizes validated strong areas in the candidate's profile.
3. **Role-Aware Skill Gaps:** When a Job Role is selected, compares detected skills against role expectations.
   - **Important Phrasing:** The system explicitly states:
     `"Not detected in the uploaded resume."`
     (Never assumes the candidate does not know it).
4. **Recommended Improvements:** Practical suggestions to strengthen the resume.
5. **Grounded Question Generation:** Every resume-based question links to a specific `source_type` (`project`, `skill`, `experience`, `education`, `certification`) and `source_reference` (e.g., `CollegeFinder`).

---

## 12. Video & Facial Analysis (Zero False Positives)
The video analysis pipeline tracks gaze, presence, and stability frame-by-frame:
- **Face Visibility %:** Actual percentage of analyzed frames where a human face was detected.
- **Eye Contact Score (0–10):** Ratio of frames where gaze is directed toward the camera versus looking away.
- **Head Stability Score (0–10):** Measured via bounding box center jitter and scale variance.
- **Look-Away Events Timeline:**
  - For each confirmed event: **Event Number**, **Start Time**, **End Time**, **Duration**, and **Direction** (e.g., *Left*, *Right*, *Up*, *Down*, *Away*).
  - Uses temporal smoothing (minimum 1.0s duration, 0.6s gap tolerance) to prevent single-frame noise from triggering false events.
- **Zero False Positives:**
  - If no face is detected in the video (e.g., black frame, camera covered, no person), the system returns:
    - `look_away_count = 0`
    - `look_away_events = []`
    - `eye_contact_score = None`
    - `head_stability_score = None`
    - `insufficient_evidence = True`
    - Note: *"Insufficient visual evidence: No face detected in video. Ensure camera is facing candidate with adequate lighting."*
  - The system **never fabricates** 95% or look-away events without video evidence.

---

## 13. Speech-to-Text & Language Handling
- **Engine:** Faster-Whisper (`small` model, int8 CPU/CUDA).
- **Dynamic Context:** Automatically supplies the candidate's name and college name (*Jayshriram Engineering College*) to Whisper's initial prompt to improve proper noun recognition.
- **No Crude Dictionaries:** No blind string replacements. Transcripts reflect actual spoken words.
- **Language Support:** Handles English, Tamil, and Mixed/Tanglish naturally without forcing artificial translations.

---

## 14. Objective Communication Analysis
Analyzes spoken audio without accent discrimination:
- **Speech Duration (seconds)**
- **Word Count**
- **Words Per Minute (WPM)**: Pacing categorized as *Too Slow* (<100 WPM), *Ideal* (120–160 WPM), or *Rushed* (>175 WPM).
- **Filler Word Count & Rate**: Identifies common fillers (*um*, *uh*, *like*, *you know*, *basically*, *actually*).
- **Zero Accent Discrimination**: Evaluates only pacing, clarity, and structure. Accents and regional pronunciations are never penalized.

---

## 15. Authentication & Strict User Isolation
- **Password Security:** PBKDF2-HMAC-SHA256 with random salt (600,000 iterations).
- **Session Tokens:** Cryptographic JWT tokens with 7-day expiration.
- **Strict User Isolation:**
  - Every API endpoint (`/api/interview/session/{id}`, `/api/interview/details/{id}`, `/api/interview/pdf/{id}`, `/api/interview/history`, `/api/resume/latest`) verifies `session.user_id == current_user.id`.
  - User B cannot access User A's sessions, answers, history, resumes, or PDF reports (returns 404/403).

---

## 16. MySQL Database Schema
Persists all data in MySQL using SQLAlchemy ORM:
- **`users`**: Candidate accounts, hashed passwords, timestamps.
- **`resume_metadata`**: User ID, filename, parsed skills, projects, education, experience, certifications, strengths, skill gaps, recommendations.
- **`interview_sessions`**: User ID, mode, technical_subject, role (nullable), difficulty, total_questions, current_question_index, status, overall_score, readiness_score, readiness_level.
- **`session_questions`**: Session ID, question text, question type, technical_subject, source_type, source_reference, traceability.
- **`candidate_answers`**: Question ID, media paths, transcript, speech duration, WPM, filler word counts.
- **`session_evaluations`**: Scores (technical, communication, problem solving, confidence), feedback, ideal answer, missing points, video metrics JSON, communication metrics JSON.
- **`session_results`**: Completed session aggregate averages and readiness summaries.

---

## 17. Deterministic Interview Readiness Score
Formula:
$$\text{Readiness Score} = (0.35 \times \text{Technical}) + (0.25 \times \text{Communication}) + (0.20 \times \text{Problem Solving}) + (0.20 \times \text{Confidence})$$

Performance Bands:
- **Strong (85–100):** Interview ready for target engineering roles.
- **Good (70–84):** Solid foundation with minor refinement needed.
- **Developing (55–69):** Demonstrates basic skills; needs practice in depth and delivery.
- **Needs Improvement (<55):** Requires focused practice on core technical concepts and pacing.

---

## 18. Professional UI Design System
The frontend is built with a clean, modern aesthetic:
- **Color Palette:**
  - Background & Cards: White (`#FFFFFF`)
  - Primary Accent: Royal Violet (`#6C3AED`)
  - Accent Tint: Light Violet (`#EDE9FE`)
  - Text: Dark Charcoal (`#111827`)
  - Muted Text & Borders: Neutral Gray (`#6B7280`, `#E5E7EB`)
- **Step-Based Interview Wizard:**
  - Step 1: Interview Mode selection cards
  - Step 2: Technical Subject selection & Optional Job Role
  - Step 3: Question Count (1, 3, 5, 7)
  - Step 4: Resume upload / skip
  - Step 5: Setup Summary card before launching
- **Result Screen:**
  - Overall Readiness Score & Performance Overview
  - Communication Analysis cards (WPM, Fillers, Duration)
  - Video Analysis cards & **Look-Away Events Timeline**
  - Question-by-question breakdown with ideal answers
  - One-click PDF download & Practice Again

---

## 19. PDF Report Generation
Generates a structured multi-page PDF report containing:
- Candidate name and session ID
- Interview mode, technical subject, and job role
- Overall readiness score and performance category
- Question-by-question spoken transcript vs ideal answer
- Detailed communication metrics and video analysis summary
- Confirmed look-away events with timestamps and directions
- Strengths, areas for improvement, and recommendations

---

## 20. Installation & Setup

### Prerequisites
- Python 3.10+
- MySQL Server 8.0+ running locally on port 3306
- FFmpeg (for audio extraction)

### 1. Clone & Setup Environment
```bash
git clone <repo-url>
cd AI-Interview-Coach-main

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create or verify `.env`:
```env
DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3306/interview_coach_db?charset=utf8mb4
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=interview_coach_db
JWT_SECRET_KEY=super-secret-interview-coach-key-2026
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Initialize MySQL Database
```sql
CREATE DATABASE IF NOT EXISTS interview_coach_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
The application automatically creates and verifies all tables and schema migrations upon startup.

### 4. Run the Application
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to:
`http://127.0.0.1:8000`

---

## 21. Testing & Validation

### Automated Verification Suites
Run the exhaustive automated verification suites:
```bash
python test_final_corrections.py
python test_master_suite.py
```

### Test Coverage Verified:
1. **Config API:** Confirms modes, technical subjects, roles, and [1, 3, 5, 7] question counts.
2. **Registration & Dynamic Identity:** Rejects short passwords and duplicates; derives candidate name dynamically.
3. **Exact Question Counts:** Validates 1, 3, 5, and 7 question sessions.
4. **Technical Domain Matrix:**
   - Technical + Java + Role=None -> Pure Java questions.
   - Technical + Java + Role=Java Dev -> Java Developer questions.
   - Technical + DSA + Role=None -> Data structures & algorithms questions.
   - Technical + DBMS/SQL + Role=None -> Database & query questions.
   - Technical + No Subject + Role=Backend Dev -> Backend engineering questions.
   - Technical + No Subject + Role=None -> General technical questions.
5. **HR & Behavioral Modes:** Verifies HR questions remain HR-focused and behavioral questions test STAR scenarios.
6. **Resume Grounding & Skill Gaps:**
   - Extracts projects, skills, education (*Jayshriram Engineering College*).
   - Verifies phrasing: *"Not detected in the uploaded resume."*
   - Verifies questions reference actual resume items with `source_type` and `source_reference`.
7. **Single Question Practice:** Tests 1-question creation, answering, evaluation, and completion.
8. **Evidence-Based Video Analysis:**
   - Zero false positives test on blank video (0 look-aways, `insufficient_evidence: True`, scores `None`).
   - Real video test verifying start/end timestamps, duration, and direction.
9. **Strict User Isolation:** Confirms User B receives 404 when attempting to access User A's session or PDF.
10. **PDF Report:** Verifies valid `%PDF` signature and multi-question summary.
11. **MySQL Persistence:** Directly queries MySQL tables to verify data integrity.

---

## 22. Known Limitations & Edge Cases
- **Low-Light Video:** Extreme low-light conditions may degrade face detection; the system handles this gracefully by flagging `insufficient_evidence`.
- **CPU Transcription Latency:** On systems without CUDA, Faster-Whisper `small` model requires 3–6 seconds for audio transcription.
- **Audio Clashing:** Background conversations in candidate audio can occasionally affect transcription clarity.

---

## 23. Future Enhancements
- Integration of MediaPipe 3D face mesh for micro-expression analysis.
- Live audio waveform visualizer during recording.
- Real-time transcription streaming via WebSockets.
- Multi-session personalized improvement plans.
- Multi-language support for regional engineering mock interviews.

---
*Developed with FastAPI, Faster-Whisper, OpenCV, Google Gemini, and MySQL.*
