"""
Quiz delivery and AI grading models.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from exams.models import ExamTemplate, GeneratedExam
from questions.models import Question
import uuid
import secrets
import string


def generate_access_code():
    """Generate a 6-character alphanumeric access code."""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))


class QuizSession(models.Model):
    """A live quiz instance that students can take."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        CLOSED = 'closed', 'Closed'
        ARCHIVED = 'archived', 'Archived'

    # Core identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_code = models.CharField(max_length=10, unique=True, default=generate_access_code, db_index=True)

    # Link to exam definition
    template = models.ForeignKey(ExamTemplate, on_delete=models.CASCADE, related_name='quiz_sessions', null=True, blank=True)
    generated_exam = models.ForeignKey(GeneratedExam, on_delete=models.SET_NULL, null=True, blank=True,
                                       help_text="Specific generated exam if using pre-selected questions")

    # Quiz metadata
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True, help_text="Instructions shown to students before starting")

    # Timing settings
    time_limit_minutes = models.PositiveIntegerField(default=60, help_text="Time limit in minutes")
    start_time = models.DateTimeField(null=True, blank=True, help_text="When quiz becomes available")
    end_time = models.DateTimeField(null=True, blank=True, help_text="When quiz closes")

    # Access control
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    require_student_id = models.BooleanField(default=True)
    allow_late_submissions = models.BooleanField(default=False)
    late_penalty_percent = models.PositiveIntegerField(default=0, help_text="Penalty percentage per minute late")
    max_attempts = models.PositiveIntegerField(default=1)

    # Display settings
    shuffle_questions = models.BooleanField(default=True)
    shuffle_answers = models.BooleanField(default=True)
    show_correct_answers = models.BooleanField(default=False, help_text="Show correct answers after submission")
    show_score_immediately = models.BooleanField(default=True)

    # Grading settings
    ai_grading_enabled = models.BooleanField(default=True)
    ai_grading_provider = models.CharField(max_length=20, default='claude', choices=[
        ('claude', 'Claude (Anthropic)'),
        ('openai', 'GPT-4 (OpenAI)'),
    ])

    # Questions for this quiz (can be set manually or pulled from template)
    questions = models.ManyToManyField(Question, blank=True, related_name='quiz_sessions')

    # Audit fields
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_quizzes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Quiz Sessions'

    def __str__(self):
        return f"{self.name} ({self.access_code})"

    def is_available(self):
        """Check if quiz is currently available to take."""
        now = timezone.now()
        if self.status != self.Status.ACTIVE:
            return False
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True

    def regenerate_code(self):
        """Generate a new access code."""
        self.access_code = generate_access_code()
        self.save(update_fields=['access_code'])
        return self.access_code


class StudentSubmission(models.Model):
    """A student's submission for a quiz session."""

    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In Progress'
        SUBMITTED = 'submitted', 'Submitted'
        GRADING = 'grading', 'Being Graded'
        GRADED = 'graded', 'Graded'
        REVIEWED = 'reviewed', 'Reviewed by Instructor'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz_session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name='submissions')

    # Student identification (no login required)
    student_name = models.CharField(max_length=200)
    student_id = models.CharField(max_length=50, blank=True, db_index=True)
    student_email = models.EmailField(blank=True)

    # Session tracking
    session_token = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When the timer runs out")
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    auto_submitted = models.BooleanField(default=False, help_text="True if timer ran out")

    # Scoring
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    total_points_possible = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_points_earned = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    percentage_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Late submission tracking
    is_late = models.BooleanField(default=False)
    late_penalty_applied = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Attempt tracking
    attempt_number = models.PositiveIntegerField(default=1)

    # Question order (JSON list of question IDs in the order shown)
    question_order = models.JSONField(default=list)

    class Meta:
        ordering = ['-submitted_at', '-started_at']

    def __str__(self):
        return f"{self.student_name} - {self.quiz_session.name}"

    def save(self, *args, **kwargs):
        if not self.session_token:
            self.session_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def calculate_score(self):
        """Recalculate total score from all responses."""
        responses = self.responses.all()
        self.total_points_possible = sum(r.points_possible for r in responses)
        self.total_points_earned = sum(r.get_final_score() or 0 for r in responses)
        if self.total_points_possible > 0:
            self.percentage_score = (self.total_points_earned / self.total_points_possible) * 100
        self.save(update_fields=['total_points_possible', 'total_points_earned', 'percentage_score'])


