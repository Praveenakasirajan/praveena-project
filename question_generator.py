"""
question_generator.py - Multi-mode, domain-specific, and role-aware interview question engine.
Supports:
1. Primary Interview Modes: Technical, HR, Behavioral, Resume-Based, Mixed
2. Technical Subjects / Domains: Java, Python, C, C++, DSA, DBMS / SQL, Operating Systems, Computer Networks, OOP, System Design, General
3. Optional Job Roles: Java Developer, Backend Developer, Full Stack Developer, Software Engineer, Data Analyst, QA Engineer, or None
4. Grounded Resume Questions: Questions tied directly to verified resume projects, skills, or experience
5. Dynamic Contextual Follow-Up Questions with intelligent fallback
"""

import os
import random
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize Google GenAI client if available
try:
    from google import genai
    from google.genai import types
    _genai_client = genai.Client()
except Exception as e:
    logger.warning("Google GenAI client unavailable in question_generator: %s", e)
    _genai_client = None


# ---------------------------------------------------------------------------
# SUPPORTED SELECTIONS
# ---------------------------------------------------------------------------

SUPPORTED_MODES = [
    "Technical",
    "HR",
    "Behavioral",
    "Resume-Based",
    "Mixed",
]

SUPPORTED_ROLES = [
    "None",
    "Java Developer",
    "Backend Developer",
    "Full Stack Developer",
    "Software Engineer",
    "Data Analyst",
    "QA Engineer",
]

SUPPORTED_TECHNICAL_SUBJECTS = [
    "Java",
    "Python",
    "C",
    "C++",
    "DSA",
    "DBMS / SQL",
    "Operating Systems",
    "Computer Networks",
    "OOP",
    "System Design",
    "General",
]


# ---------------------------------------------------------------------------
# DOMAIN-SPECIFIC TECHNICAL QUESTION BANKS (VERIFIED PRACTICE QUESTIONS)
# ---------------------------------------------------------------------------

