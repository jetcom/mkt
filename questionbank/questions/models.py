from django.db import models
from django.contrib.auth.models import User
import hashlib


class Tag(models.Model):
    """Tags for categorizing questions"""
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#6366f1')  # Hex color

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Course(models.Model):
    """Course/subject for organizing questions"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)  # e.g., "CSCI320"
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_courses', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class CourseShare(models.Model):
    """Share a course with another user"""
    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('edit', 'Can Edit'),
    ]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_courses')
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default='view')
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_shared_by_me')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['course', 'shared_with']

    def __str__(self):
        return f"{self.course.code} shared with {self.shared_with.username}"


class Week(models.Model):
    """Week/module organization for questions within a course"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='weeks')
    number = models.PositiveIntegerField(help_text="Week number (1, 2, 3...)")
    name = models.CharField(max_length=100, blank=True, help_text="Custom name like 'Week 1' or 'Introduction'")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course', 'number']
        unique_together = ['course', 'number']

    def __str__(self):
        if self.name:
            return f"{self.course.code} - {self.name}"
        return f"{self.course.code} - Week {self.number}"


class QuestionBank(models.Model):
    """Collection of questions (like a folder/file)"""
    name = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='question_banks')
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_banks', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course', 'name']
        unique_together = ['course', 'name']

    def __str__(self):
        return f"{self.course.code}/{self.name}"

    def copy_to_user(self, user, new_name=None):
        """Create a complete copy of this bank with all questions for another user"""
        from django.utils import timezone

        # Create new bank
        new_bank = QuestionBank.objects.create(
            name=new_name or f"{self.name} (copy)",
            course=self.course,
            description=self.description,
            owner=user
        )

        # Copy all questions
        for question in self.questions.all():
            Question.objects.create(
                question_bank=new_bank,
                question_type=question.question_type,
                text=question.text,
                points=question.points,
                difficulty=question.difficulty,
                answer_data=question.answer_data,
                is_bonus=question.is_bonus,
                is_required=question.is_required,
                quiz_only=question.quiz_only,
                exam_only=question.exam_only,
                canonical=question.canonical or question,  # Link to original
                created_by=user
            )

        return new_bank


class QuestionBankShare(models.Model):
    """Share a question bank with another user"""
    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('edit', 'Can Edit'),
    ]
    bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_banks')
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default='view')
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='banks_shared_by_me')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['bank', 'shared_with']

    def __str__(self):
        return f"{self.bank.name} shared with {self.shared_with.username}"


class QuestionBlock(models.Model):
    """A block of related question variants (e.g., same topic as SA vs LA vs TF)"""
    name = models.CharField(max_length=200)
    question_bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name='blocks')
    max_questions = models.PositiveIntegerField(default=1, help_text="How many questions to pick from this block")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['question_bank', 'name']

    def __str__(self):
        return f"{self.question_bank}: {self.name} ({self.questions.count()} variants)"


