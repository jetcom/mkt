from django.contrib import admin
from .models import Tag, Course, QuestionBank, Question, QuestionVersion, Week


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    search_fields = ['name']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'created_at']
    search_fields = ['code', 'name']


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'created_at']
    list_filter = ['course']
    search_fields = ['name']


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = ['course', 'number', 'name', 'question_count', 'created_at']
    list_filter = ['course']
    search_fields = ['name', 'description']
    ordering = ['course', 'number']

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'question_type', 'short_text', 'points', 'difficulty', 'question_bank', 'week', 'times_used']
    list_filter = ['question_type', 'difficulty', 'question_bank__course', 'week']
    search_fields = ['text']
    filter_horizontal = ['tags']
    raw_id_fields = ['week']

    def short_text(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    short_text.short_description = 'Question'


@admin.register(QuestionVersion)
class QuestionVersionAdmin(admin.ModelAdmin):
    list_display = ['question', 'version_number', 'created_at']
    list_filter = ['created_at']