_SUBJECT_QUESTIONS: Dict[str, List[str]] = {
    "Java": [
        "What is the difference between HashMap and Hashtable in Java, and how does Java 8 handle hash collisions using balanced trees?",
        "Explain the contract between hashCode() and equals() in Java, and what unexpected behavior occurs if it is violated?",
        "What are the differences between JVM Stack and Heap memory, and how does Garbage Collection (like G1 or ZGC) manage heap allocation?",
        "Explain the differences between synchronized blocks, ReentrantLock, and Atomic variables in multithreaded Java applications.",
        "How does the Java Stream API execute operations lazily, and what is the difference between intermediate and terminal operations?",
        "What is the difference between String, StringBuilder, and StringBuffer in Java regarding immutability and thread safety?",
        "Explain how Exception handling works in Java. What is the fundamental difference between checked and unchecked exceptions?",
        "How does the Java ClassLoader mechanism work, and what is the delegation hierarchy?"
    ],
    "Python": [
        "Explain the Global Interpreter Lock (GIL) in CPython and how it impacts CPU-bound multithreaded performance.",
        "What is the difference between deep copy and shallow copy in Python, and how are mutable default arguments handled?",
        "Explain Python generators, the iterator protocol, and the memory advantages of using `yield` compared to returning lists.",
        "How do Python decorators work under the hood, and how would you implement a decorator that accepts custom arguments?",
        "Explain the difference between `__init__` and `__new__` in Python object instantiation and metaprogramming.",
        "How does Python handle memory management and garbage collection (reference counting combined with cyclic generational GC)?",
        "Explain list comprehensions, dictionary comprehensions, and generator expressions, and when each is most appropriate.",
        "What is the difference between `is` and `==` in Python, and how does Python cache small integers and intern strings?"
    ],
    "C": [
        "Explain the difference between malloc(), calloc(), realloc(), and free() in dynamic memory management in C.",
        "What are pointers in C, and what is the difference between a pointer to a constant and a constant pointer?",
        "Explain what a segmentation fault is in C, and what common issues (like buffer overflows or dangling pointers) trigger it.",
        "What is the purpose of the `volatile` and `static` keywords in C, and how do they affect compilation and variable scope?",
        "Explain the standard memory layout of a compiled C program: Text segment, Data segment, BSS, Heap, and Stack.",
        "What is the difference between passing arguments by value versus passing by pointer in C functions?",
        "Explain structure padding, data alignment, and how memory packing affects the size of a `struct` in C."
    ],
    "C++": [
        "Explain the differences between `std::unique_ptr`, `std::shared_ptr`, and `std::weak_ptr` in modern C++ (RAII).",
        "How does the Virtual Method Table (vtable) and vptr implement runtime polymorphism in C++?",
        "What is the Rule of Three / Rule of Five in modern C++, and why are move constructors and move assignment operators necessary?",
        "Explain templates in C++ and how template specialization and concepts work at compile time.",
        "What is the difference between virtual inheritance and standard inheritance, and how does it resolve the Diamond Problem in C++?",
        "Explain move semantics and `std::move` using rvalue references (`&&`) to eliminate unnecessary deep copies.",
        "What is the difference between `std::vector` and `std::list` in terms of memory layout, cache locality, and iterator invalidation?"
    ],
    "DSA": [
        "How does a Hash Map achieve O(1) average time complexity, and how do chaining and open addressing resolve collisions?",
        "Explain how you would detect and find the starting node of a cycle in a singly linked list using Floyd's Tortoise and Hare algorithm.",
        "Compare QuickSort and MergeSort in terms of time complexity, auxiliary space, stability, and worst-case scenarios.",
        "How would you implement an LRU (Least Recently Used) Cache with O(1) get and put operations using a Doubly Linked List and Hash Map?",
        "Explain the difference between Breadth-First Search (BFS) and Depth-First Search (DFS) on graphs, and when you would prefer each.",
        "What is a Binary Search Tree (BST), and what causes it to degrade to O(N) worst-case time? How do AVL and Red-Black trees fix this?",
        "Explain how a Min-Heap or Max-Heap is represented in an array, and what the time complexity of the heapify operation is."
    ],
    "DBMS / SQL": [
        "Explain the ACID properties of database transactions and give an example of an isolation anomaly (Dirty Read, Non-Repeatable Read, Phantom Read).",
        "What is the difference between clustered and non-clustered indexes in SQL, and how do B+ Trees optimize range queries?",
        "Explain database normalization from 1NF to 3NF and BCNF, and explain why a high-throughput system might choose denormalization.",
        "Explain the difference between INNER JOIN, LEFT OUTER JOIN, and FULL OUTER JOIN with practical query examples.",
        "What are SQL Window functions (like ROW_NUMBER, RANK, DENSE_RANK), and how do they differ from GROUP BY aggregations?",
        "How would you diagnose and optimize a slow-running SQL query that joins multiple multi-million row tables?",
        "Explain the two-phase locking protocol (2PL) and how modern relational databases detect or prevent deadlocks."
    ],
    "Operating Systems": [
        "Explain the four necessary conditions for a deadlock to occur (Mutual Exclusion, Hold & Wait, No Preemption, Circular Wait) and how to prevent them.",
        "What is the difference between a process and a thread, and how does context switching differ between them?",
        "Explain virtual memory, paging, page faults, and how the operating system utilizes the Translation Lookaside Buffer (TLB).",
        "What causes thrashing in an operating system, and how does the working set model mitigate it?",
        "Explain inter-process communication (IPC) mechanisms: anonymous pipes, named pipes, shared memory, and message queues.",
        "How does CPU scheduling work, and what are the trade-offs between Round Robin, Priority Scheduling, and Multi-Level Feedback Queues?"
    ],
    "Computer Networks": [
        "Explain the steps involved in the TCP three-way handshake and four-way termination sequence.",
        "What happens step-by-step from the moment you enter a URL into a browser until the webpage renders (DNS, TCP, TLS, HTTP)?",
        "What are the key architectural differences between HTTP/1.1, HTTP/2 (multiplexing), and HTTP/3 (QUIC/UDP)?",
        "Explain how HTTPS secures communication using symmetric and asymmetric encryption during the TLS handshake.",
        "What is the difference between TCP and UDP, and in what applications is UDP preferred despite being connectionless?",
        "Explain subnetting, CIDR notation, and the difference between private IPv4 addresses and public IP addresses with NAT."
    ],
    "OOP": [
        "Explain the four core principles of Object-Oriented Programming (Encapsulation, Abstraction, Inheritance, Polymorphism) with real-world examples.",
        "Explain the difference between method overloading (compile-time) and method overriding (runtime polymorphism).",
        "What are the SOLID principles of object-oriented software design, and how has applying one of them improved your code architecture?",
        "Why is composition generally favored over class inheritance in modern object-oriented software design?",
        "Explain abstract classes versus interfaces, and when you would choose an abstract class over an interface in system design."
    ],
    "System Design": [
        "How would you design a scalable URL shortener service (like TinyURL) capable of handling 100 million daily active users?",
        "Explain the CAP theorem and the trade-offs between Consistency, Availability, and Partition Tolerance in distributed databases.",
        "How would you design a distributed caching layer using Redis to reduce database read load and prevent cache stampedes?",
        "Explain the role of load balancers, reverse proxies, and consistent hashing algorithms in distributed architectures.",
        "How would you design a scalable notification delivery system capable of dispatching email, SMS, and push alerts with guaranteed at-least-once delivery?"
    ],
    "General": [
        "Explain the time and space complexity tradeoffs between an Array, Linked List, and Hash Map for searching and insertions.",
        "What is database normalization, and why are 1NF, 2NF, and 3NF important in relational schema design?",
        "Explain how the operating system manages memory using paging and how page faults are resolved.",
        "What is the difference between synchronous and asynchronous execution, and how do non-blocking I/O models work?",
        "Explain how REST APIs adhere to statelessness, and what HTTP status codes you would return for different client errors."
    ]
}


