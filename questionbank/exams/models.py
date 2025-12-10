from django.db import models
from django.contrib.auth.models import User
from questions.models import Course, Question, QuestionBank, Tag, Week
import uuid


class ExamTemplate(models.Model):
    """Template for generating exams with saved filter settings"""
    name = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='exam_templates')
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_templates', null=True, blank=True)

    # Exam metadata
    instructor = models.CharField(max_length=200, blank=True)
    term = models.CharField(max_length=100, blank=True)  # e.g., "Fall 2024"
    school = models.CharField(max_length=200, default='Rochester Institute of Technology')
    department = models.CharField(max_length=200, default='Department of Computer Science')

    # Settings
    is_quiz = models.BooleanField(default=False)
    default_points = models.DecimalField(max_digits=5, decimal_places=2, default=2.0)
    max_points = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_mc_points = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Max points from multiple choice")
    max_tf_points = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Max points from true/false")
    max_short_points = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Max points from short answer")
    max_long_points = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Max points from long answer")
    max_questions = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum number of questions to select")
    shuffle_questions = models.BooleanField(default=True)
    shuffle_answers = models.BooleanField(default=True)

    # Display options
    use_checkboxes = models.BooleanField(default=True, help_text="Use checkboxes for multiple choice")
    include_id_field = models.BooleanField(default=True, help_text="Include student ID field")
    instructions = models.TextField(blank=True, help_text="Exam instructions/notes")

    # Default formatting
    default_solution_space = models.CharField(max_length=20, default='2.5in')
    default_line_length = models.CharField(max_length=20, default='3in')

    # Filter settings - for saved filter configurations
    filter_weeks = models.JSONField(default=list, blank=True, help_text="List of week IDs to include")
    filter_question_types = models.JSONField(default=list, blank=True, help_text="List of question types to include")
    filter_banks = models.ManyToManyField(QuestionBank, blank=True, related_name='templates')
    filter_tags = models.ManyToManyField(Tag, blank=True, related_name='templates')
    filter_difficulty = models.CharField(max_length=20, blank=True, help_text="Difficulty level filter")

    # Source INI file (for reference)
    source_file = models.CharField(max_length=500, blank=True)

    # Selection rules stored as JSON (for complex rules)
    selection_rules = models.JSONField(default=dict, help_text="Rules for question selection")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='templates_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.course.code} - {self.name}"

    def copy_to_user(self, user, new_name=None):
        """Create a complete copy of this template for another user"""
        # Create new template
        new_template = ExamTemplate.objects.create(
            name=new_name or f"{self.name} (copy)",
            course=self.course,
            description=self.description,
            owner=user,
            instructor=self.instructor,
            term=self.term,
            school=self.school,
            department=self.department,
            is_quiz=self.is_quiz,
            default_points=self.default_points,
            max_points=self.max_points,
            max_questions=self.max_questions,
            shuffle_questions=self.shuffle_questions,
            shuffle_answers=self.shuffle_answers,
            use_checkboxes=self.use_checkboxes,
            include_id_field=self.include_id_field,
            instructions=self.instructions,
            default_solution_space=self.default_solution_space,
            default_line_length=self.default_line_length,
            filter_weeks=self.filter_weeks,
            filter_question_types=self.filter_question_types,
            filter_difficulty=self.filter_difficulty,
            selection_rules=self.selection_rules,
            created_by=user
        )

        # Copy M2M relationships
        new_template.filter_banks.set(self.filter_banks.all())
        new_template.filter_tags.set(self.filter_tags.all())

        return new_template


class ExamTemplateShare(models.Model):
    """Share an exam template with another user"""
    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('edit', 'Can Edit'),
    ]
    template = models.ForeignKey(ExamTemplate, on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_templates')
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default='view')
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates_shared_by_me')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['template', 'shared_with']

    def __str__(self):
        return f"{self.template.name} shared with {self.shared_with.username}"


class GeneratedExam(models.Model):
    """A generated exam instance"""
    template = models.ForeignKey(ExamTemplate, on_delete=models.CASCADE, related_name='generated_exams')
    exam_uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    version = models.CharField(max_length=10, blank=True)  # e.g., "A", "B"

    # Snapshot of questions used
    questions = models.ManyToManyField(Question, through='ExamQuestion')

    # Generated files
    latex_file = models.FileField(upload_to='exams/latex/', null=True, blank=True)
    pdf_file = models.FileField(upload_to='exams/pdf/', null=True, blank=True)
    answer_key_pdf = models.FileField(upload_to='exams/keys/', null=True, blank=True)

    # Metadata
    total_points = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    question_count = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        version_str = f" ({self.version})" if self.version else ""
        return f"{self.template.name}{version_str} - {self.exam_uuid.hex[:8]}"


class ExamQuestion(models.Model):
    """Through table for exam-question relationship with ordering"""
    exam = models.ForeignKey(GeneratedExam, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    points_override = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ['exam', 'order']

    def __str__(self):
        return f"Q{self.order} in {self.exam}"