class Question(models.Model):
    """Individual question"""

    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = 'multipleChoice', 'Multiple Choice'
        TRUE_FALSE = 'trueFalse', 'True/False'
        SHORT_ANSWER = 'shortAnswer', 'Short Answer'
        LONG_ANSWER = 'longAnswer', 'Long Answer'
        MATCHING = 'matching', 'Matching'
        MULTIPART = 'multipart', 'Multi-part'

    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    # Core fields
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='questions', null=True, blank=True)
    question_bank = models.ForeignKey(QuestionBank, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')  # Deprecated - use course
    question_type = models.CharField(max_length=20, choices=QuestionType.choices)
    text = models.TextField(help_text="Question text in Markdown format")
    points = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)

    # Block grouping (for question variants like SA vs LA vs TF on same topic)
    block = models.ForeignKey(
        QuestionBlock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions',
        help_text="Group of question variants to pick from"
    )
    variant_number = models.PositiveIntegerField(default=1, help_text="Variant number within block")

    # Link to canonical question (for duplicates across banks/courses)
    # If set, this question is a "copy" of the canonical one
    canonical = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_questions',
        help_text="If this is a duplicate, link to the canonical version"
    )

    # Organization
    tags = models.ManyToManyField(Tag, blank=True, related_name='questions')
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    week = models.ForeignKey(
        Week,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questions',
        help_text="Week/module this question belongs to"
    )

    # Type-specific data stored as JSON
    answer_data = models.JSONField(default=dict, help_text="Type-specific answer data")

    # Metadata
    content_hash = models.CharField(max_length=32, blank=True, db_index=True)
    is_bonus = models.BooleanField(default=False)
    is_required = models.BooleanField(default=False)
    quiz_only = models.BooleanField(default=False)
    exam_only = models.BooleanField(default=False)

    # Usage tracking
    times_used = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft delete
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions_deleted')

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['question_type']),
            models.Index(fields=['difficulty']),
            models.Index(fields=['course']),
            models.Index(fields=['canonical']),
            models.Index(fields=['-updated_at']),
            models.Index(fields=['-created_at']),
        ]

    def save(self, *args, **kwargs):
        # Generate content hash for duplicate detection
        self.content_hash = hashlib.md5(self.text.encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.question_type}: {self.text[:50]}..."

    @property
    def is_deleted(self):
        """True if this question is in the trash"""
        return self.deleted_at is not None

    def soft_delete(self, user=None):
        """Move this question to trash"""
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=['deleted_at', 'deleted_by'])

    def restore(self):
        """Restore this question from trash"""
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['deleted_at', 'deleted_by'])

    @property
    def is_canonical(self):
        """True if this is a canonical question (not a copy)"""
        return self.canonical is None

    @property
    def all_linked(self):
        """Get all questions linked to this one (including self and canonical)"""
        if self.canonical:
            # This is a copy, get siblings through canonical
            return Question.objects.filter(
                models.Q(id=self.canonical.id) |
                models.Q(canonical=self.canonical)
            )
        else:
            # This is canonical, get all copies plus self
            return Question.objects.filter(
                models.Q(id=self.id) |
                models.Q(canonical=self)
            )

    def sync_from_canonical(self):
        """Update this question's text/answers from its canonical version"""
        if self.canonical:
            self.text = self.canonical.text
            self.answer_data = self.canonical.answer_data
            self.question_type = self.canonical.question_type
            self.save()

    @classmethod
    def find_duplicates_by_hash(cls):
        """Find questions that have the same content_hash (potential duplicates)"""
        from django.db.models import Count
        duplicates = cls.objects.values('content_hash').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        return duplicates


class QuestionVersion(models.Model):
    """Version history for questions"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='versions')
    text = models.TextField()
    answer_data = models.JSONField(default=dict)
    version_number = models.PositiveIntegerField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    change_summary = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = ['question', 'version_number']

    def __str__(self):
        return f"v{self.version_number} of Question {self.question.id}"


def question_image_path(instance, filename):
    """Generate upload path for question images"""
    import os
    ext = os.path.splitext(filename)[1]
    return f"questions/{instance.question.question_bank.course.code}/{instance.question.id}/{instance.id or 'new'}{ext}"


class QuestionImage(models.Model):
    """Images attached to questions"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    image = models.ImageField(upload_to='question_images/')
    alt_text = models.CharField(max_length=200, blank=True, help_text="Alternative text for accessibility")
    caption = models.CharField(max_length=500, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Image for Q{self.question_id}: {self.alt_text or self.image.name}"

    @property
    def markdown_ref(self):
        """Return markdown reference to embed this image"""
        alt = self.alt_text or "image"
        return f"![{alt}]({self.image.url})"

    @property
    def latex_ref(self):
        """Return LaTeX reference for PDF generation"""
        return f"\\includegraphics[width=0.8\\textwidth]{{{self.image.path}}}"