# ---------------------------------------------------------------------------
# ROLE-SPECIFIC TECHNICAL QUESTION REPOSITORIES
# ---------------------------------------------------------------------------

_ROLE_TECHNICAL_QUESTIONS: Dict[str, List[str]] = {
    "Java Developer": [
        "How does HashMap work internally in Java, and how does Java 8 handle hash collisions with balanced trees?",
        "Explain the differences between synchronized blocks, ReentrantLock, and Atomic variables in multithreaded Java.",
        "What are the differences between JVM Stack and Heap memory, and how does Garbage Collection (like G1 or ZGC) manage heap allocation?",
        "How would you design a custom exception hierarchy in a Spring Boot application, and how does @ControllerAdvice help?",
        "Explain the contract between hashCode() and equals() in Java, and what issues arise if it is violated?",
        "How does Spring's Dependency Injection and Bean lifecycle work under the hood?",
        "Explain how the Java Stream API executes operations lazily, and what the difference is between intermediate and terminal operations.",
        "How would you optimize SQL queries and prevent the N+1 query problem when using Hibernate or JPA?"
    ],
    "Backend Developer": [
        "How would you design an API rate limiter to protect backend services against abuse, and what algorithms would you consider?",
        "Explain the differences between REST, GraphQL, and gRPC, and when you would select each for inter-service communication.",
        "How do database indexes (B-Tree vs Hash) improve query latency, and what are the trade-offs on write-heavy workloads?",
        "Explain the Cache-Aside pattern using Redis, and how you would handle cache invalidation and cache stampedes.",
        "How do you ensure data consistency across multiple microservices without distributed two-phase locking transactions?",
        "How would you implement secure authentication and authorization using JWTs, refresh token rotation, and RBAC?",
        "What strategies would you use to gracefully handle downstream service timeouts and cascading failures in a backend pipeline?",
        "How would you design database migrations in a production system that requires zero-downtime deployments?"
    ],
    "Full Stack Developer": [
        "Explain how the React Virtual DOM diffing algorithm works, and how keys help optimize list re-rendering.",
        "How would you architect state management in a large web application between server cache (React Query/RTK) and local UI state?",
        "How would you design a secure RESTful API connection from a Single Page Application, mitigating CORS, XSS, and CSRF risks?",
        "Explain the differences between Server-Side Rendering (SSR), Client-Side Rendering (CSR), and Static Site Generation (SSG).",
        "How do you optimize initial web application load time (code splitting, lazy loading, asset compression)?",
        "How would you structure a normalized database schema and corresponding frontend data models for an e-commerce checkout flow?",
        "Explain how WebSockets differ from HTTP polling and Server-Sent Events (SSE) for real-time dashboard updates.",
        "How would you handle optimistic UI updates on the frontend while ensuring rollback if the backend request fails?"
    ],
    "Software Engineer": [
        "Explain how you would select between an Array, Linked List, Hash Map, and Balanced Tree for a latency-critical application.",
        "What are the SOLID principles of software design, and how have you applied one of them to refactor complex code?",
        "How would you detect and avoid deadlocks in a multithreaded concurrent system?",
        "Explain how virtual memory and paging work in modern operating systems, and why thrashing occurs.",
        "How do you approach profiling and diagnosing a memory leak or CPU spike in a production service?",
        "Describe a situation where choosing composition over inheritance led to a cleaner and more maintainable architecture.",
        "How would you design a scalable notification delivery system capable of dispatching email, SMS, and push alerts?",
        "Explain the time and space complexity tradeoffs of quicksort, mergesort, and heapsort under worst-case inputs."
    ],
    "Data Analyst": [
        "Explain the difference between WHERE and HAVING in SQL, and provide an example where both are required.",
        "How do SQL Window functions (like ROW_NUMBER, RANK, and DENSE_RANK) differ from standard GROUP BY aggregations?",
        "How would you handle missing, outlier, or corrupted data in a dataset using Python and Pandas before analysis?",
        "Explain the difference between star schema and snowflake schema in data warehousing.",
        "How would you design key performance metrics (KPIs) to track user retention and churn for a subscription service?",
        "Explain Type I and Type II errors in hypothesis testing, and how they apply to business decision-making.",
        "How would you optimize a slow-running SQL query that joins multiple multi-million row tables?",
        "Explain how you would perform cohort analysis to understand customer behavior over time."
    ],
    "QA Engineer": [
        "What is the difference between Boundary Value Analysis and Equivalence Partitioning in test case design?",
        "Explain the difference between regression testing and re-testing, and how you decide what tests to automate.",
        "How would you design end-to-end API test automation using Postman or PyTest for a payment gateway endpoint?",
        "What information must a comprehensive bug report include to help developers reproduce and resolve issues quickly?",
        "Explain the testing pyramid (unit, integration, end-to-end) and how you balance automated vs manual testing.",
        "How do you test a system for concurrency and race conditions when multiple users take action simultaneously?",
        "What strategies do you use for performance and load testing, and what metrics (throughput, latency, error rate) do you monitor?",
        "How would you verify a critical software release when requirements change close to the deployment deadline?"
    ]
}


