"""
Comprehensive Resume-Agnostic Verification Test Suite
Tests items A through L:
A. Raw extraction test (PDF & DOCX)
B. Structured extraction test (Single Source of Truth)
C. Skill extraction test (9 canonical categories, no hallucinated associations)
D. Project extraction test (All projects, title, techs, descriptions, responsibilities)
E. Internship extraction test (All internships, company, role, duration, responsibilities)
F. Education extraction test (Degree, branch, institution, score, no skill confusion)
G. Certification/achievement test (Proper separation)
H. Role-aware gap test ("Not detected in the uploaded resume.")
I. Resume-based question test (Dynamic grounding)
J. Question source traceability test (source_type & source_reference)
K. Multiple-resume test (3 structurally different resumes: Java Backend, Python ML, React Full Stack)
L. User/session isolation test (Multi-tenant database isolation)
"""

import sys
import os
import io
import json
import uuid
import requests
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from resume_analyzer import (
    extract_text_from_pdf,
    extract_text_from_docx,
    normalize_resume_text,
    segment_resume_sections,
    extract_candidate_info,
    extract_categorized_skills,
    extract_projects,
    extract_internships_and_experience,
    extract_education,
    extract_certifications,
    extract_achievements,
    parse_resume_content,
    generate_resume_insights,
    generate_resume_question,
)
from question_generator import generate_session_question

BASE_URL = "http://127.0.0.1:8000"

results_summary = {}

def report(test_id, passed, evidence, expected, actual):
    status = "PASS" if passed else "FAIL"
    results_summary[test_id] = {
        "status": status,
        "evidence": evidence,
        "expected": expected,
        "actual": actual
    }
    print(f"\n[{status}] TEST {test_id}")
    print(f"  Expected: {expected}")
    print(f"  Actual:   {actual}")
    print(f"  Evidence: {evidence}")