class QuestionResponse(models.Model):
    """A student's response to a single question."""

    class GradingStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        AUTO_GRADED = 'auto_graded', 'Auto-Graded'
        AI_GRADED = 'ai_graded', 'AI-Graded'
        MANUAL = 'manual', 'Manually Graded'
        OVERRIDDEN = 'overridden', 'Instructor Override'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(StudentSubmission, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='quiz_responses')

    # The question order in this student's quiz (for display)
    question_number = models.PositiveIntegerField()

    # Student's answer - stored as JSON for flexibility
    # For MC: {"selected": "The answer text"}
    # For TF: {"selected": true/false}
    # For Short/Long: {"text": "student answer"}
    response_data = models.JSONField(default=dict)

    # Points
    points_possible = models.DecimalField(max_digits=5, decimal_places=2)
    points_earned = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Grading metadata
    grading_status = models.CharField(max_length=20, choices=GradingStatus.choices, default=GradingStatus.PENDING)
    is_correct = models.BooleanField(null=True, blank=True)  # For objective questions

    # AI grading details
    ai_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ai_feedback = models.TextField(blank=True, help_text="AI-generated feedback for the student")
    ai_reasoning = models.TextField(blank=True, help_text="AI's reasoning (for instructor review)")
    ai_confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True,
                                        help_text="AI confidence score 0-1")
    ai_graded_at = models.DateTimeField(null=True, blank=True)
    ai_model_used = models.CharField(max_length=50, blank=True)

    # Instructor override
    override_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    override_feedback = models.TextField(blank=True)
    override_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='grade_overrides')
    override_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    answered_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['question_number']
        unique_together = ['submission', 'question']

    def __str__(self):
        return f"Q{self.question_number}: {self.submission.student_name}"

    def get_final_score(self):
        """Return the final score (override if present, otherwise AI/auto score)."""
        if self.override_score is not None:
            return self.override_score
        return self.points_earned


class ScannedExam(models.Model):
    """A scanned paper exam uploaded for OCR processing."""

    class Status(models.TextChoices):
        UPLOADED = 'uploaded', 'Uploaded'
        PROCESSING = 'processing', 'Processing OCR'
        EXTRACTED = 'extracted', 'Text Extracted'
        MATCHED = 'matched', 'Questions Matched'
        GRADING = 'grading', 'Being Graded'
        GRADED = 'graded', 'Graded'
        ERROR = 'error', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to exam
    quiz_session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name='scanned_exams',
                                     null=True, blank=True)
    template = models.ForeignKey(ExamTemplate, on_delete=models.CASCADE, related_name='scanned_exams')
    generated_exam = models.ForeignKey(GeneratedExam, on_delete=models.SET_NULL, null=True, blank=True)

    # File
    pdf_file = models.FileField(upload_to='scanned_exams/')
    page_count = models.PositiveIntegerField(default=0)

    # Student info (extracted or entered)
    student_name = models.CharField(max_length=200, blank=True)
    student_id = models.CharField(max_length=50, blank=True)

    # Processing status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    error_message = models.TextField(blank=True)

    # OCR results (JSON with page-by-page text)
    ocr_text = models.JSONField(default=dict)
    ocr_confidence = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    # Extracted answers (JSON mapping question_number -> extracted_text)
    extracted_answers = models.JSONField(default=dict)

    # Link to submission created from this scan
    submission = models.OneToOneField(StudentSubmission, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='scanned_exam')

    # Audit
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Scan: {self.student_name or 'Unknown'} - {self.template.name}"
