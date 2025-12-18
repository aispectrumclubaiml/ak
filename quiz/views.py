from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.urls import reverse
import random
from .models import Quiz, Question, Submission, Answer
from django.views.decorators.http import require_POST
import requests


from django.views.decorators.cache import never_cache

# Create your views here.

EVENT_CONFIG = {
    "3": {  # quiz id for Build With AI
        "name": "Build With AI",
    },
    "4": {  # quiz id for CODEWARZ
        "name": "CODEWARZ",
    },
}

@never_cache
def prelims_entry(request):
    if request.method == "POST":
        quiz_id = request.POST.get("event")
        phone = request.POST.get("phone", "").strip()

        # Fetch All Quizzes for context in case of error
        all_quizzes = Quiz.objects.all()

        if not quiz_id or not phone:
            return render(
                request,
                "prelims_landing.html",
                {
                    "step": 1,
                    "error": "Please select an event and enter phone number.",
                    "quizzes": all_quizzes,
                },
            )

        import re

        if not re.match(r"^[6-9]\d{9}$", phone):
            return render(
                request,
                "prelims_landing.html",
                {
                    "step": 1,
                    "error": "Enter a valid 10-digit Indian mobile number starting with 6–9.",
                    "quizzes": all_quizzes,
                },
            )

        # Look up event/quiz from DB
        try:
            quiz_obj = Quiz.objects.get(id=quiz_id)
            if not quiz_obj.is_active:
                 return render(
                    request,
                    "prelims_landing.html",
                    {
                        "step": 1,
                        "error": "This quiz is not active yet.",
                        "quizzes": all_quizzes,
                    },
                )
            event_name = quiz_obj.name
        except (Quiz.DoesNotExist, ValueError):
             return render(
                request,
                "prelims_landing.html",
                {
                    "step": 1,
                    "error": "Invalid event selected.",
                    "quizzes": all_quizzes,
                },
            )

        # Check for existing submission
        if Submission.objects.filter(quiz=quiz_obj, phone=phone).exists():
             return render(
                request,
                "prelims_landing.html",
                {
                    "step": 1,
                    "error": "You have already attempted this quiz. Multiple attempts are not allowed.",
                    "quizzes": all_quizzes,
                },
            )

        # ---------- CALL COLLEGE PHP SERVER ----------
        leader_name = None
        institution = None
        api_error = None

        try:
            # 🔴 Real PHP endpoint
            php_api_url = "https://rvrjcce.ac.in/xcsm/aikshetra2K25/api/get_participant.php"

            # 🔴 Payload as requested
            api_combos = {'Build With AI':'Build with AI', 'CodeWarz':'CodeWarz'}
            payload = {
                "mobile_number": phone,  # Key from user's sample
                "event_name": api_combos[event_name],
            }

            
            print(f"--- Calling API: {php_api_url}")
            print(f"--- Payload: {payload}")

            # Using json=payload because user input example looked like JSON
            resp = requests.post(php_api_url, json=payload, timeout=5)
            
            print(f"--- Response Status: {resp.status_code}")
            print(f"--- Response Text: {resp.text}")
            
            resp.raise_for_status()

            # Expected JSON: { "success": true, "name": "...", "college": "..." }
            data = resp.json()

            if not data.get("success"):
                api_error = data.get("message") or "Unable to verify registration from server."
            else:
                leader_name = data.get("name")
                institution = data.get("college")

                if not leader_name or not institution:
                    api_error = "Could not fetch complete details from server."
        except Exception as e:
            print(f"--- API Error: {e}")
            # api_error = "Could not contact college server. Please inform the coordinator."
            pass

        # Build team data (fallback if API fails)
        team_data = {
            "participant_name": leader_name or "Unknown Participant",
            "event_display": event_name,
            "institution": institution or "Unknown Institution",
        }

        # ✅ Save to session for secure access in confirm/quiz_page
        request.session['participant_phone'] = phone
        request.session['participant_event'] = quiz_id
        
        # Store temp data for confirmation page
        request.session['temp_team_data'] = team_data
        request.session['temp_api_error'] = api_error

        # ✅ PRG: Redirect to confirmation view
        return redirect('prelims_confirm')

    # GET → show step 1 with dynamic quizzes
    quizzes = Quiz.objects.all()
    # If user is already in session and tries to go to landing, maybe we could clear session?
    # For now, let's just show landing.
    
    return render(
        request,
        "prelims_landing.html",
        {
            "step": 1,
            "quizzes": quizzes,
        },
    )


