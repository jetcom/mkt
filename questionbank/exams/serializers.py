from rest_framework import serializers
from .models import ExamTemplate, GeneratedExam, ExamQuestion, ExamTemplateShare
from questions.models import Tag, QuestionBank


class ExamTemplateSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True, allow_null=True)
    is_owner = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()
    # Allow writing to ManyToMany fields
    filter_bank_ids = serializers.PrimaryKeyRelatedField(
        queryset=QuestionBank.objects.all(), many=True, write_only=True,
        source='filter_banks', required=False
    )
    filter_tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, write_only=True,
        source='filter_tags', required=False
    )
    # Read-only nested data
    filter_banks_data = serializers.SerializerMethodField()
    filter_tags_data = serializers.SerializerMethodField()

    class Meta:
        model = ExamTemplate
        fields = [
            'id', 'name', 'course', 'course_code', 'course_name', 'description',
            'owner', 'owner_username', 'is_owner', 'is_shared',
            'instructor', 'term', 'school', 'department',
            'is_quiz', 'default_points', 'max_points', 'max_mc_points', 'max_tf_points', 'max_short_points', 'max_long_points', 'max_questions',
            'shuffle_questions', 'shuffle_answers',
            'use_checkboxes', 'include_id_field', 'instructions',
            'default_solution_space', 'default_line_length',
            # Filter fields
            'filter_weeks', 'filter_question_types', 'filter_difficulty',
            'filter_banks', 'filter_bank_ids', 'filter_banks_data',
            'filter_tags', 'filter_tag_ids', 'filter_tags_data',
            'source_file', 'selection_rules',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['filter_banks_data', 'filter_tags_data', 'owner']

    def get_filter_banks_data(self, obj):
        return [{'id': b.id, 'name': b.name} for b in obj.filter_banks.all()]

    def get_filter_tags_data(self, obj):
        return [{'id': t.id, 'name': t.name, 'color': t.color} for t in obj.filter_tags.all()]

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.owner == request.user
        return False

    def get_is_shared(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.owner != request.user:
            return obj.shares.filter(shared_with=request.user).exists()
        return False


class ExamTemplateShareSerializer(serializers.ModelSerializer):
    shared_with_username = serializers.CharField(source='shared_with.username', read_only=True)
    shared_by_username = serializers.CharField(source='shared_by.username', read_only=True)

    class Meta:
        model = ExamTemplateShare
        fields = ['id', 'template', 'shared_with', 'shared_with_username', 'shared_by', 'shared_by_username', 'permission', 'created_at']
        read_only_fields = ['shared_by']


class ExamTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    course_code = serializers.CharField(source='course.code', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True, allow_null=True)
    is_owner = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()
    filter_count = serializers.SerializerMethodField()

    class Meta:
        model = ExamTemplate
        fields = [
            'id', 'name', 'course', 'course_code', 'term', 'is_quiz',
            'owner', 'owner_username', 'is_owner', 'is_shared',
            'instructor', 'default_points', 'max_points', 'max_questions',
            'filter_count', 'updated_at'
        ]

    def get_filter_count(self, obj):
        """Count active filters"""
        count = 0
        if obj.filter_weeks:
            count += 1
        if obj.filter_question_types:
            count += 1
        if obj.filter_difficulty:
            count += 1
        if obj.filter_banks.exists():
            count += 1
        if obj.filter_tags.exists():
            count += 1
        return count

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.owner == request.user
        return False

    def get_is_shared(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.owner != request.user:
            return obj.shares.filter(shared_with=request.user).exists()
        return False


class GeneratedExamSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    course_code = serializers.CharField(source='template.course.code', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = GeneratedExam
        fields = [
            'id', 'template', 'template_name', 'course_code', 'exam_uuid', 'version',
            'total_points', 'question_count', 'created_by', 'created_by_username', 'created_at'
        ]


class GeneratedExamDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer including question list"""
    template_name = serializers.CharField(source='template.name', read_only=True)
    course_code = serializers.CharField(source='template.course.code', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    questions_data = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedExam
        fields = [
            'id', 'template', 'template_name', 'course_code', 'exam_uuid', 'version',
            'total_points', 'question_count', 'created_by', 'created_by_username', 'created_at',
            'questions_data'
        ]

    def get_questions_data(self, obj):
        """Get simplified question data for history view"""
        exam_questions = obj.examquestion_set.select_related('question').all()
        return [{
            'order': eq.order,
            'id': eq.question.id,
            'type': eq.question.question_type,
            'text': eq.question.text[:100] + '...' if len(eq.question.text) > 100 else eq.question.text,
            'points': float(eq.points_override or eq.question.points)
        } for eq in exam_questions]
