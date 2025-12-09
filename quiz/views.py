from django.shortcuts import render, HttpResponse
from django.urls import reverse
import random
from django.shortcuts import render, get_object_or_404
from .models import Quiz, Question, Submission, Answer
from django.views.decorators.http import require_POST
import requests


# Create your views here.


from django.shortcuts import render

EVENT_CONFIG = {
    "3": {  # quiz id for Build With AI
        "name": "Build With AI",
    },
    "4": {  # quiz id for CODEWARZ
        "name": "CODEWARZ",
    },
}


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
        # Build participant data (fallback if API fails)
        team_data = {
            "participant_name": leader_name or "Unknown Participant",
            "event_display": event_name,
            "institution": institution or "Unknown Institution",
        }

        return render(
            request,
            "prelims_landing.html",
            {
                "step": 2,
                "phone": phone,
                "event_code": quiz_id,  # using quiz.id
                "team": team_data,
                "api_error": api_error,
            },
        )

    # GET → show step 1 with dynamic quizzes
    quizzes = Quiz.objects.all()
    return render(
        request,
        "prelims_landing.html",
        {
            "step": 1,
            "quizzes": quizzes,
        },
    )



def quiz_page(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

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
        },
    )


@require_POST
def submit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)

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

    phone = request.POST.get("phone")
    # name in form will be "event" (see HTML fix below)
    event = request.POST.get("event")

    total = len(questions)
    score = 0
    details = []

    for q in questions:
        field_name = f"q_{q.id}"  # matches name="q_{{ q.id }}" in template
        raw_selected = request.POST.get(field_name)  # 'A'/'B'/'C'/'D' or None

        # Make comparison case-insensitive, just in case
        selected = (raw_selected or "").upper()
        correct_letter = (q.correct_option or "").upper()

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

    context = {
        "quiz": quiz,
        "phone": phone,
        "event": event,
        "score": score,
        "total": total,
        "details": details,
        "submission": submission,
        "submission_id": submission.id,
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
            
        return render(request, "quiz_result.html", {
            "quiz": submission.quiz,
            "score": submission.score,
            "total": submission.total_questions,
            "feedback_submitted": True
        })
    return HttpResponse("Invalid request")
