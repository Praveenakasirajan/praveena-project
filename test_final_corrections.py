"""
test_final_corrections.py - Comprehensive verification script for FINAL CORRECTION requirements.
"""

import os
import time
import requests
import numpy as np
import cv2
import wave
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
BASE_URL = "http://127.0.0.1:8000"

def test_final_corrections():
    print("=" * 75)
    print("STARTING FINAL CORRECTIONS VERIFICATION SUITE")
    print("=" * 75)

    session_req = requests.Session()

    # 1. Config endpoint verification
    print("\n--- 1. Testing Config Endpoint (/api/interview/config) ---")
    r_cfg = session_req.get(f"{BASE_URL}/api/interview/config")
    assert r_cfg.status_code == 200, f"Config failed: {r_cfg.status_code}"
    cfg = r_cfg.json()
    print(f"Modes: {cfg['modes']}")
    print(f"Technical Subjects: {cfg['technical_subjects']}")
    print(f"Roles: {cfg['roles']}")
    print(f"Question Counts: {cfg['question_counts']}")
    
    assert set(["Technical", "HR", "Behavioral", "Resume-Based", "Mixed"]).issubset(set(cfg["modes"]))
    assert "Java" in cfg["technical_subjects"] and "DSA" in cfg["technical_subjects"] and "DBMS / SQL" in cfg["technical_subjects"]
    assert cfg["question_counts"] == [1, 3, 5, 7]
    assert "Java Developer" in cfg["roles"]
    print(">>> 1. Config Verification PASSED.")

    # 2. Registration & Dynamic Candidate Names (No hardcoded Praveena)
    print("\n--- 2. User Registration & Dynamic Name Grounding ---")
    ts = int(time.time())
    email_a = f"alice_eval_{ts}@finalpass.com"
    email_b = f"bob_eval_{ts}@finalpass.com"

    r_reg_a = session_req.post(f"{BASE_URL}/api/auth/register", json={
        "name": "Alice Candidate",
        "email": email_a,
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    assert r_reg_a.status_code == 200, f"Alice registration failed: {r_reg_a.text}"
    token_a = r_reg_a.json()["token"]
    user_a = r_reg_a.json()["user"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    assert user_a["name"] == "Alice Candidate"

    r_reg_b = session_req.post(f"{BASE_URL}/api/auth/register", json={
        "name": "Bob Reviewer",
        "email": email_b,
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    assert r_reg_b.status_code == 200
    token_b = r_reg_b.json()["token"]
    user_b = r_reg_b.json()["user"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    print(f"Registered User A: '{user_a['name']}' ({user_a['email']})")
    print(f"Registered User B: '{user_b['name']}' ({user_b['email']})")
    print(">>> 2. Registration & User Identity PASSED.")

    # 3. Question Count Verification (1, 3, 5, 7)
    print("\n--- 3. Testing Exact Question Counts (1, 3, 5, 7) ---")
    for count in [1, 3, 5, 7]:
        r_sess = session_req.post(f"{BASE_URL}/api/interview/start", json={
            "mode": "Technical",
            "technical_subject": "Java",
            "role": None,  # Job role optional!
            "total_questions": count,
            "difficulty": "Medium"
        }, headers=headers_a)
        assert r_sess.status_code == 200, f"Failed starting session with {count} questions: {r_sess.text}"
        sess_data = r_sess.json()["session"]
        assert sess_data["total_questions"] == count, f"Expected {count}, got {sess_data['total_questions']}"
        print(f"  Verified session creation with exact count = {count} (Session #{sess_data['session_id']})")
    print(">>> 3. Exact Question Count PASSED.")

    # 4. Technical Domain & Optional Job Role Matrix
    print("\n--- 4. Testing Technical Domain & Optional Job Role Matrix ---")
    
    # Case A: Technical + Java + Role = None -> pure Java questions
    r_case_a = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "Technical",
        "technical_subject": "Java",
        "role": None,
        "total_questions": 3,
        "difficulty": "Medium"
    }, headers=headers_a)
    assert r_case_a.status_code == 200
    q_a = r_case_a.json()["session"]["question"]["text"]
    print(f"  Case A (Technical + Java + Role=None): {q_a}")
    assert any(term in q_a.lower() for term in ["java", "jvm", "hashmap", "string", "thread", "garbage", "interface", "class", "oop", "memory", "exception", "collection"]), f"Question '{q_a}' is not Java specific!"

    # Case B: Technical + Java + Role = 'Java Developer'
    r_case_b = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "Technical",
        "technical_subject": "Java",
        "role": "Java Developer",
        "total_questions": 3,
        "difficulty": "Medium"
    }, headers=headers_a)
    assert r_case_b.status_code == 200
    q_b = r_case_b.json()["session"]["question"]["text"]
    print(f"  Case B (Technical + Java + Role=Java Dev): {q_b}")
    assert any(term in q_b.lower() for term in ["java", "jvm", "spring", "hashmap", "thread", "garbage", "memory", "interface", "collection"]), f"Question '{q_b}' is not Java specific!"

    # Case C: Technical + DSA + Role = None
    r_case_c = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "Technical",
        "technical_subject": "DSA",
        "role": None,
        "total_questions": 3,
        "difficulty": "Medium"
    }, headers=headers_a)
    assert r_case_c.status_code == 200
    q_c = r_case_c.json()["session"]["question"]["text"]
    print(f"  Case C (Technical + DSA + Role=None): {q_c}")
    assert any(term in q_c.lower() for term in ["tree", "graph", "binary", "sort", "search", "array", "complexity", "stack", "queue", "dynamic programming", "hash", "dsa", "algorithm"]), f"Question '{q_c}' is not DSA specific!"

    # Case D: Technical + DBMS / SQL + Role = None
    r_case_d = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "Technical",
        "technical_subject": "DBMS / SQL",
        "role": None,
        "total_questions": 3,
        "difficulty": "Medium"
    }, headers=headers_a)
    assert r_case_d.status_code == 200
    q_d = r_case_d.json()["session"]["question"]["text"]
    print(f"  Case D (Technical + DBMS / SQL + Role=None): {q_d}")
    assert any(term in q_d.lower() for term in ["index", "acid", "sql", "normalization", "transaction", "database", "query", "join", "schema", "table", "lock"]), f"Question '{q_d}' is not DBMS/SQL specific!"

    # Case E: Technical + No subject + Role = Backend Developer
    r_case_e = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "Technical",
        "technical_subject": None,
        "role": "Backend Developer",
        "total_questions": 3,
        "difficulty": "Medium"
    }, headers=headers_a)
    assert r_case_e.status_code == 200
    q_e = r_case_e.json()["session"]["question"]["text"]
    print(f"  Case E (Technical + No Subject + Role=Backend Dev): {q_e}")

    # Case F: Technical + No subject + Role = None -> General technical
    r_case_f = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "Technical",
        "technical_subject": None,
        "role": None,
        "total_questions": 3,
        "difficulty": "Medium"
    }, headers=headers_a)
    assert r_case_f.status_code == 200
    q_f = r_case_f.json()["session"]["question"]["text"]
    print(f"  Case F (Technical + No Subject + Role=None): {q_f}")
    print(">>> 4. Technical Domain & Optional Role Matrix PASSED.")

    # 5. HR & Behavioral Modes (Role does not override HR)
    print("\n--- 5. HR & Behavioral Modes ---")
    # HR with Role = None
    r_hr1 = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "HR", "role": None, "total_questions": 3, "difficulty": "Medium"
    }, headers=headers_a)
    assert r_hr1.status_code == 200
    q_hr1 = r_hr1.json()["session"]["question"]["text"]
    print(f"  HR (Role=None): {q_hr1}")

    # HR with Role = 'Java Developer' -> Still HR-oriented
    r_hr2 = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "HR", "role": "Java Developer", "total_questions": 3, "difficulty": "Medium"
    }, headers=headers_a)
    assert r_hr2.status_code == 200
    q_hr2 = r_hr2.json()["session"]["question"]["text"]
    print(f"  HR (Role=Java Developer): {q_hr2}")
    # Verify it does NOT ask code syntax
    assert not any(x in q_hr2.lower() for x in ["public static void main", "write a function", "syntax of", "hashmap implementation"]), "HR mode was turned into a technical coding test!"

    # Behavioral
    r_beh = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "Behavioral", "role": None, "total_questions": 3, "difficulty": "Medium"
    }, headers=headers_a)
    assert r_beh.status_code == 200
    q_beh = r_beh.json()["session"]["question"]["text"]
    print(f"  Behavioral (Role=None): {q_beh}")
    assert any(w in q_beh.lower() for w in ["tell me about a time", "describe a situation", "conflict", "deadline", "challenge", "team", "handle", "mistake", "disagreed", "project"]), "Behavioral question is not situation-based!"
    print(">>> 5. HR & Behavioral Verification PASSED.")

    # 6. Resume Analysis & Skill Gaps with Phrasing Requirement
    print("\n--- 6. Resume Analysis & Phrasing Verification ---")
    from resume_analyzer import parse_resume_content, generate_resume_insights, generate_resume_question
    
    sample_resume = (
        "Alice Candidate\n"
        "Education: Bachelor of Engineering in Computer Science, Jayshriram Engineering College (2020-2024)\n"
        "Skills: Java, Python, MySQL, Git, Docker, Spring Boot\n"
        "Projects: CollegeFinder - A university recommendation portal built with Java, Spring Boot, MySQL.\n"
        "Experience: Intern at Alpha Technologies working on REST APIs.\n"
        "Certifications: Oracle Certified Java Associate"
    )

    parsed = parse_resume_content(sample_resume)
    assert parsed["candidate_name"] == "Alice Candidate"
    assert "Java" in parsed["programming_languages"] or "Java" in [s.title() for s in parsed["programming_languages"]]
    assert any("CollegeFinder" in p for p in parsed["projects"])
    assert any("Jayshriram Engineering College" in edu for edu in parsed["education"])
    print(f"  Parsed Name: {parsed['candidate_name']}")
    print(f"  Parsed Education: {parsed['education']}")
    print(f"  Parsed Projects: {parsed['projects']}")
    print(f"  Parsed Skills: {parsed['skills']}")

    # Check skill gaps phrasing
    insights = generate_resume_insights(parsed, target_role="Java Developer")
    print(f"  Skill gaps generated: {insights['skill_gaps']}")
    for gap_item in insights["skill_gaps"]:
        gap_status = gap_item["status"] if isinstance(gap_item, dict) else str(gap_item)
        assert "Not detected in the uploaded resume" in gap_status, f"Gap phrasing violation! Expected 'Not detected in the uploaded resume', got: {gap_status}"
    print(f"  Strengths: {insights['resume_strengths']}")
    print(f"  Recommendations: {insights['recommended_improvements']}")

    # Grounded question generation with source_type and source_reference
    q_grounded = generate_resume_question(sample_resume, parsed, "Medium")
    assert q_grounded["source_type"] in ["project", "skill", "internship", "experience", "education", "certification"]
    assert q_grounded["source_reference"] is not None
    print(f"  Resume Question: '{q_grounded['question']}'")
    print(f"  Source Type: {q_grounded['source_type']} | Source Reference: {q_grounded['source_reference']}")
    print(">>> 6. Resume Analysis & Grounding PASSED.")

    # 7. Single Question Practice Flow (1 Question -> Submit -> Complete)
    print("\n--- 7. Single Question Practice Flow (1 Main Question) ---")
    r_single = session_req.post(f"{BASE_URL}/api/interview/start", json={
        "mode": "Technical",
        "technical_subject": "Java",
        "role": None,
        "total_questions": 1,
        "difficulty": "Medium"
    }, headers=headers_a)
    assert r_single.status_code == 200
    single_sess = r_single.json()["session"]
    single_sess_id = single_sess["session_id"]
    single_q = single_sess["question"]
    assert single_sess["total_questions"] == 1
    print(f"  Single session #{single_sess_id} started. Q: {single_q['text']}")

    # Create dummy audio for answering
    dummy_wav_path = os.path.join(os.environ.get("TEMP", "."), "ans_audio.wav")
    with wave.open(dummy_wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(np.zeros(32000, dtype=np.int16).tobytes()) # 2 seconds

    with open(dummy_wav_path, "rb") as f:
        r_ans = session_req.post(
            f"{BASE_URL}/api/interview/submit-answer",
            files={"file": ("ans_audio.wav", f, "audio/wav")},
            data={"session_id": single_sess_id, "question_id": single_q["id"]},
            headers=headers_a
        )
    assert r_ans.status_code == 200
    ans_data = r_ans.json()["data"]
    assert ans_data["is_completed"] == True, "Single question session should be completed after answering Q1!"
    print(f"  Single session answered: status={ans_data['status']}, completed={ans_data['is_completed']}")

    # Retrieve completed session details
    r_details = session_req.get(f"{BASE_URL}/api/interview/details/{single_sess_id}", headers=headers_a)
    assert r_details.status_code == 200
    details = r_details.json().get("session", {})
    assert details.get("status") == "completed"
    assert len(details.get("questions", [])) == 1
    print(f"  Session #{single_sess_id} verified completed in database.")
    print(">>> 7. Single Question Practice Flow PASSED.")

    # 8. Video Analysis — Zero False Positives & Evidence-Based Look-Aways
    print("\n--- 8. Video Analysis: Zero False Positives & Look-Away Timeline ---")
    from video_analyzer import analyze_interview_video

    # Test 8a: Black video with NO human face
    black_video_path = os.path.join(os.environ.get("TEMP", "."), "no_face_test.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(black_video_path, fourcc, 10.0, (320, 240))
    for _ in range(30): # 3 seconds of total blackness
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        out.write(frame)
    out.release()

    analysis_no_face = analyze_interview_video(black_video_path)
    print(f"  No-Face Video Result: face_visible={analysis_no_face['face_visible_percent']}%, look_away_count={analysis_no_face['look_away_count']}, insufficient={analysis_no_face.get('insufficient_evidence')}")
    assert analysis_no_face["face_visible_percent"] == 0.0, "Expected 0% face visibility for black video!"
    assert analysis_no_face["look_away_count"] == 0, "FALSE POSITIVE! Reported look-away events when NO face existed!"
    assert len(analysis_no_face["look_away_events"]) == 0
    assert analysis_no_face["insufficient_evidence"] == True
    assert analysis_no_face["eye_contact_score"] is None
    assert analysis_no_face["head_stability_score"] is None
    assert "Insufficient visual evidence" in analysis_no_face["note"]
    print("  -> Zero false positives verified: No fake look-away events when face is absent.")

    # Test 8b: Real recorded video analysis
    videos_dir = os.path.join("uploads", "videos")
    real_video_candidates = [
        os.path.join(videos_dir, "1791393094_recorded_answer.webm"),
        os.path.join(videos_dir, "1791393162_recorded_answer.webm"),
        os.path.join(videos_dir, "1791393206_recorded_answer.webm"),
        os.path.join(videos_dir, "recorded_answer.webm"),
    ]
    real_video_path = None
    for cand in real_video_candidates:
        if os.path.exists(cand):
            real_video_path = cand
            break

    if real_video_path:
        real_analysis = analyze_interview_video(real_video_path)
        print(f"  Real Video Result ({os.path.basename(real_video_path)}):")
        print(f"    Duration: {real_analysis['video_duration_seconds']}s")
        print(f"    Face Visible: {real_analysis['face_visible_percent']}%")
        print(f"    Look-Away Count: {real_analysis['look_away_count']}")
        print(f"    Eye Contact Score: {real_analysis['eye_contact_score']}/10")
        print(f"    Head Stability Score: {real_analysis['head_stability_score']}/10")
        print(f"    Visual Confidence: {real_analysis['visual_confidence_score']}/10")
        assert real_analysis["video_duration_seconds"] > 0
        assert 0.0 <= real_analysis["face_visible_percent"] <= 100.0
        for ev in real_analysis["look_away_events"]:
            print(f"      Event #{ev['event_num']}: {ev['start_time']} -> {ev['end_time']} ({ev['duration']}s, Direction: {ev['direction']})")
            assert "start_time" in ev and "end_time" in ev and "duration" in ev and "direction" in ev
    else:
        print("  Notice: No local recorded video found to analyze.")

    print(">>> 8. Video Analysis & Look-Away Timeline PASSED.")

    # 9. Strict User Isolation Verification
    print("\n--- 9. Strict User Isolation (User A vs User B) ---")
    # User B attempts to access User A's session details
    r_b_details = session_req.get(f"{BASE_URL}/api/interview/details/{single_sess_id}", headers=headers_b)
    assert r_b_details.status_code in [403, 404], f"User B accessed User A's session details! Status: {r_b_details.status_code}"

    # User B attempts to download User A's PDF
    r_b_pdf = session_req.get(f"{BASE_URL}/api/interview/pdf/{single_sess_id}", headers=headers_b)
    assert r_b_pdf.status_code in [403, 404], f"User B accessed User A's PDF! Status: {r_b_pdf.status_code}"

    # User B history check
    r_b_hist = session_req.get(f"{BASE_URL}/api/interview/history", headers=headers_b)
    assert r_b_hist.status_code == 200
    b_history = r_b_hist.json()["history"]
    assert not any(s["id"] == single_sess_id for s in b_history), "User A's session leaked into User B's history!"
    print(f"  User B blocked from User A session #{single_sess_id} (Status {r_b_details.status_code})")
    print(f"  User B blocked from User A PDF #{single_sess_id} (Status {r_b_pdf.status_code})")
    print(">>> 9. Strict User Isolation PASSED.")

    # 10. PDF Report Content Verification
    print("\n--- 10. PDF Report Generation & Header Verification ---")
    r_a_pdf = session_req.get(f"{BASE_URL}/api/interview/pdf/{single_sess_id}", headers=headers_a)
    assert r_a_pdf.status_code == 200, f"User A PDF failed: {r_a_pdf.status_code}"
    assert r_a_pdf.headers["content-type"] == "application/pdf"
    assert r_a_pdf.content.startswith(b"%PDF"), "PDF file does not start with valid %PDF header"
    print(f"  Session #{single_sess_id} PDF verified ({len(r_a_pdf.content)} bytes). Valid %PDF signature.")
    print(">>> 10. PDF Report Generation PASSED.")

    # 11. Direct MySQL Database Persistence Verification
    print("\n--- 11. Direct MySQL Database Persistence Verification ---")
    db_url = os.getenv("DATABASE_URL")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        users = conn.execute(text("SELECT id, name, email FROM users WHERE email = :email"), {"email": email_a}).fetchall()
        assert len(users) == 1, "User A not found in MySQL users table!"
        
        sessions = conn.execute(text("SELECT id, mode, technical_subject, role, total_questions, status FROM interview_sessions WHERE id = :id"), {"id": single_sess_id}).fetchall()
        assert len(sessions) == 1, "Session not found in MySQL interview_sessions table!"
        s_row = sessions[0]
        print(f"  MySQL Record: Session #{s_row[0]} | Mode={s_row[1]} | Subject={s_row[2]} | Role={s_row[3]} | TotalQ={s_row[4]} | Status={s_row[5]}")
        assert s_row[1] == "Technical"
        assert s_row[2] == "Java"
        assert s_row[3] is None  # Verified role is NULL when not selected
        assert s_row[4] == 1     # Verified exact count
        assert s_row[5] == "completed"
    print(">>> 11. MySQL Database Persistence PASSED.")

    print("\n" + "=" * 75)
    print("ALL FINAL CORRECTION TESTS EXECUTED AND PASSED WITH 100% SUCCESS!")
    print("=" * 75)

if __name__ == "__main__":
    test_final_corrections()
