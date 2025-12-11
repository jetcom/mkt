from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GenerateExamView, ExamPreviewView, MultiVersionPreviewView, ExamTemplateViewSet, GeneratedExamViewSet

router = DefaultRouter()
router.register(r'templates', ExamTemplateViewSet, basename='exam-templates')
router.register(r'history', GeneratedExamViewSet, basename='exam-history')

urlpatterns = [
    path('generate/', GenerateExamView.as_view(), name='exam-generate'),
    path('preview/', ExamPreviewView.as_view(), name='exam-preview'),
    path('preview/versions/', MultiVersionPreviewView.as_view(), name='exam-preview-versions'),
    path('', include(router.urls)),
]
