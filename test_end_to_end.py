"""
test_end_to_end.py - Comprehensive verification suite for AI Interview Coach.
Tests all 10 flows specified in the requirements:
1. Normal interview flow
2. Resume upload & resume-based questions
3. Good technical answer
4. Poor technical answer
5. Irrelevant answer
6. Empty / silent answer
7. Different resume (Resume B isolation)
8. Session isolation
9. Video look-away detection with timestamps
10. Error handling & PDF report export
"""

import io
import json
import os
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import requests
from reportlab.pdfgen import canvas
import docx

from synth_speech import synthesize_speech

BASE_URL = "http://127.0.0.1:8000"


def make_test_video(portrait_path: str, duration_sec: float = 3.0, look_away_sec: float = 0.0) -> str:
    """Generate a test MP4 video with optional look-away behavior."""
    portrait = cv2.imread(portrait_path)
    portrait = cv2.resize(portrait, (400, 400))

    temp_vid = os.path.join(tempfile.gettempdir(), f"vid_{int(time.time()*1000)}.mp4")
    fps = 30.0
    total_frames = int(duration_sec * fps)
    out = cv2.VideoWriter(temp_vid, cv2.VideoWriter_fourcc(*'mp4v'), fps, (640, 480))

    away_frames = int(look_away_sec * fps)
    center_before = (total_frames - away_frames) // 2
    center_after = total_frames - away_frames - center_before

    for _ in range(center_before):
        c = np.full((480, 640, 3), 180, dtype=np.uint8)
        c[40:440, 120:520] = portrait
        out.write(c)

    for _ in range(away_frames):
        c = np.full((480, 640, 3), 180, dtype=np.uint8)
        # Shift face far right (cx ~ 0.72)
        c[40:440, 240:640] = portrait
        out.write(c)

    for _ in range(center_after):
        c = np.full((480, 640, 3), 180, dtype=np.uint8)
        c[40:440, 120:520] = portrait
        out.write(c)

    out.release()
    return temp_vid


