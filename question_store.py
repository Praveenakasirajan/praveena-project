"""
question_store.py - In-memory session state management for interview questions and resume data.
"""

current_question: str = ""
current_category: str = ""
current_difficulty: str = ""
current_traceability: str = ""
current_resume_context: str = ""
current_resume_filename: str = ""
current_parsed_resume: dict = {}


def set_question(question: str, category: str = "", difficulty: str = "", traceability: str = ""):
    global current_question, current_category, current_difficulty, current_traceability
    current_question = question
    current_category = category
    current_difficulty = difficulty
    current_traceability = traceability


def set_resume(filename: str, text: str, parsed: dict):
    global current_resume_filename, current_resume_context, current_parsed_resume
    current_resume_filename = filename
    current_resume_context = text
    current_parsed_resume = parsed


def reset_session():
    global current_question, current_category, current_difficulty, current_traceability
    global current_resume_context, current_resume_filename, current_parsed_resume
    current_question = ""
    current_category = ""
    current_difficulty = ""
    current_traceability = ""
    current_resume_context = ""
    current_resume_filename = ""
    current_parsed_resume = {}


def clear_resume():
    global current_resume_context, current_resume_filename, current_parsed_resume
    current_resume_context = ""
    current_resume_filename = ""
    current_parsed_resume = {}