"""
URL routing for quizzes app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'sessions', views.QuizSessionViewSet, basename='quiz-sessions')
router.register(r'submissions', views.StudentSubmissionViewSet, basename='submissions')
router.register(r'responses', views.QuestionResponseViewSet, basename='responses')
router.register(r'scanned', views.ScannedExamViewSet, basename='scanned-exams')
router.register(r'invitations', views.QuizInvitationViewSet, basename='invitations')

urlpatterns = [
    # Instructor API endpoints (auth required)
    path('', include(router.urls)),
    path('grade/ai/<uuid:response_id>/', views.AIGradeView.as_view(), name='ai-grade'),
    path('grade/override/<uuid:response_id>/', views.GradeOverrideView.as_view(), name='grade-override'),
    path('grade/batch/', views.BatchGradeView.as_view(), name='batch-grade'),

    # Scanned exam upload
    path('scan/upload/', views.ScannedExamUploadView.as_view(), name='scan-upload'),

    # Roster and invitations
    path('sessions/<uuid:quiz_id>/roster/import/', views.RosterImportView.as_view(), name='roster-import'),
    path('sessions/<uuid:quiz_id>/invitations/send/', views.SendInvitationsView.as_view(), name='send-invitations'),

    # Public student API endpoints (no auth required)
    path('take/<str:code>/', views.QuizAccessView.as_view(), name='quiz-access'),
    path('take/<str:code>/start/', views.QuizStartView.as_view(), name='quiz-start'),
    path('take/<str:code>/questions/', views.QuizQuestionsView.as_view(), name='quiz-questions'),
    path('take/<str:code>/answer/', views.QuizAnswerView.as_view(), name='quiz-answer'),
    path('take/<str:code>/submit/', views.QuizSubmitView.as_view(), name='quiz-submit'),
    path('take/<str:code>/results/', views.QuizResultsView.as_view(), name='quiz-results'),
]

# HTML page URLs (for quiz taking interface)
html_urlpatterns = [
    path('quiz/<str:code>/', views.quiz_take_page, name='quiz-take-page'),
    path('quiz/preview/<uuid:quiz_id>/', views.quiz_preview_page, name='quiz-preview-page'),
]
