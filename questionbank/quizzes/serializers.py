"""
Serializers for quiz models.
"""
from rest_framework import serializers
from .models import QuizSession, StudentSubmission, QuestionResponse, ScannedExam
from questions.serializers import QuestionListSerializer
from exams.serializers import ExamTemplateSerializer


class QuestionResponseSerializer(serializers.ModelSerializer):
    """Serializer for student's response to a question."""
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    final_score = serializers.SerializerMethodField()

    class Meta:
        model = QuestionResponse
        fields = [
            'id', 'question_number', 'question', 'question_text', 'question_type',
            'response_data', 'points_possible', 'points_earned', 'final_score',
            'grading_status', 'is_correct',
            'ai_score', 'ai_feedback', 'ai_reasoning', 'ai_confidence', 'ai_graded_at',
            'override_score', 'override_feedback', 'override_by', 'override_at',
            'answered_at'
        ]
        read_only_fields = [
            'id', 'question_text', 'question_type', 'final_score',
            'ai_score', 'ai_feedback', 'ai_reasoning', 'ai_confidence', 'ai_graded_at',
            'override_score', 'override_feedback', 'override_by', 'override_at'
        ]

    def get_final_score(self, obj):
        return float(obj.get_final_score()) if obj.get_final_score() is not None else None


class StudentSubmissionListSerializer(serializers.ModelSerializer):
    """List serializer for submissions (minimal data)."""
    quiz_name = serializers.CharField(source='quiz_session.name', read_only=True)

    class Meta:
        model = StudentSubmission
        fields = [
            'id', 'quiz_session', 'quiz_name',
            'student_name', 'student_id', 'student_email',
            'status', 'total_points_possible', 'total_points_earned', 'percentage_score',
            'started_at', 'submitted_at', 'auto_submitted', 'is_late'
        ]


class StudentSubmissionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single submission with responses."""
    quiz_name = serializers.CharField(source='quiz_session.name', read_only=True)
    responses = QuestionResponseSerializer(many=True, read_only=True)

    class Meta:
        model = StudentSubmission
        fields = [
            'id', 'quiz_session', 'quiz_name',
            'student_name', 'student_id', 'student_email',
            'status', 'total_points_possible', 'total_points_earned', 'percentage_score',
            'started_at', 'expires_at', 'submitted_at', 'time_spent_seconds',
            'auto_submitted', 'is_late', 'late_penalty_applied',
            'attempt_number', 'question_order', 'responses'
        ]


class QuizSessionListSerializer(serializers.ModelSerializer):
    """List serializer for quiz sessions."""
    template_name = serializers.CharField(source='template.name', read_only=True)
    course_code = serializers.CharField(source='template.course.code', read_only=True)
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = QuizSession
        fields = [
            'id', 'access_code', 'name', 'description',
            'template', 'template_name', 'course_code',
            'status', 'time_limit_minutes',
            'start_time', 'end_time',
            'shuffle_questions', 'ai_grading_enabled',
            'submission_count', 'created_at'
        ]

    def get_submission_count(self, obj):
        return obj.submissions.count()


class QuizSessionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for quiz session."""
    template_name = serializers.CharField(source='template.name', read_only=True)
    course_code = serializers.CharField(source='template.course.code', read_only=True)
    questions_data = QuestionListSerializer(source='questions', many=True, read_only=True)
    submission_count = serializers.SerializerMethodField()
    graded_count = serializers.SerializerMethodField()

    class Meta:
        model = QuizSession
        fields = [
            'id', 'access_code', 'name', 'description', 'instructions',
            'template', 'template_name', 'course_code', 'generated_exam',
            'status', 'time_limit_minutes',
            'start_time', 'end_time',
            'require_student_id', 'allow_late_submissions', 'late_penalty_percent',
            'max_attempts',
            'shuffle_questions', 'shuffle_answers',
            'show_correct_answers', 'show_score_immediately',
            'ai_grading_enabled', 'ai_grading_provider',
            'questions', 'questions_data',
            'submission_count', 'graded_count',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'access_code', 'created_at', 'updated_at']

    def get_submission_count(self, obj):
        return obj.submissions.count()

    def get_graded_count(self, obj):
        return obj.submissions.filter(status__in=['graded', 'reviewed']).count()


class QuizSessionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a quiz session."""

    class Meta:
        model = QuizSession
        fields = [
            'name', 'description', 'instructions',
            'template', 'generated_exam',
            'time_limit_minutes', 'start_time', 'end_time',
            'require_student_id', 'allow_late_submissions', 'late_penalty_percent',
            'max_attempts',
            'shuffle_questions', 'shuffle_answers',
            'show_correct_answers', 'show_score_immediately',
            'ai_grading_enabled', 'ai_grading_provider',
            'questions'
        ]

    def create(self, validated_data):
        questions = validated_data.pop('questions', [])
        validated_data['created_by'] = self.context['request'].user
        quiz = QuizSession.objects.create(**validated_data)

        if questions:
            quiz.questions.set(questions)
        elif quiz.template:
            # Auto-populate questions from template sections
            self._populate_questions_from_template(quiz)

        return quiz

    def _populate_questions_from_template(self, quiz):
        """Pull questions from the template's selection rules (sections)."""
        from questions.models import Question
        from django.db.models import Q
        import random

        template = quiz.template
        selection_rules = template.selection_rules

        if not selection_rules:
            # Fall back to filter_banks if no sections defined
            if template.filter_banks.exists():
                questions = Question.objects.filter(
                    question_bank__in=template.filter_banks.all(),
                    deleted_at__isnull=True
                )
                quiz.questions.set(questions[:100])  # Limit to 100
            return

        # Handle case where selection_rules is not a list of dicts
        # (e.g., it might be a dict or have unexpected format)
        if not isinstance(selection_rules, list):
            # Fall back to filter_banks
            if template.filter_banks.exists():
                questions = Question.objects.filter(
                    question_bank__in=template.filter_banks.all(),
                    deleted_at__isnull=True
                )
                quiz.questions.set(questions[:100])
            return

        # Process each section in selection_rules
        all_questions = []

        for section in selection_rules:
            # Skip non-dict entries (strings, etc.)
            if not isinstance(section, dict):
                continue
            section_questions = self._get_section_questions(template, section)

            # Apply count limit if specified
            count = section.get('count') or section.get('questionCount')
            if count and count < len(section_questions):
                section_questions = random.sample(section_questions, count)

            all_questions.extend(section_questions)

        # If we got questions from sections, use them; otherwise fall back to filter_banks or course
        if all_questions:
            quiz.questions.set(all_questions)
        elif template.filter_banks.exists():
            questions = Question.objects.filter(
                question_bank__in=template.filter_banks.all(),
                deleted_at__isnull=True
            )
            quiz.questions.set(questions[:100])
        elif template.course:
            # Fall back to all questions from the template's course
            questions = Question.objects.filter(
                question_bank__course=template.course,
                deleted_at__isnull=True
            ).filter(
                Q(block__isnull=True) | Q(variant_number=1)
            )
            quiz.questions.set(questions[:100])

    def _get_section_questions(self, template, section):
        """Get questions matching section criteria."""
        from questions.models import Question
        from django.db.models import Q

        # Start with base queryset
        queryset = Question.objects.filter(deleted_at__isnull=True)

        # Filter by course
        course = section.get('course') or (template.course.code if template.course else None)
        if course:
            queryset = queryset.filter(question_bank__course__code=course)

        # Filter by bank
        bank_id = section.get('bank')
        if bank_id:
            queryset = queryset.filter(question_bank_id=bank_id)
        elif template.filter_banks.exists():
            queryset = queryset.filter(question_bank__in=template.filter_banks.all())

        # Filter by tags
        tags = section.get('tags', [])
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__name=tag)

        # Filter by question type
        question_type = section.get('type') or section.get('questionType')
        if question_type:
            queryset = queryset.filter(question_type=question_type)

        # Filter by difficulty
        difficulty = section.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)

        # Only get first variant from blocks
        queryset = queryset.filter(
            Q(block__isnull=True) | Q(variant_number=1)
        )

        return list(queryset.distinct())


# Public serializers (for student quiz taking - no auth)

class QuizInfoSerializer(serializers.ModelSerializer):
    """Public serializer for quiz info (before starting)."""
    course_name = serializers.CharField(source='template.course.name', read_only=True)

    class Meta:
        model = QuizSession
        fields = [
            'name', 'description', 'instructions',
            'course_name', 'time_limit_minutes',
            'require_student_id', 'max_attempts'
        ]


class QuizQuestionSerializer(serializers.ModelSerializer):
    """Serializer for quiz questions (shown to students)."""
    from questions.models import Question

    class Meta:
        from questions.models import Question
        model = Question
        fields = ['id', 'question_type', 'text', 'points', 'answer_data']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Remove correct answers from answer_data for students
        answer_data = data.get('answer_data', {})
        if instance.question_type == 'multipleChoice':
            # Only show choices, not which is correct
            choices = [answer_data.get('correct', '')] + answer_data.get('wrong', [])
            import random
            if self.context.get('shuffle_answers', True):
                random.shuffle(choices)
            data['answer_data'] = {'choices': choices}
        elif instance.question_type == 'trueFalse':
            data['answer_data'] = {'choices': ['True', 'False']}
        else:
            # Short/long answer - no answer data needed
            data['answer_data'] = {}
        return data


class ScannedExamSerializer(serializers.ModelSerializer):
    """Serializer for scanned exams."""
    template_name = serializers.CharField(source='template.name', read_only=True)

    class Meta:
        model = ScannedExam
        fields = [
            'id', 'quiz_session', 'template', 'template_name', 'generated_exam',
            'pdf_file', 'page_count',
            'student_name', 'student_id',
            'status', 'error_message',
            'ocr_text', 'ocr_confidence', 'extracted_answers',
            'submission',
            'uploaded_by', 'uploaded_at', 'processed_at'
        ]
        read_only_fields = [
            'id', 'page_count', 'status', 'error_message',
            'ocr_text', 'ocr_confidence', 'extracted_answers',
            'submission', 'uploaded_at', 'processed_at'
        ]
