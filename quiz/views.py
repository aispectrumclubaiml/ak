from django.shortcuts import render, HttpResponse
from django.urls import reverse
import random
from django.shortcuts import render, get_object_or_404
from .models import Quiz, Question, Submission, Answer
from django.views.decorators.http import require_POST


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
        event_code = request.POST.get("event")   # "3" or "2"
        phone = request.POST.get("phone", "").strip()

        if not event_code or not phone:
            return render(
                request,
                "prelims_landing.html",
                {
                    "step": 1,
                    "error": "Please select an event and enter phone number.",
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
                },
            )

        # Look up event display name from the selected code
        event_info = EVENT_CONFIG.get(event_code)
        event_name = event_info["name"] if event_info else f"Event {event_code}"

        team_data = {
            "team_name": f"Team-{phone[-4:]}",
            "event_display": event_name,
            "members": [],
        }

        return render(
            request,
            "prelims_landing.html",
            {
                "step": 2,
                "phone": phone,
                "event_code": event_code,  # this is also the quiz_id
                "team": team_data,
            },
        )

    return render(
        request,
        "prelims_landing.html",
        {
            "step": 1,
        },
    )


def quiz_page(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    all_questions = list(quiz.questions.all())
    num = min(quiz.num_questions, len(all_questions))
    chosen_questions = random.sample(all_questions, num) if num > 0 else []

    question_data = []
    for q in chosen_questions:
        options = [
            ('A', q.option_a),
            ('B', q.option_b),
            ('C', q.option_c),
            ('D', q.option_d),
        ]
        random.shuffle(options)
        question_data.append({
            "obj": q,
            "options": options,
        })

    return render(request, "quiz.html", {
        "quiz": quiz,
        "questions": question_data,
        "duration_seconds": quiz.duration_minutes * 60,
    })


@require_POST
def submit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    questions = quiz.questions.all()[: quiz.num_questions]

    phone = request.POST.get("phone")
    event = request.POST.get("event")

    total = questions.count()
    score = 0
    details = []

    for q in questions:
        field_name = f"q_{q.id}"        # matches name="q_{{ q.id }}" in template
        selected = request.POST.get(field_name)  # 'A'/'B'/'C'/'D' or None

        is_correct = (selected == q.correct_option)
        if is_correct:
            score += 1

        option_map = {
            "A": q.option_a,
            "B": q.option_b,
            "C": q.option_c,
            "D": q.option_d,
        }

        details.append({
            "question": q,
            "selected_letter": selected,
            "selected_text": option_map.get(selected) if selected else None,
            "correct_letter": q.correct_option,
            "correct_text": option_map.get(q.correct_option),
            "is_correct": is_correct,
        })

    # 🔴 Save submission in DB
    submission = Submission.objects.create(
        quiz=quiz,
        phone=phone or "",
        event=event or "",
        score=score,
        total_questions=total,
    )

    # 🔴 Save each answer
    answer_objs = []
    for item in details:
        answer_objs.append(Answer(
            submission=submission,
            question=item["question"],
            selected_option=item["selected_letter"],
            correct_option=item["correct_letter"],
            is_correct=item["is_correct"],
        ))
    Answer.objects.bulk_create(answer_objs)

    context = {
        "quiz": quiz,
        "phone": phone,
        "event": event,
        "score": score,
        "total": total,
        "details": details,
        "submission": submission,
    }
    return render(request, "quiz_result.html", context)