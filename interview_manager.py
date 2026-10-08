"""
interview_manager.py - Multi-question session lifecycle, follow-up orchestration, and results aggregation.
Guarantees strict user data isolation and persistent database backing in MySQL.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models
from question_generator import generate_session_question, generate_follow_up_question
from readiness_scorer import calculate_interview_readiness
from communication_analyzer import analyze_communication

logger = logging.getLogger(__name__)


def create_interview_session(
    db: Session,
    user: models.User,
    mode: str = "Technical",
    role: Optional[str] = None,
    technical_subject: Optional[str] = None,
    difficulty: str = "Medium",
    total_questions: int = 5,
    resume_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Start a brand-new multi-question interview session in MySQL.
    Generates and persists Question 1.
    """
    total_q = max(1, min(int(total_questions or 5), 10))
    clean_role = role if (role and role != "None") else None
    clean_subj = technical_subject if (technical_subject and technical_subject != "None") else None

    session = models.InterviewSession(
        user_id=user.id,
        mode=mode,
        role=clean_role,
        technical_subject=clean_subj,
        difficulty=difficulty,
        total_questions=total_q,
        current_question_index=1,
        status="in_progress",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Check for resume context if available
    resume_context = None
    parsed_resume = None
    if resume_id:
        res = db.query(models.ResumeMetadata).filter(
            models.ResumeMetadata.id == resume_id,
            models.ResumeMetadata.user_id == user.id,
        ).first()
        if res:
            resume_context = f"Skills: {res.skills}\nProjects: {res.projects}\nExperience: {res.experience}"
            parsed_resume = {
                "skills": res.skills or [],
                "structured_skills": getattr(res, "structured_skills", {}) or {},
                "projects": res.projects or [],
                "experience": res.experience or [],
                "internships": [e for e in (res.experience or []) if isinstance(e, dict) and "intern" in e.get("role", "").lower()] or (res.experience or []),
                "certifications": getattr(res, "certifications", []) or [],
                "achievements": getattr(res, "achievements", []) or [],
                "education": getattr(res, "education", []) or [],
            }
    elif mode.lower() in ["resume-based", "mixed"]:
        latest_res = db.query(models.ResumeMetadata).filter(
            models.ResumeMetadata.user_id == user.id
        ).order_by(desc(models.ResumeMetadata.created_at)).first()
        if latest_res:
            resume_context = f"Skills: {latest_res.skills}\nProjects: {latest_res.projects}\nExperience: {latest_res.experience}"
            parsed_resume = {
                "skills": latest_res.skills or [],
                "structured_skills": getattr(latest_res, "structured_skills", {}) or {},
                "projects": latest_res.projects or [],
                "experience": latest_res.experience or [],
                "internships": [e for e in (latest_res.experience or []) if isinstance(e, dict) and "intern" in e.get("role", "").lower()] or (latest_res.experience or []),
                "certifications": getattr(latest_res, "certifications", []) or [],
                "achievements": getattr(latest_res, "achievements", []) or [],
                "education": getattr(latest_res, "education", []) or [],
            }

    # Generate First Question
    q_data = generate_session_question(
        mode=mode,
        technical_subject=clean_subj,
        role=clean_role,
        question_index=1,
        total_questions=total_q,
        difficulty=difficulty,
        resume_context=resume_context,
        parsed_resume=parsed_resume,
        previous_questions=[],
    )

    first_q = models.SessionQuestion(
        session_id=session.id,
        question_order=1,
        question_text=q_data["question"],
        question_type=q_data.get("type", "main"),
        mode=q_data.get("mode", mode),
        technical_subject=q_data.get("technical_subject", clean_subj),
        role=q_data.get("role", clean_role),
        difficulty=q_data.get("difficulty", difficulty),
        traceability=q_data.get("traceability", ""),
        source_type=q_data.get("source_type"),
        source_reference=q_data.get("source_reference"),
    )
    db.add(first_q)
    db.commit()
    db.refresh(first_q)

    return {
        "session_id": session.id,
        "mode": session.mode,
        "role": session.role,
        "technical_subject": session.technical_subject,
        "difficulty": session.difficulty,
        "total_questions": session.total_questions,
        "current_question_index": 1,
        "question": {
            "id": first_q.id,
            "order": first_q.question_order,
            "text": first_q.question_text,
            "type": first_q.question_type,
            "technical_subject": first_q.technical_subject,
            "source_type": first_q.source_type,
            "source_reference": first_q.source_reference,
            "traceability": first_q.traceability,
        }
    }


def record_answer_and_progress(
    db: Session,
    session_id: int,
    question_id: int,
    user_id: int,
    audio_path: Optional[str],
    video_path: Optional[str],
    transcript: str,
    duration: float,
    evaluation: Dict[str, Any],
    video_metrics: Optional[Dict[str, Any]] = None,
    comm_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Save candidate answer and evaluation.
    Determine whether to spawn a dynamic follow-up or advance to next question or complete session.
    """
    # 1. Verify session belongs to user
    session = db.query(models.InterviewSession).filter(
        models.InterviewSession.id == session_id,
        models.InterviewSession.user_id == user_id,
    ).first()
    if not session:
        raise ValueError("Interview session not found or access denied.")

    # 2. Verify question
    question = db.query(models.SessionQuestion).filter(
        models.SessionQuestion.id == question_id,
        models.SessionQuestion.session_id == session.id,
    ).first()
    if not question:
        raise ValueError("Question not found in session.")

    # 3. Create or update CandidateAnswer
    existing_answer = db.query(models.CandidateAnswer).filter(
        models.CandidateAnswer.question_id == question.id
    ).first()

    wpm = comm_metrics.get("words_per_minute", 0.0) if comm_metrics else 0.0
    fillers_count = comm_metrics.get("filler_words_count", 0) if comm_metrics else 0
    fillers_freq = comm_metrics.get("filler_rate_percent", 0.0) if comm_metrics else 0.0

    if existing_answer:
        ans = existing_answer
        ans.audio_path = audio_path
        ans.video_path = video_path
        ans.transcript = transcript
        ans.speech_duration = duration
        ans.words_per_minute = wpm
        ans.filler_words_count = fillers_count
        ans.filler_words_freq = fillers_freq
    else:
        ans = models.CandidateAnswer(
            question_id=question.id,
            session_id=session.id,
            audio_path=audio_path,
            video_path=video_path,
            transcript=transcript,
            speech_duration=duration,
            words_per_minute=wpm,
            filler_words_count=fillers_count,
            filler_words_freq=fillers_freq,
        )
        db.add(ans)
    db.commit()
    db.refresh(ans)

    # 4. Create or update QuestionEvaluation
    existing_eval = db.query(models.QuestionEvaluation).filter(
        models.QuestionEvaluation.answer_id == ans.id
    ).first()

    # Extract scores
    t_score = float(evaluation.get("technical_score", 0.0))
    c_score = float(evaluation.get("communication_score", 0.0))
    p_score = float(evaluation.get("problem_solving_score", 0.0))
    l_score = float(evaluation.get("leadership_score", 0.0))
    conf_score = float(video_metrics.get("visual_confidence_score", 7.0)) if video_metrics else 7.0
    o_score = float(evaluation.get("score", (t_score * 0.4 + c_score * 0.3 + p_score * 0.3) * 10))

    star_data = evaluation.get("star_analysis", {})

    if existing_eval:
        ev = existing_eval
        ev.technical_score = t_score
        ev.communication_score = c_score
        ev.problem_solving_score = p_score
        ev.leadership_score = l_score
        ev.confidence_score = conf_score
        ev.overall_score = o_score
        ev.feedback = evaluation.get("feedback", "")
        ev.ideal_answer = evaluation.get("ideal_answer", "")
        ev.strengths = evaluation.get("strengths", [])
        ev.weaknesses = evaluation.get("weaknesses", [])
        ev.suggestions = evaluation.get("improvement_suggestions", evaluation.get("suggestions", []))
        ev.star_analysis = star_data
        ev.video_metrics = video_metrics or {}
        ev.communication_metrics = comm_metrics or {}
    else:
        ev = models.QuestionEvaluation(
            answer_id=ans.id,
            question_id=question.id,
            technical_score=t_score,
            communication_score=c_score,
            problem_solving_score=p_score,
            leadership_score=l_score,
            confidence_score=conf_score,
            overall_score=o_score,
            feedback=evaluation.get("feedback", ""),
            ideal_answer=evaluation.get("ideal_answer", ""),
            strengths=evaluation.get("strengths", []),
            weaknesses=evaluation.get("weaknesses", []),
            suggestions=evaluation.get("improvement_suggestions", evaluation.get("suggestions", [])),
            star_analysis=star_data,
            video_metrics=video_metrics or {},
            communication_metrics=comm_metrics or {},
        )
        db.add(ev)
    db.commit()
    db.refresh(ev)

    # 5. Check if dynamic follow-up question is warranted
    # Only offer follow-up if current question was 'main' (prevent recursive endless follow-ups)
    follow_up_generated = False
    next_question = None

    if question.question_type == "main":
        follow_up_text = generate_follow_up_question(
            main_question=question.question_text,
            candidate_answer=transcript,
            mode=session.mode,
            role=session.role,
        )
        if follow_up_text:
            # Create follow-up question
            follow_q = models.SessionQuestion(
                session_id=session.id,
                question_order=question.question_order,  # shares index or 1.1
                question_text=follow_up_text,
                question_type="follow_up",
                mode=session.mode,
                technical_subject=session.technical_subject,
                role=session.role,
                difficulty=session.difficulty,
                traceability=f"AI Follow-up based on your answer to Question #{question.question_order}",
                source_type="follow_up",
                source_reference=f"Question #{question.question_order}",
                parent_question_id=question.id,
            )
            db.add(follow_q)
            db.commit()
            db.refresh(follow_q)
            follow_up_generated = True
            next_question = {
                "id": follow_q.id,
                "order": follow_q.question_order,
                "text": follow_q.question_text,
                "type": "follow_up",
                "technical_subject": follow_q.technical_subject,
                "traceability": follow_q.traceability,
                "source_type": follow_q.source_type,
                "source_reference": follow_q.source_reference,
                "parent_id": question.id,
            }

    # 6. If no follow-up, advance to next main question or complete session
    if not follow_up_generated:
        main_questions_count = db.query(models.SessionQuestion).filter(
            models.SessionQuestion.session_id == session.id,
            models.SessionQuestion.question_type == "main",
        ).count()

        if main_questions_count < session.total_questions:
            # Generate next main question
            all_prev_texts = [q.question_text for q in session.questions]
            next_order = main_questions_count + 1
            session.current_question_index = next_order
            db.commit()

            # Retrieve resume if available
            parsed_resume = None
            resume_context = None
            if session.mode in ["Resume-Based", "Mixed"]:
                latest_res = db.query(models.ResumeMetadata).filter(
                    models.ResumeMetadata.user_id == user_id
                ).order_by(desc(models.ResumeMetadata.created_at)).first()
                if latest_res:
                    resume_context = f"Skills: {latest_res.skills}\nProjects: {latest_res.projects}\nExperience: {latest_res.experience}"
                    parsed_resume = {
                        "skills": latest_res.skills or [],
                        "structured_skills": getattr(latest_res, "structured_skills", {}) or {},
                        "projects": latest_res.projects or [],
                        "experience": latest_res.experience or [],
                        "internships": [e for e in (latest_res.experience or []) if isinstance(e, dict) and "intern" in e.get("role", "").lower()] or (latest_res.experience or []),
                        "certifications": getattr(latest_res, "certifications", []) or [],
                        "achievements": getattr(latest_res, "achievements", []) or [],
                        "education": getattr(latest_res, "education", []) or [],
                    }

            q_data = generate_session_question(
                mode=session.mode,
                technical_subject=session.technical_subject,
                role=session.role,
                question_index=next_order,
                total_questions=session.total_questions,
                difficulty=session.difficulty,
                resume_context=resume_context,
                parsed_resume=parsed_resume,
                previous_questions=all_prev_texts,
            )

            next_q_model = models.SessionQuestion(
                session_id=session.id,
                question_order=next_order,
                question_text=q_data["question"],
                question_type="main",
                mode=q_data.get("mode", session.mode),
                technical_subject=q_data.get("technical_subject", session.technical_subject),
                role=q_data.get("role", session.role),
                difficulty=q_data.get("difficulty", session.difficulty),
                traceability=q_data.get("traceability", ""),
                source_type=q_data.get("source_type"),
                source_reference=q_data.get("source_reference"),
            )
            db.add(next_q_model)
            db.commit()
            db.refresh(next_q_model)

            next_question = {
                "id": next_q_model.id,
                "order": next_q_model.question_order,
                "text": next_q_model.question_text,
                "type": "main",
                "technical_subject": next_q_model.technical_subject,
                "source_type": next_q_model.source_type,
                "source_reference": next_q_model.source_reference,
                "traceability": next_q_model.traceability,
            }
        else:
            # Session Complete! Aggregate results
            finalize_session_results(db, session)

    return {
        "session_id": session.id,
        "status": session.status,
        "current_question_index": session.current_question_index,
        "total_questions": session.total_questions,
        "current_evaluation": {
            "score": ev.overall_score,
            "technical_score": ev.technical_score,
            "communication_score": ev.communication_score,
            "problem_solving_score": ev.problem_solving_score,
            "confidence_score": ev.confidence_score,
            "feedback": ev.feedback,
            "ideal_answer": ev.ideal_answer,
            "strengths": ev.strengths,
            "weaknesses": ev.weaknesses,
            "suggestions": ev.suggestions,
            "star_analysis": ev.star_analysis,
        },
        "has_next_question": next_question is not None,
        "next_question": next_question,
        "is_follow_up": follow_up_generated,
        "is_completed": session.status == "completed",
    }


def finalize_session_results(db: Session, session: models.InterviewSession) -> models.SessionResult:
    """Aggregate question evaluations into complete SessionResult with readiness score."""
    evaluations = []
    videos = []
    comms = []

    for q in session.questions:
        if q.evaluation:
            evaluations.append({
                "technical_score": q.evaluation.technical_score,
                "communication_score": q.evaluation.communication_score,
                "problem_solving_score": q.evaluation.problem_solving_score,
                "confidence_score": q.evaluation.confidence_score,
                "overall_score": q.evaluation.overall_score,
            })
            if q.evaluation.video_metrics:
                videos.append(q.evaluation.video_metrics)
            if q.evaluation.communication_metrics:
                comms.append(q.evaluation.communication_metrics)

    readiness = calculate_interview_readiness(evaluations, videos, comms)

    # Calculate averages
    t_avg = sum(e["technical_score"] for e in evaluations) / len(evaluations) if evaluations else 0.0
    c_avg = sum(e["communication_score"] for e in evaluations) / len(evaluations) if evaluations else 0.0
    p_avg = sum(e["problem_solving_score"] for e in evaluations) / len(evaluations) if evaluations else 0.0
    l_avg = sum(e.get("leadership_score", 7.0) for e in evaluations) / len(evaluations) if evaluations else 7.0
    conf_avg = sum(e["confidence_score"] for e in evaluations) / len(evaluations) if evaluations else 7.0
    overall_avg = sum(e["overall_score"] for e in evaluations) / len(evaluations) if evaluations else 0.0

    # Aggregate unique strengths and weaknesses
    all_strengths = []
    all_weaknesses = []
    all_suggestions = []
    for q in session.questions:
        if q.evaluation:
            all_strengths.extend(q.evaluation.strengths or [])
            all_weaknesses.extend(q.evaluation.weaknesses or [])
            all_suggestions.extend(q.evaluation.suggestions or [])

    unique_strengths = list(dict.fromkeys(all_strengths))[:5]
    unique_weaknesses = list(dict.fromkeys(all_weaknesses))[:5]
    unique_suggestions = list(dict.fromkeys(all_suggestions))[:5]

    session.status = "completed"
    session.overall_score = round(overall_avg, 1)
    session.readiness_score = readiness["readiness_score"]
    session.readiness_level = readiness["readiness_level"]
    session.completed_at = datetime.utcnow()

    # Create or update SessionResult
    result = db.query(models.SessionResult).filter(models.SessionResult.session_id == session.id).first()
    if not result:
        result = models.SessionResult(
            session_id=session.id,
            user_id=session.user_id,
            overall_score=session.overall_score,
            technical_avg=round(t_avg, 1),
            communication_avg=round(c_avg, 1),
            problem_solving_avg=round(p_avg, 1),
            leadership_avg=round(l_avg, 1),
            confidence_avg=round(conf_avg, 1),
            readiness_score=session.readiness_score,
            readiness_level=session.readiness_level,
            readiness_summary=readiness["readiness_summary"],
            strengths=unique_strengths,
            weaknesses=unique_weaknesses,
            improvement_suggestions=unique_suggestions,
        )
        db.add(result)
    else:
        result.overall_score = session.overall_score
        result.technical_avg = round(t_avg, 1)
        result.communication_avg = round(c_avg, 1)
        result.problem_solving_avg = round(p_avg, 1)
        result.leadership_avg = round(l_avg, 1)
        result.confidence_avg = round(conf_avg, 1)
        result.readiness_score = session.readiness_score
        result.readiness_level = session.readiness_level
        result.readiness_summary = readiness["readiness_summary"]
        result.strengths = unique_strengths
        result.weaknesses = unique_weaknesses
        result.improvement_suggestions = unique_suggestions

    db.commit()
    db.refresh(result)
    return result


def get_user_interview_history(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Fetch user-specific interview history from MySQL. Strictly isolated to user_id."""
    sessions = db.query(models.InterviewSession).filter(
        models.InterviewSession.user_id == user_id
    ).order_by(desc(models.InterviewSession.created_at)).all()

    history = []
    for s in sessions:
        history.append({
            "id": s.id,
            "mode": s.mode,
            "role": s.role or "None",
            "technical_subject": getattr(s, "technical_subject", None) or "None",
            "difficulty": s.difficulty,
            "total_questions": s.total_questions,
            "status": s.status,
            "overall_score": s.overall_score,
            "readiness_score": s.readiness_score,
            "readiness_level": s.readiness_level,
            "date": s.created_at.strftime("%Y-%m-%d"),
            "time": s.created_at.strftime("%H:%M:%S"),
            "completed_at": s.completed_at.strftime("%Y-%m-%d %H:%M:%S") if s.completed_at else None,
        })
    return history


def get_session_details(db: Session, session_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve complete session breakdown for result and detail screens. User isolated."""
    session = db.query(models.InterviewSession).filter(
        models.InterviewSession.id == session_id,
        models.InterviewSession.user_id == user_id,
    ).first()
    if not session:
        return None

    questions_data = []
    for q in session.questions:
        q_item = {
            "id": q.id,
            "order": q.question_order,
            "text": q.question_text,
            "type": q.question_type,
            "technical_subject": getattr(q, "technical_subject", None),
            "source_type": getattr(q, "source_type", None),
            "source_reference": getattr(q, "source_reference", None),
            "traceability": q.traceability,
            "has_answer": q.answer is not None,
            "transcript": q.answer.transcript if q.answer else None,
            "duration": q.answer.speech_duration if q.answer else None,
            "words_per_minute": q.answer.words_per_minute if q.answer else None,
            "filler_words_count": q.answer.filler_words_count if q.answer else None,
        }
        if q.evaluation:
            q_item["evaluation"] = {
                "overall_score": q.evaluation.overall_score,
                "technical_score": q.evaluation.technical_score,
                "communication_score": q.evaluation.communication_score,
                "problem_solving_score": q.evaluation.problem_solving_score,
                "confidence_score": q.evaluation.confidence_score,
                "feedback": q.evaluation.feedback,
                "ideal_answer": q.evaluation.ideal_answer,
                "strengths": q.evaluation.strengths,
                "weaknesses": q.evaluation.weaknesses,
                "suggestions": q.evaluation.suggestions,
                "star_analysis": q.evaluation.star_analysis,
                "video_metrics": q.evaluation.video_metrics,
                "communication_metrics": q.evaluation.communication_metrics,
            }
        questions_data.append(q_item)

    result_data = None
    if session.result:
        result_data = {
            "overall_score": session.result.overall_score,
            "technical_avg": session.result.technical_avg,
            "communication_avg": session.result.communication_avg,
            "problem_solving_avg": session.result.problem_solving_avg,
            "leadership_avg": session.result.leadership_avg,
            "confidence_avg": session.result.confidence_avg,
            "readiness_score": session.result.readiness_score,
            "readiness_level": session.result.readiness_level,
            "readiness_summary": session.result.readiness_summary,
            "strengths": session.result.strengths,
            "weaknesses": session.result.weaknesses,
            "improvement_suggestions": session.result.improvement_suggestions,
        }

    return {
        "id": session.id,
        "mode": session.mode,
        "role": session.role or "None",
        "technical_subject": getattr(session, "technical_subject", None) or "None",
        "difficulty": session.difficulty,
        "total_questions": session.total_questions,
        "current_question_index": session.current_question_index,
        "status": session.status,
        "overall_score": session.overall_score,
        "readiness_score": session.readiness_score,
        "readiness_level": session.readiness_level,
        "created_at": session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "completed_at": session.completed_at.strftime("%Y-%m-%d %H:%M:%S") if session.completed_at else None,
        "questions": questions_data,
        "result": result_data,
    }