# ---------------------------------------------------------------------------
# HR INTERVIEW PRACTICE QUESTIONS
# ---------------------------------------------------------------------------

_HR_QUESTIONS: List[str] = [
    "Could you walk me through your background, your key technical interests, and what brings you to this interview today?",
    "What do you consider your greatest professional strength, and what is one area you are actively working to improve?",
    "Where do you see yourself in three to five years in your software engineering career?",
    "Tell me about a time you had to adapt quickly to a major change in project requirements, technology, or deadlines.",
    "How do you handle critical feedback or code review suggestions from senior engineers or peers?",
    "Describe how you prioritize tasks when you have multiple competing deadlines and limited time.",
    "Tell me about a time you collaborated with a team member who had a very different working style or opinion from yours.",
    "Why are you interested in this specific role, and what motivates you to do your best work every day?"
]


# ---------------------------------------------------------------------------
# BEHAVIORAL INTERVIEW PRACTICE QUESTIONS (STAR METHODOLOGY)
# ---------------------------------------------------------------------------

_BEHAVIORAL_QUESTIONS: List[str] = [
    "Tell me about a challenging technical problem you encountered in a project. What was the situation, what action did you take, and what was the outcome?",
    "Describe a situation where a project deadline was at risk. How did you manage the situation and what was the final result?",
    "Tell me about a time you made a mistake or experienced a project failure. How did you handle it and what did you learn?",
    "Describe a scenario where you disagreed with a teammate or technical decision. How did you communicate your perspective and resolve the disagreement?",
    "Tell me about a time you took the initiative to learn a new tool, technology, or framework independently to accomplish a goal.",
    "Describe a project where you had to balance building features quickly versus writing clean, maintainable, and tested code.",
    "Tell me about a time you had to explain a complex technical concept to a non-technical peer or stakeholder. How did you ensure clarity?",
    "Describe an experience where you went above and beyond your defined responsibilities to help your team succeed."
]


