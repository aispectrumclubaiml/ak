from django.contrib import admin
from .models import Quiz, Question, Submission, Answer, Feedback
from django.utils.html import strip_tags


admin.site.site_header = "AI KSHETRA Administration"
admin.site.site_title = "AI KSHETRA Admin Portal"
admin.site.index_title = "Welcome to AI KSHETRA Prelims Admin"


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0


from django.contrib import admin
from django.http import HttpResponse
import csv

from .models import Quiz, Question, Submission, Answer


# Optional small helper for stripping HTML if you want cleaner CSV
from django.utils.html import strip_tags


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "duration_minutes", "num_questions")
    actions = ["export_as_csv"]

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="quizzes.csv"'

        writer = csv.writer(response)
        writer.writerow(["ID", "Name", "Duration (min)", "Num Questions"])

        for quiz in queryset:
            writer.writerow([
                quiz.id,
                quiz.name,
                quiz.duration_minutes,
                quiz.num_questions,
            ])

        return response

    export_as_csv.short_description = "Download selected quizzes as CSV"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz", "short_text", "correct_option")
    list_filter = ("quiz",)
    actions = ["export_as_csv"]

    def short_text(self, obj):
        # first 80 chars, HTML stripped
        return strip_tags(obj.text_html)[:80]

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="questions.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "ID",
            "Quiz ID",
            "Quiz Name",
            "Text (stripped)",
            "Image",
            "Option A",
            "Option B",
            "Option C",
            "Option D",
            "Correct Option",
        ])

        for q in queryset:
            writer.writerow([
                q.id,
                q.quiz_id,
                q.quiz.name,
                strip_tags(q.text_html),
                q.image.url if q.image else "",
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_option,
            ])

        return response

    export_as_csv.short_description = "Download selected questions as CSV"


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "quiz", "phone", "event", "score", "total_questions", "time_taken_seconds", "submitted_at")
    list_filter = ("quiz", "event")
    search_fields = ("phone",)
    actions = ["export_as_csv"]

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="submissions.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "ID",
            "Quiz ID",
            "Quiz Name",
            "Phone",
            "Event",
            "Score",
            "Total Questions",
            "Time Taken (s)",
            "Submitted At",
        ])

        for s in queryset:
            writer.writerow([
                s.id,
                s.quiz_id,
                s.quiz.name,
                s.phone,
                s.event,
                s.score,
                s.total_questions,
                s.time_taken_seconds,
                s.submitted_at,
            ])

        return response

    export_as_csv.short_description = "Download selected submissions as CSV"


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "question", "selected_option", "correct_option", "is_correct")
    list_filter = ("submission__quiz", "is_correct")
    search_fields = ("submission__phone",)
    actions = ["export_as_csv"]

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="answers.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "ID",
            "Submission ID",
            "Quiz ID",
            "Quiz Name",
            "Phone",
            "Question ID",
            "Question Text (stripped)",
            "Selected Option",
            "Correct Option",
            "Is Correct",
        ])

        for a in queryset.select_related("submission", "question", "submission__quiz"):
            writer.writerow([
                a.id,
                a.submission_id,
                a.submission.quiz_id,
                a.submission.quiz.name,
                a.submission.phone,
                a.question_id,
                strip_tags(a.question.text_html),
                a.selected_option or "",
                a.correct_option,
                a.is_correct,
            ])

        return response

    export_as_csv.short_description = "Download selected answers as CSV"


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "rating", "rating_ui", "rating_difficulty", "rating_relevance", "created_at")
    list_filter = ("rating", "rating_ui", "rating_difficulty", "rating_relevance", "created_at")
    search_fields = ("submission__phone", "comments")
    actions = ["export_as_csv"]

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="feedback.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "ID",
            "Submission ID",
            "Phone",
            "Event",
            "Overall Rating",
            "UI/UX Rating",
            "Difficulty Rating",
            "Relevance Rating",
            "Comments",
            "Created At"
        ])

        for f in queryset.select_related("submission"):
            writer.writerow([
                f.id,
                f.submission.id,
                f.submission.phone,
                f.submission.event,
                f.rating,
                f.rating_ui,
                f.rating_difficulty,
                f.rating_relevance,
                f.comments,
                f.created_at,
            ])
        return response

    export_as_csv.short_description = "Download selected feedback as CSV"