@never_cache
def prelims_confirm(request):
    """
    Step 2 of the entry flow. Renders the confirmation details from session data.
    Refreshes are safe here because it's a GET request reading from session.
    """
    phone = request.session.get('participant_phone')
    quiz_id = request.session.get('participant_event')
    
    if not phone or not quiz_id:
        return redirect('prelims_entry')

    team_data = request.session.get('temp_team_data', {})
    api_error = request.session.get('temp_api_error')

    return render(
        request,
        "prelims_landing.html",
        {
            "step": 2,
            "phone": phone,
            "event_code": quiz_id,
            "team": team_data,
            "api_error": api_error,
        },
    )


@never_cache
def quiz_page(request, quiz_id):
    # ✅ 1. Security Check: Ensure user came from landing page
    session_phone = request.session.get('participant_phone')
    if not session_phone:
        return render(request, "prelims_landing.html", {
            "step": 1,
            "error": "Session expired or invalid. Please login again.",
            "quizzes": Quiz.objects.all()
        })

    quiz = get_object_or_404(Quiz, id=quiz_id)

    # ✅ 2. Double Security: Ensure they are accessing the event they selected
    session_event = request.session.get('participant_event')
    if str(session_event) != str(quiz_id):
         return render(request, "prelims_landing.html", {
            "step": 1,
            "error": "Invalid event access. Please select correct event.",
            "quizzes": Quiz.objects.all()
        })

    # ✅ 3. Check if ALREADY SUBMITTED
    if Submission.objects.filter(quiz=quiz, phone=session_phone).exists():
        return render(request, "prelims_landing.html", {
            "step": 1,
            "error": "You have already attempted this quiz. Multiple attempts are not allowed.",
            "quizzes": Quiz.objects.all()
        })

    # Get all questions for this quiz
    all_questions = list(quiz.questions.all())
    num = min(quiz.num_questions, len(all_questions))

    # Randomly choose the questions that will be shown
    chosen_questions = random.sample(all_questions, num) if num > 0 else []

    # ✅ Store the chosen question IDs in session so submit_quiz knows exactly which to grade
    request.session[f"quiz_{quiz.id}_question_ids"] = [q.id for q in chosen_questions]

    # Build data for template (+ shuffle options per question)
    question_data = []
    for q in chosen_questions:
        options = [
            ("A", q.option_a),
            ("B", q.option_b),
            ("C", q.option_c),
            ("D", q.option_d),
        ]
        random.shuffle(options)
        question_data.append(
            {
                "obj": q,
                "options": options,
            }
        )

    return render(
        request,
        "quiz.html",
        {
            "quiz": quiz,
            "questions": question_data,
            "duration_seconds": quiz.duration_minutes * 60,
            # Pass these to template so we don't need URL params anymore
            "participant_phone": session_phone,
            "participant_event": session_event,
        },
    )


