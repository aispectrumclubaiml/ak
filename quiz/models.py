from django.db import models
from ckeditor.fields import RichTextField


class Quiz(models.Model):
    name = models.CharField(max_length=100)
    duration_minutes = models.IntegerField(default=30)
    num_questions = models.IntegerField(default=20)

    def __str__(self):
        return self.name


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    # text_html = models.TextField()
    text_html = RichTextField()
    image = models.ImageField(upload_to='quiz_images/', blank=True, null=True)

    option_a = models.TextField()
    option_b = models.TextField()
    option_c = models.TextField()
    option_d = models.TextField()
    correct_option = models.CharField(max_length=1)  # 'A','B','C','D'

    def __str__(self):
        return f"{self.quiz.name} – Q{self.id}"


class Submission(models.Model):
    """
    One row = one attempt of a quiz by a team (phone+event).
    """
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="submissions")
    phone = models.CharField(max_length=20)
    event = models.CharField(max_length=50, blank=True, null=True)

    score = models.IntegerField()
    total_questions = models.IntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quiz.name} – {self.phone} – {self.score}/{self.total_questions}"


class Answer(models.Model):
    """
    One row per question answered in a submission.
    """
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    selected_option = models.CharField(max_length=1, blank=True, null=True)  # 'A','B','C','D' or None
    correct_option = models.CharField(max_length=1)  # copy from Question.correct_option
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"Submission {self.submission_id} – Q{self.question_id}"
