from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Tag, Course, QuestionBank, QuestionBlock, Question, QuestionVersion, Week, CourseShare, QuestionBankShare, QuestionImage


class UserSerializer(serializers.ModelSerializer):
    """Simplified user serializer for sharing"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class TagSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'question_count']

    def get_question_count(self, obj):
        return obj.questions.count()


class CourseSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source='owner.username', read_only=True, allow_null=True)
    is_owner = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'name', 'code', 'description', 'question_count', 'owner', 'owner_username', 'is_owner', 'is_shared', 'created_at', 'updated_at']
        read_only_fields = ['owner']

    def get_question_count(self, obj):
        return obj.questions.count()

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


class CourseShareSerializer(serializers.ModelSerializer):
    shared_with_username = serializers.CharField(source='shared_with.username', read_only=True)
    shared_by_username = serializers.CharField(source='shared_by.username', read_only=True)

    class Meta:
        model = CourseShare
        fields = ['id', 'course', 'shared_with', 'shared_with_username', 'shared_by', 'shared_by_username', 'permission', 'created_at']
        read_only_fields = ['shared_by']


class WeekSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course.code', read_only=True)
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Week
        fields = ['id', 'course', 'course_code', 'number', 'name', 'description', 'question_count', 'created_at', 'updated_at']


class QuestionBankSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course.code', read_only=True)
    # These are annotated in the viewset queryset for performance
    question_count = serializers.IntegerField(read_only=True)
    block_count = serializers.IntegerField(read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True, allow_null=True)
    is_owner = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()

    class Meta:
        model = QuestionBank
        fields = ['id', 'name', 'course', 'course_code', 'description', 'question_count', 'block_count', 'owner', 'owner_username', 'is_owner', 'is_shared', 'created_at', 'updated_at']
        read_only_fields = ['owner']

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


class QuestionBankShareSerializer(serializers.ModelSerializer):
    shared_with_username = serializers.CharField(source='shared_with.username', read_only=True)
    shared_by_username = serializers.CharField(source='shared_by.username', read_only=True)

    class Meta:
        model = QuestionBankShare
        fields = ['id', 'bank', 'shared_with', 'shared_with_username', 'shared_by', 'shared_by_username', 'permission', 'created_at']
        read_only_fields = ['shared_by']


class QuestionBlockSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()
    bank_name = serializers.CharField(source='question_bank.name', read_only=True)
    course_code = serializers.CharField(source='question_bank.course.code', read_only=True)

    class Meta:
        model = QuestionBlock
        fields = ['id', 'name', 'question_bank', 'bank_name', 'course_code', 'max_questions', 'description', 'question_count', 'created_at', 'updated_at']

    def get_question_count(self, obj):
        return obj.questions.count()


class QuestionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    tags = TagSerializer(many=True, read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    bank_name = serializers.CharField(source='question_bank.name', read_only=True, allow_null=True)  # Deprecated
    linked_count = serializers.SerializerMethodField()
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    block_max_questions = serializers.IntegerField(source='block.max_questions', read_only=True, allow_null=True)
    block_variant_count = serializers.SerializerMethodField()
    block_types = serializers.SerializerMethodField()
    block_samples = serializers.SerializerMethodField()
    week_number = serializers.IntegerField(source='week.number', read_only=True, allow_null=True)
    week_name = serializers.CharField(source='week.name', read_only=True, allow_null=True)

    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'text', 'points', 'difficulty',
            'tags', 'course_code', 'bank_name', 'times_used', 'last_used',
            'is_bonus', 'is_required', 'canonical', 'linked_count',
            'block', 'block_name', 'block_max_questions', 'variant_number', 'block_variant_count', 'block_types', 'block_samples',
            'week', 'week_number', 'week_name',
            'deleted_at',
            'created_at', 'updated_at'
        ]

    def get_linked_count(self, obj):
        """Count of linked questions (including this one)"""
        # Use annotated value if available (from list view)
        if hasattr(obj, '_linked_count'):
            count = obj._linked_count or 0
            return count + 1 if count > 0 else 0
        # Fallback for detail view
        if obj.canonical:
            return obj.canonical.linked_questions.count() + 1
        return obj.linked_questions.count() + 1 if obj.linked_questions.exists() else 0

    def get_block_variant_count(self, obj):
        """Count of variants in the block"""
        # Use annotated value if available (from list view)
        if hasattr(obj, '_block_variant_count'):
            return obj._block_variant_count or 0
        # Fallback for detail view
        if obj.block:
            return obj.block.questions.count()
        return 0

    def get_block_types(self, obj):
        """Get all variants in the block with their types"""
        if not obj.block:
            return None
        # Return list of all variants with id, type, text preview, and points
        variants = []
        for q in obj.block.questions.all().order_by('variant_number'):
            variants.append({
                'id': q.id,
                'type': q.question_type,
                'text': q.text[:150] + ('...' if len(q.text) > 150 else ''),
                'points': int(q.points)
            })
        return variants if variants else None

    def get_block_samples(self, obj):
        """Deprecated - data is now in block_types"""
        return None


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Full serializer with answer data"""
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, write_only=True, source='tags', required=False
    )
    course_code = serializers.CharField(source='course.code', read_only=True)
    bank_name = serializers.CharField(source='question_bank.name', read_only=True, allow_null=True)  # Deprecated
    block_name = serializers.CharField(source='block.name', read_only=True, allow_null=True)
    block_max_questions = serializers.IntegerField(source='block.max_questions', read_only=True, allow_null=True)
    block_variant_count = serializers.SerializerMethodField()
    week_number = serializers.IntegerField(source='week.number', read_only=True, allow_null=True)
    week_name = serializers.CharField(source='week.name', read_only=True, allow_null=True)

    class Meta:
        model = Question
        fields = [
            'id', 'course', 'question_bank', 'question_type', 'text', 'points', 'difficulty',
            'answer_data', 'tags', 'tag_ids', 'course_code', 'bank_name',
            'block', 'block_name', 'block_max_questions', 'variant_number', 'block_variant_count',
            'week', 'week_number', 'week_name',
            'is_bonus', 'is_required', 'quiz_only', 'exam_only',
            'times_used', 'last_used', 'content_hash',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['content_hash', 'times_used', 'last_used', 'created_by']
        extra_kwargs = {
            'question_bank': {'required': False, 'allow_null': True},  # Deprecated
            'course': {'required': False},  # Will be required once migration complete
        }

    def get_block_variant_count(self, obj):
        """Count of variants in the block"""
        if obj.block:
            return obj.block.questions.count()
        return 0


class QuestionVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionVersion
        fields = ['id', 'version_number', 'text', 'answer_data', 'change_summary', 'created_by', 'created_at']


class QuestionImageSerializer(serializers.ModelSerializer):
    markdown_ref = serializers.ReadOnlyField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = QuestionImage
        fields = ['id', 'question', 'image', 'url', 'alt_text', 'caption', 'markdown_ref', 'uploaded_by', 'created_at']
        read_only_fields = ['uploaded_by', 'markdown_ref']

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        elif obj.image:
            return obj.image.url
        return None
