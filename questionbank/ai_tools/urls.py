from django.urls import path
from .views import GenerateQuestionsView, ImproveQuestionView, ValidateQuestionView, GenerateVariantView, ExtractFileContentView

urlpatterns = [
    path('generate/', GenerateQuestionsView.as_view(), name='ai-generate'),
    path('generate-variant/', GenerateVariantView.as_view(), name='ai-generate-variant'),
    path('improve/', ImproveQuestionView.as_view(), name='ai-improve'),
    path('validate/', ValidateQuestionView.as_view(), name='ai-validate'),
    path('extract-file/', ExtractFileContentView.as_view(), name='ai-extract-file'),
]