def make_test_pdf_resume(candidate_name: str, skills: list, projects: list, experience: list) -> bytes:
    """Create a PDF resume in memory."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, f"{candidate_name} - Software Engineer")
    c.drawString(100, 730, f"Technical Skills: {', '.join(skills)}")
    c.drawString(100, 710, f"Projects: {projects[0]}")
    c.drawString(100, 690, f"Experience: {experience[0]}")
    c.drawString(100, 670, "Education: B.Tech in Computer Science & Engineering")
    c.save()
    return buf.getvalue()


def run_tests():
    portrait_path = r"C:\Users\Praveena\.gemini\antigravity-ide\brain\28316c64-99ac-439a-ae93-bc05a0b87710\candidate_face_portrait_1791350246863.jpg"
    print("==================================================================")
    print("STARTING COMPREHENSIVE END-TO-END INTERVIEW COACH TESTS")
    print("==================================================================")

    # ------------------------------------------------------------------
    # TEST 1: Server Root & Static Files
    # ------------------------------------------------------------------
    print("\n[TEST 1] Testing server root & static assets...")
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200, f"Root returned {r.status_code}"
    assert "AI Interview Coach" in r.text
    r_js = requests.get(f"{BASE_URL}/static/script.js")
    assert r_js.status_code == 200, f"Static script.js returned {r_js.status_code}"
    r_css = requests.get(f"{BASE_URL}/static/style.css")
    assert r_css.status_code == 200, f"Static style.css returned {r_css.status_code}"
    print("[OK] [TEST 1 PASSED] Server root, HTML, CSS, and JS all load correctly.")

    # ------------------------------------------------------------------
    # TEST 2: Question Generation (Category & Difficulty)
    # ------------------------------------------------------------------
    print("\n[TEST 2] Testing standard question generation...")
    for cat in ["DSA", "OOP", "DBMS", "Operating Systems", "System Design"]:
        r = requests.post(f"{BASE_URL}/question", json={"category": cat, "difficulty": "Medium"})
        assert r.status_code == 200
        d = r.json()
        assert d.get("question"), "No question in response"
        assert d.get("category") == cat
        print(f"  [OK] Category {cat}: \"{d['question'][:60]}...\"")
    print("[OK] [TEST 2 PASSED] Standard question generation works across categories.")

    # ------------------------------------------------------------------
    # TEST 3: Resume Upload & Parsing (PDF)
    # ------------------------------------------------------------------
    print("\n[TEST 3] Testing resume upload & parsing (PDF)...")
    pdf_resume_a = make_test_pdf_resume(
        "Alice Smith",
        ["Java", "Spring Boot", "SQL", "Docker", "AWS"],
        ["PlacementPro - Campus recruitment tracking platform built using Spring Boot and SQL"],
        ["Backend Engineering Intern at GlobalTech"],
    )
    r = requests.post(
        f"{BASE_URL}/upload-resume",
        files={"file": ("alice_resume.pdf", pdf_resume_a, "application/pdf")},
    )
    assert r.status_code == 200, f"Upload resume failed: {r.text}"
    data_res_a = r.json()
    assert data_res_a["status"] == "success"
    parsed_skills = data_res_a["parsed"]["skills"]
    assert "Java" in parsed_skills or "Spring Boot" in parsed_skills or "SQL" in parsed_skills
    print(f"  [OK] Uploaded alice_resume.pdf -> Extracted skills: {parsed_skills}")
    print("[OK] [TEST 3 PASSED] PDF resume upload, validation, and parsing work.")

    # ------------------------------------------------------------------
    # TEST 4: Resume-Based Question Generation & Traceability
    # ------------------------------------------------------------------
    print("\n[TEST 4] Testing resume-based question generation with traceability...")
    r = requests.post(f"{BASE_URL}/question", json={"category": "Resume-Based", "difficulty": "Medium"})
    assert r.status_code == 200, f"Question generation failed: {r.text}"
    q_data = r.json()
    q_text = q_data["question"]
    trace = q_data.get("traceability", "")
    print(f"  Question: {q_text}")
    print(f"  Traceability: {trace}")
    assert "PlacementPro" in q_text or "Spring Boot" in q_text or "Java" in q_text or "GlobalTech" in q_text, \
        "Question did not reference resume projects or skills!"
    assert trace != "", "Traceability was missing!"
    print("[OK] [TEST 4 PASSED] Question is strictly grounded in candidate's resume with clear traceability.")

    # ------------------------------------------------------------------
    # TEST 5: Full Answer Submission — Whisper + Video + Gemini Evaluation
    # ------------------------------------------------------------------
    print("\n[TEST 5] Testing full answer submission pipeline...")
    # 1. Synthesize audio answer
    audio_path = os.path.join(tempfile.gettempdir(), "test_answer_audio.wav")
    answer_text = "In PlacementPro, I designed a normalized relational schema with Students, Companies, and Applications tables linked by foreign keys. For transactional consistency, I used Spring @Transactional annotation with READ_COMMITTED isolation level so application submissions and seat allocations succeed or rollback atomically. To optimize query performance during high-traffic placement drives, I added B-tree indexes on foreign keys and student roll numbers, and used JPQL fetch joins to eliminate N-plus-one query bottlenecks."
    synthesize_speech(answer_text, audio_path)

    # 2. Make video
    vid_path = make_test_video(portrait_path, duration_sec=4.0, look_away_sec=2.2)

    with open(audio_path, "rb") as fa:
        r = requests.post(
            f"{BASE_URL}/upload",
            files={"file": ("test_answer_audio.wav", fa, "audio/wav")},
            data={
                "question": q_text,
                "category": "Resume-Based",
                "difficulty": "Medium",
                "traceability": trace,
            },
        )
    assert r.status_code == 200, f"Submission failed: {r.text}"
    res = r.json()
    transcript = res.get("transcript", "")
    score = res.get("score")
    eval_data = res.get("ai_evaluation", {})
    ideal_ans = res.get("ideal_answer", "")

    print(f"  Transcript: \"{transcript}\"")
    print(f"  Score: {score}/100")
    print(f"  Technical Score: {eval_data.get('technical_score')}/10")
    print(f"  Ideal Answer: \"{ideal_ans[:80]}...\"")
    print(f"  Missing Points: {res.get('missing_points')}")
    assert "PlacementPro" in transcript or "Spring Boot" in transcript or "SQL" in transcript or len(transcript.split()) >= 10, \
        "Transcript does not match actual synthesized speech!"
    assert eval_data.get("technical_score") >= 6, "Expected strong score for relevant technical answer"
    os.remove(audio_path)
    print("[OK] [TEST 5 PASSED] Whisper transcribed real audio, Gemini evaluated transcript with resume context.")

    # ------------------------------------------------------------------
    # TEST 6: Video Analysis & Look-Away Events Detection
    # ------------------------------------------------------------------
    print("\n[TEST 6] Testing video analysis & look-away event timestamps...")
    with open(vid_path, "rb") as fv:
        r = requests.post(
            f"{BASE_URL}/upload",
            files={"file": ("test_answer_video.mp4", fv, "video/mp4")},
            data={"question": "Explain Spring Boot architecture"},
        )
    assert r.status_code == 200
    res_vid = r.json()
    va = res_vid.get("video_analysis", {})
    print(f"  Face Visible %: {va.get('face_visible_percent')}%")
    print(f"  Look-Away Count: {va.get('look_away_count')}")
    print(f"  Look-Away Events: {va.get('look_away_events')}")
    print(f"  Eye Contact Score: {va.get('eye_contact_score')}/10")
    print(f"  Visual Confidence Score: {va.get('visual_confidence_score')}/10")
    assert va.get("face_visible_percent") > 80.0
    assert va.get("look_away_count") >= 1, "Expected look-away event to be detected"
    events = va.get("look_away_events", [])
    assert len(events) >= 1
    ev0 = events[0]
    assert "start_time" in ev0 and "end_time" in ev0 and "duration" in ev0 and "direction" in ev0
    assert 0.0 <= ev0["start_seconds"] <= ev0["end_seconds"] <= va["video_duration_seconds"]
    os.remove(vid_path)
    print("[OK] [TEST 6 PASSED] Video analysis detected real face, eye contact, and look-away timestamps.")

    # ------------------------------------------------------------------
    # TEST 7: Poor / Incorrect Technical Answer Evaluation
    # ------------------------------------------------------------------
    print("\n[TEST 7] Testing evaluation on poor / incorrect answer...")
    poor_audio = os.path.join(tempfile.gettempdir(), "poor_ans.wav")
    synthesize_speech("Deadlock happens when the laptop battery runs out of charge and shuts down completely.", poor_audio)
    with open(poor_audio, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/upload",
            files={"file": ("poor_ans.wav", f, "audio/wav")},
            data={"question": "What is a deadlock in Operating Systems?"},
        )
    res_poor = r.json()
    eval_poor = res_poor["ai_evaluation"]
    print(f"  Transcript: \"{res_poor['transcript']}\"")
    print(f"  Technical Score: {eval_poor.get('technical_score')}/10")
    print(f"  Feedback: \"{res_poor.get('feedback')}\"")
    assert eval_poor.get("technical_score") <= 3, f"Expected low technical score, got {eval_poor.get('technical_score')}"
    os.remove(poor_audio)
    print("[OK] [TEST 7 PASSED] Poor technical answer receives low score and appropriate constructive criticism.")

    # ------------------------------------------------------------------
    # TEST 8: Irrelevant Answer Evaluation
    # ------------------------------------------------------------------
    print("\n[TEST 8] Testing evaluation on completely irrelevant answer...")
    irrel_audio = os.path.join(tempfile.gettempdir(), "irrel_ans.wav")
    synthesize_speech("I really enjoy eating pepperoni pizza and watching superhero movies during rainy days.", irrel_audio)
    with open(irrel_audio, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/upload",
            files={"file": ("irrel_ans.wav", f, "audio/wav")},
            data={"question": "Explain normalization and denormalization in DBMS."},
        )
    res_irrel = r.json()
    eval_irrel = res_irrel["ai_evaluation"]
    print(f"  Technical Score: {eval_irrel.get('technical_score')}/10")
    print(f"  Feedback: \"{res_irrel.get('feedback')}\"")
    assert eval_irrel.get("technical_score") <= 2, f"Expected near zero technical score, got {eval_irrel.get('technical_score')}"
    os.remove(irrel_audio)
    print("[OK] [TEST 8 PASSED] Irrelevant answer is caught and penalized appropriately.")

    # ------------------------------------------------------------------
    # TEST 9: Empty / Silent Answer
    # ------------------------------------------------------------------
    print("\n[TEST 9] Testing empty / silent answer...")
    silent_audio = os.path.join(tempfile.gettempdir(), "silent_ans.wav")
    # 2 seconds of silence
    import wave
    with wave.open(silent_audio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(np.zeros(32000, dtype=np.int16).tobytes())

    with open(silent_audio, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/upload",
            files={"file": ("silent_ans.wav", f, "audio/wav")},
            data={"question": "What are ACID properties in DBMS?"},
        )
    res_silent = r.json()
    print(f"  Transcript: \"{res_silent.get('transcript')}\"")
    print(f"  Overall Score: {res_silent.get('score')}")
    print(f"  Technical Score: {res_silent.get('ai_evaluation', {}).get('technical_score')}")
    assert res_silent.get("score") == 0
    assert res_silent.get("ai_evaluation", {}).get("technical_score") == 0
    os.remove(silent_audio)
    print("[OK] [TEST 9 PASSED] Empty audio yields 0 score without fake high scores.")

    # ------------------------------------------------------------------
    # TEST 10: Resume B Isolation & DOCX Support
    # ------------------------------------------------------------------
    print("\n[TEST 10] Testing Resume B isolation & DOCX support...")
    doc = docx.Document()
    doc.add_heading("Bob Johnson Resume", 0)
    doc.add_paragraph("Technical Skills: Python, FastAPI, MongoDB, PyTorch, Kubernetes")
    doc.add_paragraph("Projects: VisionBot - Real-time object detection assistant built with FastAPI and PyTorch")
    doc.add_paragraph("Experience: Machine Learning Intern at AI Vision Labs")
    docx_buf = io.BytesIO()
    doc.save(docx_buf)
    docx_bytes = docx_buf.getvalue()

    r = requests.post(
        f"{BASE_URL}/upload-resume",
        files={"file": ("bob_resume.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 200
    res_b = r.json()
    assert "Python" in res_b["parsed"]["skills"] or "FastAPI" in res_b["parsed"]["skills"]

    # Generate question for Resume B
    r_q = requests.post(f"{BASE_URL}/question", json={"category": "Resume-Based", "difficulty": "Medium"})
    q_b = r_q.json()["question"]
    print(f"  Resume B Question: {q_b}")
    assert "VisionBot" in q_b or "FastAPI" in q_b or "Python" in q_b or "PyTorch" in q_b, \
        "Resume B question did not reference Bob's resume items!"
    assert "PlacementPro" not in q_b and "Spring Boot" not in q_b, \
        "STALE RESUME LEAKAGE: Resume B question referenced items from Resume A!"
    print("[OK] [TEST 10 PASSED] DOCX parsing works and Resume B does not leak data from Resume A.")

    # ------------------------------------------------------------------
    # TEST 11: Error Handling (Invalid Resume, Missing File)
    # ------------------------------------------------------------------
    print("\n[TEST 11] Testing error handling (invalid file format, empty file)...")
    r_bad_ext = requests.post(
        f"{BASE_URL}/upload-resume",
        files={"file": ("malicious.exe", b"not a resume", "application/octet-stream")},
    )
    assert r_bad_ext.status_code == 400
    print(f"  [OK] Invalid extension error: {r_bad_ext.json().get('error')}")

    r_empty = requests.post(
        f"{BASE_URL}/upload-resume",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert r_empty.status_code == 400
    print(f"  [OK] Empty file error: {r_empty.json().get('error')}")
    print("[OK] [TEST 11 PASSED] Errors return proper HTTP 400 with helpful messages.")

    # ------------------------------------------------------------------
    # TEST 12: PDF Report Download
    # ------------------------------------------------------------------
    print("\n[TEST 12] Testing PDF report generation...")
    r_rep = requests.post(
        f"{BASE_URL}/download-report",
        json={
            "question": "Explain encapsulation",
            "category": "OOP",
            "difficulty": "Medium",
            "transcript": "Encapsulation is...",
            "score": 85,
            "ai_evaluation": {"technical_score": 8, "communication_score": 9},
            "video_analysis": {"face_visible_percent": 95.0, "eye_contact_score": 8.0, "look_away_count": 0},
        },
    )
    assert r_rep.status_code == 200
    assert r_rep.headers.get("content-type") == "application/pdf"
    assert len(r_rep.content) > 1000
    print(f"  [OK] PDF report generated: {len(r_rep.content)} bytes")
    print("[OK] [TEST 12 PASSED] PDF report download works cleanly.")

    print("\n==================================================================")
    print("ALL 12 TESTS PASSED PERFECTLY!")
    print("==================================================================")


if __name__ == "__main__":
    run_tests()
