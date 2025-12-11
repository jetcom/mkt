from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q, Count, Avg
from django.contrib.auth.models import User
from django.conf import settings
from .models import Tag, Course, QuestionBank, QuestionBlock, Question, QuestionVersion, Week, CourseShare, QuestionBankShare, QuestionImage
from exams.models import ExamTemplate, ExamTemplateShare

# Try to import PostgreSQL full-text search, fall back gracefully
try:
    from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
    HAS_POSTGRES_SEARCH = 'postgresql' in settings.DATABASES.get('default', {}).get('ENGINE', '')
except ImportError:
    HAS_POSTGRES_SEARCH = False
from .serializers import (
    TagSerializer, CourseSerializer, QuestionBankSerializer, QuestionBlockSerializer,
    QuestionListSerializer, QuestionDetailSerializer, QuestionVersionSerializer, WeekSerializer,
    CourseShareSerializer, QuestionBankShareSerializer, UserSerializer, QuestionImageSerializer
)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    search_fields = ['name']
    pagination_class = None

    def get_queryset(self):
        queryset = Tag.objects.all()
        course = self.request.query_params.get('course')
        if course:
            # Get tags used by questions in this course
            queryset = queryset.filter(
                questions__question_bank__course__code=course
            ).distinct()
        return queryset.order_by('name')


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    search_fields = ['name', 'code']
    lookup_field = 'code'

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Course.objects.none()
        # Show courses user owns or that are shared with them
        return Course.objects.filter(
            Q(owner=user) | Q(shares__shared_with=user)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def share(self, request, code=None):
        """Share this course with another user - cascades to all banks and templates"""
        course = self.get_object()
        if course.owner != request.user:
            return Response({'error': 'Only the owner can share'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        permission = request.data.get('permission', 'view')

        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Share the course
        share, created = CourseShare.objects.update_or_create(
            course=course,
            shared_with=target_user,
            defaults={'permission': permission, 'shared_by': request.user}
        )

        # Cascade: share all question banks in this course
        for bank in course.question_banks.filter(owner=request.user):
            QuestionBankShare.objects.update_or_create(
                bank=bank,
                shared_with=target_user,
                defaults={'permission': permission, 'shared_by': request.user}
            )

        # Cascade: share all exam templates in this course
        for template in course.exam_templates.filter(owner=request.user):
            ExamTemplateShare.objects.update_or_create(
                template=template,
                shared_with=target_user,
                defaults={'permission': permission, 'shared_by': request.user}
            )

        return Response(CourseShareSerializer(share).data)

    @action(detail=True, methods=['delete'])
    def unshare(self, request, code=None):
        """Remove sharing for a user - cascades to all banks and templates"""
        course = self.get_object()
        if course.owner != request.user:
            return Response({'error': 'Only the owner can manage sharing'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')

        # Unshare the course
        CourseShare.objects.filter(course=course, shared_with__username=username).delete()

        # Cascade: unshare all question banks in this course
        QuestionBankShare.objects.filter(
            bank__course=course,
            bank__owner=request.user,
            shared_with__username=username
        ).delete()

        # Cascade: unshare all exam templates in this course
        ExamTemplateShare.objects.filter(
            template__course=course,
            template__owner=request.user,
            shared_with__username=username
        ).delete()

        return Response({'status': 'unshared'})

    @action(detail=True, methods=['get'])
    def shares(self, request, code=None):
        """List all shares for this course"""
        course = self.get_object()
        if course.owner != request.user:
            return Response({'error': 'Only the owner can view shares'}, status=status.HTTP_403_FORBIDDEN)
        shares = course.shares.all()
        return Response(CourseShareSerializer(shares, many=True).data)


class WeekViewSet(viewsets.ModelViewSet):
    queryset = Week.objects.select_related('course').all()
    serializer_class = WeekSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Week.objects.select_related('course').annotate(
            question_count=Count('questions')
        )
        course = self.request.query_params.get('course')
        if course:
            queryset = queryset.filter(course__code=course)
        return queryset.order_by('course', 'number')


class QuestionBankViewSet(viewsets.ModelViewSet):
    queryset = QuestionBank.objects.select_related('course').all()
    serializer_class = QuestionBankSerializer
    search_fields = ['name', 'description']
    pagination_class = None  # Return all banks without pagination

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return QuestionBank.objects.none()

        # Use annotate to avoid N+1 queries for question_count and block_count
        queryset = QuestionBank.objects.select_related('course', 'owner').annotate(
            question_count=Count('questions'),
            block_count=Count('blocks')
        )

        # Filter by ownership or sharing
        queryset = queryset.filter(
            Q(owner=user) | Q(shares__shared_with=user) | Q(course__owner=user) | Q(course__shares__shared_with=user)
        ).distinct()

        course = self.request.query_params.get('course')
        if course:
            queryset = queryset.filter(course__code=course)
        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share this bank with another user (collaboration)"""
        bank = self.get_object()
        if bank.owner != request.user:
            return Response({'error': 'Only the owner can share'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        permission = request.data.get('permission', 'view')

        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        share, created = QuestionBankShare.objects.update_or_create(
            bank=bank,
            shared_with=target_user,
            defaults={'permission': permission, 'shared_by': request.user}
        )
        return Response(QuestionBankShareSerializer(share).data)

    @action(detail=True, methods=['post'])
    def copy(self, request, pk=None):
        """Create a copy of this bank for the current user"""
        bank = self.get_object()
        new_name = request.data.get('name', f"{bank.name} (copy)")
        new_bank = bank.copy_to_user(request.user, new_name)
        return Response(QuestionBankSerializer(new_bank).data)

    @action(detail=True, methods=['delete'])
    def unshare(self, request, pk=None):
        """Remove sharing for a user"""
        bank = self.get_object()
        if bank.owner != request.user:
            return Response({'error': 'Only the owner can manage sharing'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        QuestionBankShare.objects.filter(bank=bank, shared_with__username=username).delete()
        return Response({'status': 'unshared'})

    @action(detail=True, methods=['get'])
    def shares(self, request, pk=None):
        """List all shares for this bank"""
        bank = self.get_object()
        if bank.owner != request.user:
            return Response({'error': 'Only the owner can view shares'}, status=status.HTTP_403_FORBIDDEN)
        shares = bank.shares.all()
        return Response(QuestionBankShareSerializer(shares, many=True).data)


class QuestionBlockViewSet(viewsets.ModelViewSet):
    queryset = QuestionBlock.objects.select_related('question_bank__course').all()
    serializer_class = QuestionBlockSerializer
    search_fields = ['name', 'description']
    pagination_class = None

    def get_queryset(self):
        queryset = QuestionBlock.objects.select_related('question_bank__course').all()
        course = self.request.query_params.get('course')
        if course:
            queryset = queryset.filter(question_bank__course__code=course)
        bank = self.request.query_params.get('bank')
        if bank:
            queryset = queryset.filter(question_bank_id=bank)
        return queryset

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Get all questions in this block"""
        block = self.get_object()
        questions = block.questions.all()
        return Response(QuestionListSerializer(questions, many=True).data)


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all()
    pagination_class = None  # Return all questions without pagination for exam builder
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['text', 'tags__name']
    ordering_fields = ['created_at', 'updated_at', 'points', 'difficulty', 'times_used']
    ordering = ['-updated_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return QuestionListSerializer
        return QuestionDetailSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Question.objects.none()

        queryset = Question.objects.select_related(
            'question_bank__course',
            'block',  # Add block to avoid N+1 for block info
            'week'   # Add week to avoid N+1 for week info
        ).prefetch_related('tags')

        # Filter by question bank ownership/sharing
        # User can see questions if they own the bank, bank is shared with them,
        # they own the course, or course is shared with them
        queryset = queryset.filter(
            Q(question_bank__owner=user) |
            Q(question_bank__shares__shared_with=user) |
            Q(question_bank__course__owner=user) |
            Q(question_bank__course__shares__shared_with=user)
        ).distinct()

        # Check if we're viewing trash
        show_trash = self.request.query_params.get('trash') == 'true'

        if show_trash:
            # Only show deleted questions
            queryset = queryset.filter(deleted_at__isnull=False)
        else:
            # Exclude deleted questions by default
            queryset = queryset.filter(deleted_at__isnull=True)

        # For list view, only show canonical questions (not duplicates)
        # and only show one question per block (variant 1 or first)
        if self.action == 'list' and not show_trash:
            queryset = queryset.filter(canonical__isnull=True)
            # Only show first variant from each block (or questions not in blocks)
            queryset = queryset.filter(
                Q(block__isnull=True) | Q(variant_number__isnull=True) | Q(variant_number=1)
            )
            # Annotate with counts to avoid N+1 queries in serializers
            queryset = queryset.annotate(
                _linked_count=Count('linked_questions', distinct=True),
                _block_variant_count=Count('block__questions', distinct=True)
            )

        # Filter by course
        course = self.request.query_params.get('course')
        if course:
            queryset = queryset.filter(question_bank__course__code=course)

        # Filter by question bank
        bank = self.request.query_params.get('bank')
        if bank:
            queryset = queryset.filter(question_bank_id=bank)

        # Filter by type
        qtype = self.request.query_params.get('type')
        if qtype:
            queryset = queryset.filter(question_type=qtype)

        # Filter by difficulty
        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)

        # Filter by tags
        tags = self.request.query_params.getlist('tags')
        if tags:
            queryset = queryset.filter(tags__name__in=tags).distinct()

        # Filter by week
        week = self.request.query_params.get('week')
        if week:
            queryset = queryset.filter(week_id=week)

        # Enhanced search (overrides default DRF search)
        search = self.request.query_params.get('search')
        if search:
            search = search.strip()
            if HAS_POSTGRES_SEARCH:
                # Use PostgreSQL full-text search with ranking
                search_vector = SearchVector('text', weight='A') + SearchVector('tags__name', weight='B')
                search_query = SearchQuery(search)
                queryset = queryset.annotate(
                    search=search_vector,
                    rank=SearchRank(search_vector, search_query)
                ).filter(search=search_query).order_by('-rank')
            else:
                # SQLite fallback: improved multi-word search
                # Split search into words and require all words to match
                words = search.split()
                for word in words:
                    queryset = queryset.filter(
                        Q(text__icontains=word) |
                        Q(tags__name__icontains=word) |
                        Q(answer_data__icontains=word)
                    )
                queryset = queryset.distinct()

        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    def destroy(self, request, *args, **kwargs):
        """Soft delete instead of hard delete"""
        question = self.get_object()
        question.soft_delete(user=request.user if request.user.is_authenticated else None)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore a soft-deleted question from trash"""
        # Get the question even if it's deleted
        question = Question.objects.filter(pk=pk).first()
        if not question:
            return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)
        if not question.deleted_at:
            return Response({'error': 'Question is not in trash'}, status=status.HTTP_400_BAD_REQUEST)
        question.restore()
        return Response(QuestionDetailSerializer(question).data)

    @action(detail=True, methods=['delete'])
    def permanent_delete(self, request, pk=None):
        """Permanently delete a question from trash"""
        question = Question.objects.filter(pk=pk, deleted_at__isnull=False).first()
        if not question:
            return Response({'error': 'Question not found in trash'}, status=status.HTTP_404_NOT_FOUND)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def empty_trash(self, request):
        """Permanently delete all trashed questions for the current user's courses"""
        user = request.user
        if not user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        # Get questions in trash from user's courses
        deleted = Question.objects.filter(
            deleted_at__isnull=False
        ).filter(
            Q(question_bank__course__owner=user) |
            Q(question_bank__owner=user) |
            Q(created_by=user)
        )
        count = deleted.count()
        deleted.delete()
        return Response({'deleted': count})

    @action(detail=False, methods=['get'])
    def trash_count(self, request):
        """Get count of questions in trash"""
        user = request.user
        if not user.is_authenticated:
            return Response({'count': 0})

        count = Question.objects.filter(
            deleted_at__isnull=False
        ).filter(
            Q(question_bank__course__owner=user) |
            Q(question_bank__owner=user) |
            Q(created_by=user)
        ).count()
        return Response({'count': count})

    @action(detail=False, methods=['get'])
    def usage_stats(self, request):
        """Get question usage statistics"""
        user = request.user
        if not user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        # Get all questions accessible to user (not deleted)
        queryset = Question.objects.filter(
            deleted_at__isnull=True
        ).filter(
            Q(question_bank__course__owner=user) |
            Q(question_bank__owner=user) |
            Q(created_by=user)
        ).distinct()

        # Filter by course if provided
        course = request.query_params.get('course')
        if course:
            queryset = queryset.filter(question_bank__course__code=course)

        total = queryset.count()
        used = queryset.filter(times_used__gt=0).count()
        never_used = total - used

        # Most used questions
        most_used = queryset.filter(times_used__gt=0).order_by('-times_used')[:10]

        # Recently used
        recently_used = queryset.filter(last_used__isnull=False).order_by('-last_used')[:10]

        # Usage by type
        by_type = {}
        for q in queryset:
            qtype = q.question_type
            if qtype not in by_type:
                by_type[qtype] = {'total': 0, 'used': 0, 'times_used': 0}
            by_type[qtype]['total'] += 1
            by_type[qtype]['times_used'] += q.times_used
            if q.times_used > 0:
                by_type[qtype]['used'] += 1

        return Response({
            'total_questions': total,
            'questions_used': used,
            'questions_never_used': never_used,
            'usage_rate': round(used / total * 100, 1) if total > 0 else 0,
            'most_used': [
                {
                    'id': q.id,
                    'text': q.text[:80] + '...' if len(q.text) > 80 else q.text,
                    'type': q.question_type,
                    'times_used': q.times_used,
                    'last_used': q.last_used
                } for q in most_used
            ],
            'recently_used': [
                {
                    'id': q.id,
                    'text': q.text[:80] + '...' if len(q.text) > 80 else q.text,
                    'type': q.question_type,
                    'times_used': q.times_used,
                    'last_used': q.last_used
                } for q in recently_used
            ],
            'by_type': by_type
        })

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Get version history for a question"""
        question = self.get_object()
        versions = question.versions.all()
        serializer = QuestionVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def duplicates(self, request):
        """Find potential duplicate questions"""
        duplicates = (
            Question.objects
            .values('content_hash')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )
        result = []
        for dup in duplicates:
            questions = Question.objects.filter(content_hash=dup['content_hash'])
            result.append({
                'hash': dup['content_hash'],
                'count': dup['count'],
                'questions': QuestionListSerializer(questions, many=True).data
            })
        return Response(result)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get question statistics"""
        course = request.query_params.get('course')
        queryset = Question.objects.all()
        if course:
            queryset = queryset.filter(question_bank__course__code=course)

        stats = {
            'total': queryset.count(),
            'by_type': dict(queryset.values('question_type').annotate(count=Count('id')).values_list('question_type', 'count')),
            'by_difficulty': dict(queryset.values('difficulty').annotate(count=Count('id')).values_list('difficulty', 'count')),
            'avg_points': queryset.aggregate(avg=Avg('points'))['avg'],
        }
        return Response(stats)

    @action(detail=True, methods=['get'])
    def linked(self, request, pk=None):
        """Get all questions linked to this one (canonical + copies)"""
        question = self.get_object()
        linked = question.all_linked
        return Response(QuestionListSerializer(linked, many=True).data)

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Sync this question from its canonical version"""
        question = self.get_object()
        if not question.canonical:
            return Response({'error': 'This question has no canonical version'}, status=status.HTTP_400_BAD_REQUEST)
        question.sync_from_canonical()
        return Response({'status': 'synced'})

    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Create a clone of this question"""
        question = self.get_object()

        # Create a copy with all relevant fields
        cloned = Question.objects.create(
            question_bank=question.question_bank,
            question_type=question.question_type,
            text=question.text,
            points=question.points,
            difficulty=question.difficulty,
            answer_data=question.answer_data.copy() if question.answer_data else {},
            is_bonus=question.is_bonus,
            is_required=question.is_required,
            quiz_only=question.quiz_only,
            exam_only=question.exam_only,
            week=question.week,
            created_by=request.user if request.user.is_authenticated else None
        )

        # Copy tags
        cloned.tags.set(question.tags.all())

        return Response(QuestionDetailSerializer(cloned).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def images(self, request, pk=None):
        """Get all images for this question"""
        question = self.get_object()
        images = question.images.all()
        serializer = QuestionImageSerializer(images, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_image(self, request, pk=None):
        """Upload an image for this question"""
        question = self.get_object()
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'No image file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if image_file.content_type not in allowed_types:
            return Response({'error': 'Invalid file type. Use JPEG, PNG, GIF, or WebP.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the image record
        image = QuestionImage.objects.create(
            question=question,
            image=image_file,
            alt_text=request.data.get('alt_text', ''),
            caption=request.data.get('caption', ''),
            uploaded_by=request.user
        )

        serializer = QuestionImageSerializer(image, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ImageUploadViewSet(viewsets.ViewSet):
    """Standalone image upload for new questions (before question exists)"""
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request):
        """Upload an image without associating to a question yet"""
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'No image file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if image_file.content_type not in allowed_types:
            return Response({'error': 'Invalid file type. Use JPEG, PNG, GIF, or WebP.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create orphan image (no question yet)
        image = QuestionImage.objects.create(
            question=None,
            image=image_file,
            alt_text=request.data.get('alt_text', ''),
            caption=request.data.get('caption', ''),
            uploaded_by=request.user
        )

        serializer = QuestionImageSerializer(image, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for searching users (for sharing)"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = User.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        # Exclude current user from results
        if self.request.user.is_authenticated:
            queryset = queryset.exclude(id=self.request.user.id)
        return queryset[:20]  # Limit results
