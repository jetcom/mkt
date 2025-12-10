from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TagViewSet, CourseViewSet, QuestionBankViewSet, QuestionBlockViewSet, QuestionViewSet, WeekViewSet, UserViewSet, ImageUploadViewSet

router = DefaultRouter()
router.register(r'tags', TagViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'weeks', WeekViewSet)
router.register(r'banks', QuestionBankViewSet)
router.register(r'blocks', QuestionBlockViewSet)
router.register(r'questions', QuestionViewSet)
router.register(r'users', UserViewSet)
router.register(r'images', ImageUploadViewSet, basename='images')

urlpatterns = [
    path('', include(router.urls)),
]