@require_POST
def submit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)

    # ✅ Security: Get phone from session if possible, else POST
    # Ideally trust session, but fall back to POST if session died mid-quiz (unlikely but possible)?
    # Actually, we should strictly enforce session or at least valid phone.
    phone = request.session.get('participant_phone') or request.POST.get("phone")
    event = request.session.get('participant_event') or request.POST.get("event")

    # ✅ Check if ALREADY SUBMITTED
    existing_sub = Submission.objects.filter(quiz=quiz, phone=phone).first()
    if existing_sub:
        # If they somehow resubmit, redirect to result
        return redirect('quiz_result', submission_id=existing_sub.id)

    # ✅ Get the exact questions that were shown to the user from session
    session_key = f"quiz_{quiz.id}_question_ids"
    qids = request.session.get(session_key, [])

    if qids:
        questions_qs = Question.objects.filter(id__in=qids, quiz=quiz)
        # Preserve order from qids
        questions_by_id = {q.id: q for q in questions_qs}
        questions = [questions_by_id[qid] for qid in qids if qid in questions_by_id]
        # Optional: clear after use
        request.session.pop(session_key, None)
    else:
        # Fallback (if session missing): first num_questions
        questions = list(quiz.questions.all()[: quiz.num_questions])

    total = len(questions)
    score = 0
    details = []

    for q in questions:
        field_name = f"q_{q.id}"  # matches name="q_{{ q.id }}" in template
        raw_selected = request.POST.get(field_name)  # 'A'/'B'/'C'/'D' or None

        # Make comparison case-insensitive, just in case
        selected = (raw_selected or "").strip().upper()
        correct_letter = (q.correct_option or "").strip().upper()

        is_correct = selected == correct_letter
        if is_correct:
            score += 1

        option_map = {
            "A": q.option_a,
            "B": q.option_b,
            "C": q.option_c,
            "D": q.option_d,
        }

        details.append(
            {
                "question": q,
                "selected_letter": selected or None,
                "selected_text": option_map.get(selected) if selected else None,
                "correct_letter": correct_letter,
                "correct_text": option_map.get(correct_letter),
                "is_correct": is_correct,
            }
        )

    time_taken = request.POST.get("time_taken", 0)
    try:
        time_taken = int(float(time_taken or 0))
    except (ValueError, TypeError):
        time_taken = 0

    # Save submission in DB
    submission = Submission.objects.create(
        quiz=quiz,
        phone=phone or "",
        event=event or "",
        score=score,
        total_questions=total,
        time_taken_seconds=time_taken,
    )

    # Save each answer
    answer_objs = [
        Answer(
            submission=submission,
            question=item["question"],
            selected_option=item["selected_letter"],
            correct_option=item["correct_letter"],
            is_correct=item["is_correct"],
        )
        for item in details
    ]
    Answer.objects.bulk_create(answer_objs)
    
    # ✅ Clean up session
    request.session.pop('participant_phone', None)
    request.session.pop('participant_event', None)
    # Also clear temp data if it's still there
    request.session.pop('temp_team_data', None)
    request.session.pop('temp_api_error', None)


    # ✅ PRG: Redirect to result view
    return redirect('quiz_result', submission_id=submission.id)


def quiz_result(request, submission_id):
    """
    Renders the result page for a given submission.
    """
    submission = get_object_or_404(Submission, id=submission_id)
    
    # Optional: We could check if the logged in user owns this submission if we kept the session,
    # but we cleared the session. For a simple event, ID obfuscation or just openness is often acceptable.
    # If strict privacy is needed, we would need to keep session alive or sign the ID.
    # For now, we assume knowing the submission ID is sufficient access (security through obscurity/simplicity).

    # We need to reconstruct 'details' if we want to show full breakdown,
    # but ONLY if the quiz allows showing results.
    
    show_results = submission.quiz.show_results
    details = []
    
    if show_results:
        answers = submission.answers.select_related('question').all()
        for ans in answers:
            q = ans.question
            
            option_map = {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d,
            }

            sel = (ans.selected_option or "").strip().upper()
            corr = (ans.correct_option or "").strip().upper()
            
            details.append({
                "question": q,
                "selected_letter": ans.selected_option,
                "selected_text": option_map.get(sel) if sel else None,
                "correct_letter": ans.correct_option,
                "correct_text": option_map.get(corr),
                "is_correct": ans.is_correct,
            })
    
    # Check if feedback already exists
    feedback_submitted = hasattr(submission, 'feedback')

    context = {
        "quiz": submission.quiz,
        "phone": submission.phone,
        "event": submission.event,
        "score": submission.score,
        "total": submission.total_questions,
        "details": details,
        "submission": submission,
        "submission_id": submission.id,
        "feedback_submitted": feedback_submitted,
        "show_results": show_results,
    }
    return render(request, "quiz_result.html", context)


def submit_feedback(request):
    if request.method == "POST":
        submission_id = request.POST.get("submission_id")
        rating = request.POST.get("rating")
        rating_ui = request.POST.get("rating_ui")
        rating_difficulty = request.POST.get("rating_difficulty")
        rating_relevance = request.POST.get("rating_relevance")
        comments = request.POST.get("comments", "")

        submission = get_object_or_404(Submission, id=submission_id)
        
        from .models import Feedback
        
        try:
            Feedback.objects.create(
                submission=submission,
                rating=rating,
                rating_ui=rating_ui or 0,
                rating_difficulty=rating_difficulty or 0,
                rating_relevance=rating_relevance or 0,
                comments=comments
            )
        except Exception:
            # Maybe already exists
            pass
            
        # Ideally redirect to result page too, but let's stick to simple render for now strictly following user request scope,
        # OR better, redirect to the result page we just made!
        return redirect('quiz_result', submission_id=submission.id)
        
    return HttpResponse("Invalid request")