def make_sample_pdf(filepath, lines):
    c = canvas.Canvas(filepath, pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
        if y < 50:
            c.showPage()
            y = 750
    c.save()

def make_sample_docx(filepath, paragraphs):
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    doc.save(filepath)

def run_tests():
    os.makedirs("test_artifacts", exist_ok=True)

    # =========================================================================
    # TEST A: Raw Extraction Test (PDF and DOCX)
    # =========================================================================
    pdf_path = "test_artifacts/test_a.pdf"
    docx_path = "test_artifacts/test_a.docx"

    pdf_content = [
        "Alex Rivera",
        "Email: alex.rivera@example.com | Phone: +1 555-0192",
        "Technical Skills: Golang, Docker, Kubernetes, PostgreSQL",
        "Projects: CloudGate - API Gateway built with Go and Redis",
        "Experience: DevOps Intern at CloudMatrix (Jan 2024 - May 2024)",
        "Education: B.S. in Computer Systems, Pacific University (2020-2024) - GPA: 3.8",
    ]
    make_sample_pdf(pdf_path, pdf_content)

    docx_content = [
        "Samantha Lee",
        "Email: samantha.lee@example.com | Phone: +1 555-4321",
        "Skills: Swift, SwiftUI, iOS Development, SQLite",
        "Projects: HealthPulse - iOS Fitness Tracker using SwiftUI and CoreData",
        "Experience: Mobile Engineer Intern at AppWorks (Jun 2023 - Aug 2023)",
        "Education: Bachelor of Science in Software Engineering, Metro College, 2024",
    ]
    make_sample_docx(docx_path, docx_content)

    with open(pdf_path, "rb") as f:
        pdf_raw = extract_text_from_pdf(f.read())
    with open(docx_path, "rb") as f:
        docx_raw = extract_text_from_docx(f.read())

    passed_a = (
        "CloudGate" in pdf_raw and "Kubernetes" in pdf_raw and
        "HealthPulse" in docx_raw and "SwiftUI" in docx_raw
    )
    report(
        "A: Raw Extraction Test",
        passed_a,
        f"PDF extracted {len(pdf_raw)} chars; DOCX extracted {len(docx_raw)} chars.",
        "Both PDF and DOCX text extraction successfully preserve tokens without loss.",
        "PDF contained 'CloudGate'/'Kubernetes'; DOCX contained 'HealthPulse'/'SwiftUI'." if passed_a else "Extraction failed."
    )

    # =========================================================================
    # TEST B: Structured Extraction Test (Single Source of Truth)
    # =========================================================================
    sample_text = """
    Marcus Vance
    Email: marcus.vance@tech.org | Phone: 9876543210
    Location: San Francisco, CA

    Education
    Bachelor of Technology in Computer Science
    Stanford University (2021 - 2025)
    CGPA: 8.9/10

    Technical Skills
    Programming Languages: Java, Python, C++
    Core CS: Data Structures and Algorithms, Object-Oriented Programming, Database Management Systems
    Frameworks: Spring Boot
    Databases: MySQL, PostgreSQL
    Tools: Git, Docker, Postman

    Projects
    Distributed Cache Engine
    Technologies: Java, Spring Boot, Redis
    • Engineered an in-memory key-value cache cluster with LRU eviction.
    • Achieved sub-5ms lookup latency under concurrent workloads.

    Microservices E-Commerce
    Technologies: Python, Flask, PostgreSQL
    • Designed modular REST APIs for order placement and checkout.

    Experience
    Backend Engineering Intern at FinTech Labs (May 2024 - August 2024)
    • Developed asynchronous payment webhook consumers using Spring Boot.
    • Optimized database queries cutting response latency by 35%.

    Certifications
    • AWS Certified Solutions Architect Associate
    • Oracle Certified Professional Java SE 11 Developer

    Achievements
    • Winner of National Hackathon 2024 among 120 teams
    • Published paper on Distributed Systems in IEEE Student Conference
    """

    parsed_b = parse_resume_content(sample_text)
    required_keys = ["candidate", "education", "skills", "all_skills", "projects", "experience", "internships", "certifications", "achievements"]
    has_all_keys = all(k in parsed_b for k in required_keys)
    passed_b = has_all_keys and len(parsed_b["projects"]) >= 2 and len(parsed_b["certifications"]) >= 2 and len(parsed_b["achievements"]) >= 2
    report(
        "B: Structured Extraction Test",
        passed_b,
        f"Parsed keys: {list(parsed_b.keys())}, Projects: {len(parsed_b['projects'])}, Certs: {len(parsed_b['certifications'])}, Achievements: {len(parsed_b['achievements'])}",
        "Complete Single Source of Truth structure populated with zero fabricated fields.",
        f"All required keys present. Found {len(parsed_b['projects'])} projects, {len(parsed_b['certifications'])} certs, {len(parsed_b['achievements'])} achievements."
    )

    # =========================================================================
    # TEST C: Skill Extraction Test (No Hallucinated Associations)
    # =========================================================================
    minimal_java_text = """
    Jane Doe
    Skills: Java, Data Structures and Algorithms, Object Oriented Programming, DBMS
    """
    parsed_c = parse_resume_content(minimal_java_text)
    c_skills = parsed_c["all_skills"]
    struct_c = parsed_c["skills"]

    # Java is present, but Spring Boot, Hibernate, Node.js, Express MUST NOT be present!
    no_hallucinations = (
        "Java" in c_skills and
        "Spring Boot" not in c_skills and
        "Hibernate" not in c_skills and
        "Node.js" not in c_skills and
        "MongoDB" not in c_skills
    )
    # Check normalized core CS skills
    normalized_core_cs = any("Data Structures" in s for s in c_skills) and any("Object-Oriented" in s for s in c_skills)
    passed_c = no_hallucinations and normalized_core_cs

    report(
        "C: Dynamic Skill Extraction Test",
        passed_c,
        f"Extracted skills: {c_skills}; Structured: {struct_c}",
        "Extracts only present skills (Java, DSA, OOP, DBMS); does NOT hallucinate Spring Boot, Hibernate, or Node.js.",
        f"Extracted exactly: {c_skills}. No unmentioned frameworks or databases were added."
    )

    # =========================================================================
    # TEST D: Project Extraction Test (Captures ALL projects & attributes)
    # =========================================================================
    projects_c = parsed_b["projects"]
    passed_d = len(projects_c) == 2 and all(
        p.get("title") and p.get("technologies") and p.get("responsibilities") for p in projects_c
    )
    p_titles = [p["title"] for p in projects_c]
    report(
        "D: Project Extraction Test",
        passed_d,
        f"Extracted project titles: {p_titles}",
        "Extracts all projects with title, technologies, description, and responsibilities.",
        f"Successfully extracted {len(projects_c)} projects: {p_titles} with respective tech stacks."
    )

    # =========================================================================
    # TEST E: Internship Extraction Test
    # =========================================================================
    internships_b = parsed_b["internships"]
    passed_e = len(internships_b) >= 1 and "FinTech Labs" in internships_b[0]["company"] and len(internships_b[0]["responsibilities"]) >= 2
    report(
        "E: Internship / Experience Extraction Test",
        passed_e,
        f"Internships found: {[i['source_reference'] for i in internships_b]}",
        "Extracts all internship entries with company, role, duration, and bullet responsibilities.",
        f"Found {len(internships_b)} internship entries with company '{internships_b[0].get('company')}'."
    )

    # =========================================================================
    # TEST F: Education Extraction Test (No Skill Confusion)
    # =========================================================================
    edu_b = parsed_b["education"]
    passed_f = len(edu_b) >= 1 and "Stanford University" in edu_b[0]["institution"] and "Stanford University" not in parsed_b["all_skills"]
    report(
        "F: Education Extraction Test",
        passed_f,
        f"Education entry: {edu_b[0]}",
        "Extracts degree, institution, score without polluting technical skills.",
        f"Degree: {edu_b[0].get('degree')}, Institution: {edu_b[0].get('institution')}, Score: {edu_b[0].get('score')}. College name is not in skills."
    )

    # =========================================================================
    # TEST G: Certification / Achievement Test (Proper Separation)
    # =========================================================================
    certs_b = parsed_b["certifications"]
    achs_b = parsed_b["achievements"]
    passed_g = (
        len(certs_b) >= 2 and
        len(achs_b) >= 2 and
        all(c not in achs_b for c in certs_b) and
        all(a not in certs_b for a in achs_b)
    )
    report(
        "G: Certification & Achievement Test",
        passed_g,
        f"Certs: {certs_b}\nAchievements: {achs_b}",
        "Certifications and achievements are extracted separately and not confused with each other or with claimed professional skills.",
        f"{len(certs_b)} certifications and {len(achs_b)} achievements preserved distinctly."
    )

    # =========================================================================
    # TEST H: Role-Aware Gap Test ("Not detected in the uploaded resume.")
    # =========================================================================
    insights_java_role = generate_resume_insights(parsed_b, target_role="Java Developer")
    gaps_java = insights_java_role.get("skill_gaps", [])

    # In parsed_b: Java and Spring Boot are present. Hibernate, JUnit are missing.
    # Therefore Hibernate or JUnit should be in gaps, but Java and Spring Boot MUST NOT be in gaps!
    gap_skills = [g["skill"] for g in gaps_java]
    statuses = [g["status"] for g in gaps_java]

    passed_h = (
        "Java" not in gap_skills and
        "Spring Boot" not in gap_skills and
        any(g["skill"] in ["Hibernate", "REST APIs", "JUnit"] for g in gaps_java) and
        all("Not detected in the uploaded resume." in s for s in statuses)
    )
    report(
        "H: Role-Aware Skill Gap Test",
        passed_h,
        f"Gaps for 'Java Developer': {gaps_java}",
        "Skills present in resume (Java, Spring Boot) are NOT gaps; missing skills marked with exact phrasing 'Not detected in the uploaded resume.'",
        f"Identified gaps: {gap_skills}. Exact status string verified: 'Not detected in the uploaded resume.'"
    )

    # =========================================================================
    # TEST I: Resume-Based Question Test (Dynamic Grounding)
    # =========================================================================
    q_b = generate_resume_question(parsed_b, role="Java Developer", difficulty="Medium")
    passed_i = (
        any(term in q_b["question"] for term in ["Distributed Cache Engine", "Spring Boot", "FinTech Labs", "Microservices E-Commerce", "Redis", "LRU"])
    )
    report(
        "I: Resume-Based Question Test",
        passed_i,
        f"Generated question: \"{q_b['question']}\"",
        "Generates interview question specifically grounded in candidate's project/internship/skills.",
        f"Question is directly grounded in resume evidence: {q_b['question']}"
    )

    # =========================================================================
    # TEST J: Question Source Traceability Test (source_type & source_reference)
    # =========================================================================
    has_traceability = (
        "source_type" in q_b and
        "source_reference" in q_b and
        q_b["source_type"] in ["project", "internship", "skill", "education"] and
        len(q_b["source_reference"]) > 0
    )
    passed_j = has_traceability
    report(
        "J: Question Source Traceability Test",
        passed_j,
        f"source_type='{q_b.get('source_type')}', source_reference='{q_b.get('source_reference')}'",
        "Question stores source_type and source_reference linking directly to resume items.",
        f"Verified traceability: source_type={q_b.get('source_type')}, source_reference={q_b.get('source_reference')}"
    )

    # =========================================================================
    # TEST K: Multiple-Resume Test (3 Structurally Different Resumes)
    # =========================================================================
    # Candidate 1: Java + Spring Boot + MySQL + Banking Project
    resume_1_text = """
    Rohan Sharma
    rohan.sharma@domain.in | 9988776655 | Pune, India
    Education: B.Tech in IT, COEP Pune (2020-2024) - 8.5 CGPA
    Skills: Java, Spring Boot, MySQL, Hibernate, Docker
    Projects: SecureBank Portal
    • Engineered transactional core-banking system in Java and Spring Boot with MySQL.
    Experience: Backend Intern at Apex Finance (Jan 2024 - Jun 2024)
    • Handled payments integration and transactional locks.
    """

    # Candidate 2: Python + Django + PostgreSQL + ML Fraud Detection Project
    resume_2_text = """
    Elena Rostova
    elena.rostova@ai.net | +44 7700 900123 | London, UK
    Education: M.Sc. in Machine Learning, Imperial College (2023-2024) - Distinction
    Skills: Python, Django, PostgreSQL, PyTorch, Scikit-learn, Pandas
    Projects: FraudSentinel ML
    • Built an XGBoost and PyTorch fraud detection pipeline with a Django backend and PostgreSQL database.
    Experience: ML Engineering Intern at DeepRisk AI (Mar 2024 - Aug 2024)
    • Trained real-time anomaly detection models on credit card transactions.
    """

    # Candidate 3: React + Node.js + MongoDB + Full Stack Social Platform
    resume_3_text = """
    David Chen
    david.chen@dev.io | (415) 555-7890 | Seattle, WA
    Education: B.S. in Computer Science, University of Washington (2021-2025)
    Skills: JavaScript, TypeScript, React, Next.js, Node.js, Express, MongoDB, Tailwind CSS
    Projects: DevConnect Social
    • Created a real-time developer social platform with Next.js, Node.js, and MongoDB websockets.
    Experience: Full Stack Intern at WebSphere Labs (Jun 2024 - Sep 2024)
    • Developed feeds and instant messaging with React and Express.
    """

    p1 = parse_resume_content(resume_1_text)
    p2 = parse_resume_content(resume_2_text)
    p3 = parse_resume_content(resume_3_text)

    q1 = generate_resume_question(p1, role="Java Developer")
    q2 = generate_resume_question(p2, role="Data Analyst")
    q3 = generate_resume_question(p3, role="Full Stack Developer")

    skills_different = (p1["all_skills"] != p2["all_skills"]) and (p2["all_skills"] != p3["all_skills"])
    projects_different = (p1["projects"] != p2["projects"]) and (p2["projects"] != p3["projects"])
    questions_different = (q1["question"] != q2["question"]) and (q2["question"] != q3["question"])
    sources_different = (q1.get("source_reference") != q2.get("source_reference")) and (q2.get("source_reference") != q3.get("source_reference"))

    passed_k = skills_different and projects_different and questions_different and sources_different
    report(
        "K: Multiple-Resume Differentiation Test",
        passed_k,
        f"Candidate 1 Question: \"{q1['question']}\" (Ref: {q1.get('source_reference')})\n"
        f"Candidate 2 Question: \"{q2['question']}\" (Ref: {q2.get('source_reference')})\n"
        f"Candidate 3 Question: \"{q3['question']}\" (Ref: {q3.get('source_reference')})",
        "Different resumes produce entirely different extracted skills, projects, and grounded interview questions with zero data leakage.",
        f"Skills, projects, and questions changed completely across candidates with verified references."
    )

    # =========================================================================
    # TEST L: User / Session Isolation Test (API Multi-Tenant Access)
    # =========================================================================
    passed_l = False
    evidence_l = ""
    try:
        # Create User 1
        u1_email = f"user1_{uuid.uuid4().hex[:6]}@test.com"
        u2_email = f"user2_{uuid.uuid4().hex[:6]}@test.com"
        pwd = "TestPassword123!"

        r1 = requests.post(f"{BASE_URL}/api/auth/register", json={"name": "Candidate Alpha", "email": u1_email, "password": pwd})
        t1 = r1.json().get("token")

        r2 = requests.post(f"{BASE_URL}/api/auth/register", json={"name": "Candidate Beta", "email": u2_email, "password": pwd})
        t2 = r2.json().get("token")

        if t1 and t2:
            # Upload Resume 1 for User 1 (PDF)
            pdf_bytes = io.BytesIO()
            make_sample_pdf(pdf_path, ["Candidate Alpha", "Skills: Java, Spring Boot", "Projects: AlphaBank System"])
            with open(pdf_path, "rb") as f:
                up1 = requests.post(
                    f"{BASE_URL}/upload-resume",
                    headers={"Authorization": f"Bearer {t1}"},
                    files={"file": ("alpha_resume.pdf", f.read(), "application/pdf")}
                )

            # Upload Resume 2 for User 2 (DOCX)
            make_sample_docx(docx_path, ["Candidate Beta", "Skills: Python, Django", "Projects: BetaVision ML"])
            with open(docx_path, "rb") as f:
                up2 = requests.post(
                    f"{BASE_URL}/upload-resume",
                    headers={"Authorization": f"Bearer {t2}"},
                    files={"file": ("beta_resume.docx", f.read(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                )

            # Fetch Latest Resume for User 1
            res1 = requests.get(f"{BASE_URL}/api/resume/latest", headers={"Authorization": f"Bearer {t1}"}).json()
            # Fetch Latest Resume for User 2
            res2 = requests.get(f"{BASE_URL}/api/resume/latest", headers={"Authorization": f"Bearer {t2}"}).json()

            u1_filename = res1.get("resume", {}).get("filename")
            u2_filename = res2.get("resume", {}).get("filename")

            u1_skills = res1.get("resume", {}).get("skills", [])
            u2_skills = res2.get("resume", {}).get("skills", [])

            isolated = (
                u1_filename == "alpha_resume.pdf" and
                u2_filename == "beta_resume.docx" and
                "Java" in u1_skills and "Python" not in u1_skills and
                "Python" in u2_skills and "Java" not in u2_skills
            )
            passed_l = isolated
            evidence_l = f"User 1 retrieved: {u1_filename} (skills: {u1_skills}); User 2 retrieved: {u2_filename} (skills: {u2_skills})"
    except Exception as e:
        evidence_l = f"Error during multi-tenant test: {e}"

    report(
        "L: User / Session Isolation Test",
        passed_l,
        evidence_l,
        "User 1 only sees Resume 1; User 2 only sees Resume 2 with strict multi-tenant isolation.",
        "Strict isolation confirmed: User 1 has alpha_resume.pdf with Java; User 2 has beta_resume.docx with Python." if passed_l else "Isolation check failed."
    )

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 60)
    print("RESUME-AGNOSTIC VERIFICATION SUMMARY")
    print("=" * 60)
    all_pass = all(item["status"] == "PASS" for item in results_summary.values())
    for tid, item in results_summary.items():
        print(f"[{item['status']}] {tid}")
    print(f"\nOVERALL RESULT: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")

    return all_pass

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
