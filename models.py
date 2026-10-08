"""
models.py - SQLAlchemy ORM entities for AI Interview Coach.
Relational schema supporting users, sessions, questions, answers, evaluations, and results.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Enum,
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship("InterviewSession", back_populates="user", cascade="all, delete-orphan")
    resumes = relationship("ResumeMetadata", back_populates="user", cascade="all, delete-orphan")
    results = relationship("SessionResult", back_populates="user", cascade="all, delete-orphan")


class ResumeMetadata(Base):
    __tablename__ = "resume_metadata"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    candidate_name = Column(String(120), nullable=True)
    skills = Column(JSON, default=list)
    projects = Column(JSON, default=list)
    experience = Column(JSON, default=list)
    education = Column(JSON, default=list)
    certifications = Column(JSON, default=list)
    achievements = Column(JSON, default=list)
    structured_skills = Column(JSON, default=dict)
    skill_gaps = Column(JSON, default=list)
    resume_strengths = Column(JSON, default=list)
    recommended_improvements = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="resumes")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String(50), nullable=False, default="Technical")  # Technical, HR, Behavioral, Resume-Based, Mixed
    role = Column(String(80), nullable=True)  # Optional: Java Developer, Backend Developer, etc. or None
    technical_subject = Column(String(80), nullable=True)  # Java, Python, C, C++, DSA, DBMS/SQL, etc.
    difficulty = Column(String(30), nullable=False, default="Medium")
    total_questions = Column(Integer, nullable=False, default=5)
    current_question_index = Column(Integer, nullable=False, default=1)
    status = Column(String(30), nullable=False, default="in_progress")  # in_progress, completed, abandoned
    
    overall_score = Column(Float, nullable=True)
    readiness_score = Column(Float, nullable=True)
    readiness_level = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")
    questions = relationship("SessionQuestion", back_populates="session", cascade="all, delete-orphan", order_by="SessionQuestion.question_order")
    answers = relationship("CandidateAnswer", back_populates="session", cascade="all, delete-orphan")
    result = relationship("SessionResult", back_populates="session", uselist=False, cascade="all, delete-orphan")


class SessionQuestion(Base):
    __tablename__ = "session_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_order = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), nullable=False, default="main")  # main, follow_up
    mode = Column(String(50), nullable=False)
    role = Column(String(80), nullable=True)
    technical_subject = Column(String(80), nullable=True)
    difficulty = Column(String(30), nullable=True)
    traceability = Column(String(255), nullable=True)
    source_type = Column(String(50), nullable=True)  # skill, project, internship, education, experience
    source_reference = Column(String(255), nullable=True)
    parent_question_id = Column(Integer, ForeignKey("session_questions.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("InterviewSession", back_populates="questions")
    answer = relationship("CandidateAnswer", back_populates="question", uselist=False, cascade="all, delete-orphan")
    evaluation = relationship("QuestionEvaluation", back_populates="question", uselist=False, cascade="all, delete-orphan")


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("session_questions.id", ondelete="CASCADE"), nullable=False, unique=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    audio_path = Column(String(500), nullable=True)
    video_path = Column(String(500), nullable=True)
    transcript = Column(Text, nullable=True)
    speech_duration = Column(Float, nullable=True, default=0.0)
    words_per_minute = Column(Float, nullable=True, default=0.0)
    filler_words_count = Column(Integer, nullable=True, default=0)
    filler_words_freq = Column(Float, nullable=True, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("InterviewSession", back_populates="answers")
    question = relationship("SessionQuestion", back_populates="answer")
    evaluation = relationship("QuestionEvaluation", back_populates="answer", uselist=False, cascade="all, delete-orphan")


class QuestionEvaluation(Base):
    __tablename__ = "question_evaluations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    answer_id = Column(Integer, ForeignKey("candidate_answers.id", ondelete="CASCADE"), nullable=False, unique=True)
    question_id = Column(Integer, ForeignKey("session_questions.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    technical_score = Column(Float, default=0.0)
    communication_score = Column(Float, default=0.0)
    problem_solving_score = Column(Float, default=0.0)
    leadership_score = Column(Float, default=0.0)
    confidence_score = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)

    feedback = Column(Text, nullable=True)
    ideal_answer = Column(Text, nullable=True)
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    suggestions = Column(JSON, default=list)
    star_analysis = Column(JSON, default=dict)  # Situation, Task, Action, Result analysis for behavioral
    video_metrics = Column(JSON, default=dict)
    communication_metrics = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    answer = relationship("CandidateAnswer", back_populates="evaluation")
    question = relationship("SessionQuestion", back_populates="evaluation")


class SessionResult(Base):
    __tablename__ = "session_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    overall_score = Column(Float, nullable=False, default=0.0)
    technical_avg = Column(Float, nullable=False, default=0.0)
    communication_avg = Column(Float, nullable=False, default=0.0)
    problem_solving_avg = Column(Float, nullable=False, default=0.0)
    leadership_avg = Column(Float, nullable=False, default=0.0)
    confidence_avg = Column(Float, nullable=False, default=0.0)

    readiness_score = Column(Float, nullable=False, default=0.0)
    readiness_level = Column(String(50), nullable=False, default="Developing")
    readiness_summary = Column(Text, nullable=True)

    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    improvement_suggestions = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("InterviewSession", back_populates="result")
    user = relationship("User", back_populates="results")
