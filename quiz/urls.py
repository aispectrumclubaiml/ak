from django.urls import path
from . import views

urlpatterns = [
    path('', views.prelims_entry, name='prelims_entry'),
    path('quiz/<int:quiz_id>/', views.quiz_page, name='quiz'),
    path("quiz/<int:quiz_id>/submit/", views.submit_quiz, name="submit_quiz"),
    path("submit/feedback/", views.submit_feedback, name="submit_feedback"),
     
    # path('login/', views.user_login, name='login'),
    # path('quiz/<int:quiz_id>/', views.quiz_page, name='quiz'),
    # path('submit/<int:quiz_id>/', views.submit_quiz, name='submit'),
]