# ---------------------------------------------------------------------------
# CORE SESSION QUESTION GENERATOR
# ---------------------------------------------------------------------------

def generate_session_question(
    mode: str = "Technical",
    technical_subject: Optional[str] = None,
    role: Optional[str] = None,
    question_index: int = 1,
    total_questions: int = 5,
    difficulty: str = "Medium",
    resume_context: Optional[str] = None,
    parsed_resume: Optional[Dict] = None,
    previous_questions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate an interview question based on:
    1. Interview Mode (Primary)
    2. Technical Subject (Primary technical context when Technical mode)
    3. Job Role (Optional additional context)
    4. Resume Context (Grounded projects and skills)
    5. Sequence Index & Total Questions
    """
    prev_set = set((q or "").strip().lower() for q in (previous_questions or []))
    clean_role = role if (role and role not in ["None", "null", ""]) else None
    clean_subj = technical_subject if (technical_subject and technical_subject not in ["None", "null", ""]) else None

    # MODE 1: HR Interview
    if mode.lower() == "hr":
        pool = [q for q in _HR_QUESTIONS if q.lower() not in prev_set]
        q_text = random.choice(pool or _HR_QUESTIONS)
        trace = "HR Competency & Values Question"
        if clean_role:
            trace += f" (Context: {clean_role})"
        return {
            "question": q_text,
            "mode": "HR",
            "role": clean_role,
            "technical_subject": None,
            "type": "main",
            "source_type": "hr_competency",
            "source_reference": "HR Question Bank",
            "traceability": trace,
            "difficulty": "Standard",
        }

    # MODE 2: Behavioral Interview (STAR Methodology)
    if mode.lower() == "behavioral":
        pool = [q for q in _BEHAVIORAL_QUESTIONS if q.lower() not in prev_set]
        q_text = random.choice(pool or _BEHAVIORAL_QUESTIONS)
        trace = "Behavioral Situation-Based Question (STAR Framework)"
        if clean_role:
            trace += f" (Context: {clean_role})"
        return {
            "question": q_text,
            "mode": "Behavioral",
            "role": clean_role,
            "technical_subject": None,
            "type": "main",
            "source_type": "behavioral_star",
            "source_reference": "STAR Methodology Bank",
            "traceability": trace,
            "difficulty": "Standard",
        }

    # MODE 3: Resume-Based Interview
    if mode.lower() == "resume-based":
        # Check parsed resume items
        if parsed_resume and isinstance(parsed_resume, dict):
            projects = parsed_resume.get("projects", [])
            skills = parsed_resume.get("skills", [])
            experience = parsed_resume.get("experience", [])

            # Dynamic AI grounded question if Gemini is accessible
            if _genai_client and resume_context:
                ai_q = _generate_resume_question_ai(resume_context, clean_role, prev_set)
                if ai_q:
                    return {
                        "question": ai_q["question"],
                        "mode": "Resume-Based",
                        "role": clean_role,
                        "technical_subject": clean_subj,
                        "type": "main",
                        "source_type": ai_q.get("source_type", "project"),
                        "source_reference": ai_q.get("source_reference", "Resume Content"),
                        "traceability": ai_q.get("traceability", "Grounded in uploaded resume"),
                        "difficulty": difficulty,
                    }

            # Deterministic grounding fallback using actual extracted items
            if projects:
                proj = projects[min(question_index - 1, len(projects) - 1)]
                if isinstance(proj, dict):
                    p_title = proj.get("title", "Project")
                    techs = proj.get("technologies") or []
                    skill_ref = ", ".join(techs[:3]) if techs else (skills[0] if skills else "the core stack")
                else:
                    p_title = str(proj)
                    skill_ref = skills[0] if skills else "the core stack"

                q_text = f"In your project '{p_title}', you worked with {skill_ref}. Could you walk me through the system architecture, how you handled data or components, and what challenges you resolved?"
                return {
                    "question": q_text,
                    "mode": "Resume-Based",
                    "role": clean_role,
                    "technical_subject": None,
                    "type": "main",
                    "source_type": "project",
                    "source_reference": p_title,
                    "traceability": f"Based on project '{p_title}' from your resume",
                    "difficulty": difficulty,
                }
            elif experience:
                exp_item = experience[min(question_index - 1, len(experience) - 1)]
                if isinstance(exp_item, dict):
                    i_role = exp_item.get("role", "intern")
                    i_comp = exp_item.get("company", "your organization")
                    ref_name = f"{i_role} at {i_comp}" if i_comp else i_role
                    q_text = f"During your experience as {i_role} at {i_comp}, what was a key technical challenge you encountered, and what architecture decisions did you make?"
                else:
                    ref_name = str(exp_item)
                    q_text = f"During your experience as '{ref_name}', what was a key technical challenge you encountered, and what architecture decisions did you make?"
                return {
                    "question": q_text,
                    "mode": "Resume-Based",
                    "role": clean_role,
                    "technical_subject": None,
                    "type": "main",
                    "source_type": "internship" if "intern" in ref_name.lower() else "experience",
                    "source_reference": ref_name,
                    "traceability": f"Based on experience '{ref_name}' from your resume",
                    "difficulty": difficulty,
                }
            elif skills:
                skill = skills[min(question_index - 1, len(skills) - 1)]
                q_text = f"You listed {skill} on your resume. Could you explain how you have practically applied {skill} in your projects or practical software development?"
                return {
                    "question": q_text,
                    "mode": "Resume-Based",
                    "role": clean_role,
                    "technical_subject": None,
                    "type": "main",
                    "source_type": "skill",
                    "source_reference": skill,
                    "traceability": f"Based on skill '{skill}' from your resume",
                    "difficulty": difficulty,
                }

        # If resume text exists but parsing was raw
        if resume_context and resume_context.strip():
            ai_q = _generate_resume_question_ai(resume_context, clean_role, prev_set)
            if ai_q:
                return {
                    "question": ai_q["question"],
                    "mode": "Resume-Based",
                    "role": clean_role,
                    "technical_subject": clean_subj,
                    "type": "main",
                    "source_type": ai_q.get("source_type", "project"),
                    "source_reference": ai_q.get("source_reference", "Resume Excerpt"),
                    "traceability": ai_q.get("traceability", "Grounded in uploaded resume"),
                    "difficulty": difficulty,
                }

        # Fallback question if resume data is missing
        q_text = "Could you walk me through the architecture and design decisions of the most complex software project on your resume?"
        return {
            "question": q_text,
            "mode": "Resume-Based",
            "role": clean_role,
            "technical_subject": None,
            "type": "main",
            "source_type": "project",
            "source_reference": "Resume Projects",
            "traceability": "Resume-Based Practice Question",
            "difficulty": difficulty,
        }

    # MODE 4: Mixed Interview (Harmonious combination)
    if mode.lower() == "mixed":
        # 1-question session -> Technical or Resume
        if total_questions == 1:
            return generate_session_question("Technical", clean_subj, clean_role, 1, 1, difficulty, resume_context, parsed_resume, previous_questions)

        # Question distribution across a multi-question session:
        # Q1: HR Self-Intro
        if question_index == 1:
            return generate_session_question("HR", None, clean_role, 1, total_questions, difficulty, resume_context, parsed_resume, previous_questions)
        # Q2: Technical question (respects technical subject if selected, or role)
        elif question_index == 2:
            return generate_session_question("Technical", clean_subj, clean_role, 2, total_questions, difficulty, resume_context, parsed_resume, previous_questions)
        # Q3: Resume-grounded question if resume present, otherwise deep technical
        elif question_index == 3:
            if resume_context or (parsed_resume and (parsed_resume.get("skills") or parsed_resume.get("projects"))):
                return generate_session_question("Resume-Based", clean_subj, clean_role, 3, total_questions, difficulty, resume_context, parsed_resume, previous_questions)
            else:
                return generate_session_question("Technical", clean_subj, clean_role, 3, total_questions, difficulty, resume_context, parsed_resume, previous_questions)
        # Q4: Behavioral STAR question
        elif question_index == 4:
            return generate_session_question("Behavioral", None, clean_role, 4, total_questions, difficulty, resume_context, parsed_resume, previous_questions)
        # Q5+: Technical / Architecture depth
        else:
            return generate_session_question("Technical", clean_subj, clean_role, question_index, total_questions, difficulty, resume_context, parsed_resume, previous_questions)

    # MODE 5: Technical (Primary Technical Mode)
    # Priority Rule: Technical Subject ALWAYS takes precedence over Job Role!
    target_pool = []
    trace_label = ""
    resolved_subject = clean_subj

    # CASE A: Technical Subject is specified (e.g. Java, Python, C, C++, DSA, DBMS / SQL, etc.)
    if clean_subj and clean_subj in _SUBJECT_QUESTIONS:
        target_pool = _SUBJECT_QUESTIONS[clean_subj]
        trace_label = f"Technical Domain: {clean_subj}"
        if clean_role:
            trace_label += f" | Optional Context: {clean_role}"

    # CASE B: No Subject specified, but Job Role is selected (e.g. Backend Developer)
    elif clean_role and clean_role in _ROLE_TECHNICAL_QUESTIONS:
        target_pool = _ROLE_TECHNICAL_QUESTIONS[clean_role]
        trace_label = f"Role-Specific Technical: {clean_role}"
        resolved_subject = clean_role

    # CASE C: No Subject and No Role -> General balanced technical questions
    else:
        target_pool = _SUBJECT_QUESTIONS["General"]
        trace_label = "General Technical Practice"
        resolved_subject = "General"

    # Filter out previously asked questions to avoid duplication
    avail = [q for q in target_pool if q.lower() not in prev_set]
    selected_q = random.choice(avail or target_pool)

    return {
        "question": selected_q,
        "mode": "Technical",
        "role": clean_role,
        "technical_subject": resolved_subject,
        "type": "main",
        "source_type": "technical_bank",
        "source_reference": trace_label,
        "traceability": trace_label,
        "difficulty": difficulty,
    }


def _generate_resume_question_ai(resume_text: str, role: Optional[str], prev_questions: set) -> Optional[Dict[str, str]]:
    """Generate a high-relevance interview question grounded in resume text using Gemini."""
    if not _genai_client:
        return None
    try:
        role_clause = f" for a '{role}' role" if role else ""
        prompt = (
            f"You are a technical interviewer interviewing a candidate{role_clause}.\n"
            f"Candidate Resume Excerpt:\n{resume_text[:2000]}\n\n"
            "TASK: Generate ONE highly specific interview question strictly grounded in an actual project, "
            "technical skill, or experience mentioned in the resume excerpt above.\n"
            "CRITICAL RULES:\n"
            "1. You must explicitly name the real project or skill from the resume in the question.\n"
            "2. Do NOT invent or hallucinate technologies or projects that do not appear above.\n"
            "3. Format output strictly as JSON with keys:\n"
            "   'question': the question text,\n"
            "   'source_type': 'project' or 'skill' or 'experience',\n"
            "   'source_reference': the exact project or skill name,\n"
            "   'traceability': 'Grounded in [item] from your resume'\n"
            "Output ONLY the JSON object."
        )
        response = _genai_client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=prompt,
        )
        if response and response.text:
            import json
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("question"):
                q = data["question"].strip()
                if q.lower() not in prev_questions:
                    return {
                        "question": q,
                        "source_type": data.get("source_type", "project"),
                        "source_reference": data.get("source_reference", "Resume"),
                        "traceability": data.get("traceability", "Grounded in uploaded resume"),
                    }
    except Exception as e:
        logger.warning("AI resume question generation fallback: %s", e)
    return None


def generate_follow_up_question(
    main_question: str,
    candidate_answer: str,
    mode: str = "Technical",
    role: Optional[str] = None,
    technical_subject: Optional[str] = None,
) -> Optional[str]:
    """
    Generate an intelligent, contextual follow-up question based on the ACTUAL candidate answer.
    Returns None if the answer was empty, completely off-topic, or too short.
    """
    ans = (candidate_answer or "").strip()
    words = ans.split()
    if len(words) < 8:
        # Answer too short for a meaningful follow-up
        return None

    # Try Gemini AI follow-up generation
    if _genai_client:
        try:
            context_clause = f"Mode: {mode}"
            if technical_subject:
                context_clause += f", Subject: {technical_subject}"
            if role and role not in ["None", "null"]:
                context_clause += f", Role: {role}"

            prompt = (
                f"You are an expert interviewer. {context_clause}\n\n"
                f"Main Question asked: \"{main_question}\"\n"
                f"Candidate's Actual Answer: \"{ans}\"\n\n"
                "Analyze the candidate's answer:\n"
                "- If the candidate made a technical claim, ask how they would test, optimize, or implement it in practice.\n"
                "- If they described a scenario or project, drill deeper into a trade-off, challenge, or result.\n"
                "- If they gave an incomplete explanation, ask for clarification on the missing piece.\n"
                "Requirements:\n"
                "1. The follow-up must be directly grounded in what the candidate actually said.\n"
                "2. It must be ONE concise, professional sentence.\n"
                "3. Output ONLY the follow-up question text without quotes or preamble."
            )
            response = _genai_client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt,
            )
            if response and response.text:
                q = response.text.strip().replace('"', '').replace('**', '')
                if len(q) > 15 and "?" in q:
                    return q
        except Exception as e:
            logger.warning("Gemini follow-up generation failed, falling back to rule-based: %s", e)

    # Safe deterministic fallbacks based on mode and spoken keywords
    ans_lower = ans.lower()
    if mode.lower() == "behavioral":
        return "Could you elaborate on the measurable outcome of that action, and what you would do differently in hindsight?"
    elif mode.lower() == "hr":
        return "How has that experience shaped your day-to-day approach when working in a collaborative team environment?"
    else:
        # Technical fallback
        if any(w in ans_lower for w in ["database", "sql", "query", "index", "table", "schema"]):
            return "How would you handle indexing and transaction isolation if this database scaled to millions of concurrent reads?"
        elif any(w in ans_lower for w in ["api", "service", "request", "server", "endpoint"]):
            return "What error handling and retry strategies would you put in place if that service experienced intermittent network failures?"
        elif any(w in ans_lower for w in ["cache", "redis", "memory"]):
            return "How would you manage cache invalidation and prevent stale data from affecting downstream consumers?"
        elif any(w in ans_lower for w in ["thread", "async", "concurrency", "lock"]):
            return "How would you detect and avoid race conditions or deadlocks in that concurrent scenario?"
        else:
            return "What specific architectural trade-offs did you consider with that approach, and how would you optimize it for high throughput?"


# ---------------------------------------------------------------------------
# BACKWARDS COMPATIBILITY HELPERS
# ---------------------------------------------------------------------------

_last_selection: Dict[str, str] = {"category": "DSA", "difficulty": "Medium"}


def get_last_selection() -> Dict[str, str]:
    return dict(_last_selection)


def generate_question(category: Optional[str] = None, difficulty: Optional[str] = None) -> str:
    """Generate question for single-question legacy endpoint."""
    cat = category if category and category in _SUBJECT_QUESTIONS else "General"
    diff = difficulty if difficulty in ["Easy", "Medium", "Hard"] else "Medium"
    _last_selection["category"] = cat
    _last_selection["difficulty"] = diff
    pool = _SUBJECT_QUESTIONS.get(cat, _SUBJECT_QUESTIONS["General"])
    return random.choice(pool)
