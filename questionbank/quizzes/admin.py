from django.contrib import admin
from .models import QuizSession, StudentSubmission, QuestionResponse, ScannedExam


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'access_code', 'template', 'status', 'time_limit_minutes', 'created_at']
    list_filter = ['status', 'ai_grading_enabled', 'created_at']
    search_fields = ['name', 'access_code', 'template__name']
    readonly_fields = ['id', 'access_code', 'created_at', 'updated_at']
    filter_horizontal = ['questions']


@admin.register(StudentSubmission)
class StudentSubmissionAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'student_id', 'quiz_session', 'status', 'percentage_score', 'submitted_at']
    list_filter = ['status', 'is_late', 'auto_submitted']
    search_fields = ['student_name', 'student_id', 'student_email']
    readonly_fields = ['id', 'session_token', 'started_at']


@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = ['submission', 'question_number', 'grading_status', 'points_earned', 'points_possible', 'is_correct']
    list_filter = ['grading_status', 'is_correct']
    search_fields = ['submission__student_name']
    readonly_fields = ['id']


@admin.register(ScannedExam)
class ScannedExamAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'student_id', 'template', 'status', 'uploaded_at']
    list_filter = ['status']
    search_fields = ['student_name', 'student_id']
    readonly_fields = ['id', 'uploaded_at', 'processed_at']
