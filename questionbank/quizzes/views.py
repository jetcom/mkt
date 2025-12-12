"""
Views for quiz delivery and grading.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.http import HttpResponse
from django.db.models import Q, Count
from datetime import timedelta
import random
import csv
import secrets

from .models import QuizSession, StudentSubmission, QuestionResponse, ScannedExam, QuizInvitation
from .serializers import (
    QuizSessionListSerializer, QuizSessionDetailSerializer, QuizSessionCreateSerializer,
    StudentSubmissionListSerializer, StudentSubmissionDetailSerializer,
    QuestionResponseSerializer, ScannedExamSerializer,
    QuizInfoSerializer, QuizQuestionSerializer, QuizInvitationSerializer
)
from .services.grading import AIGradingService


# ==========================================
# Instructor Views (Auth Required)
# ==========================================

class QuizSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing quiz sessions (instructor)."""
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'access_code', 'template__name']
    ordering_fields = ['created_at', 'name', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        # Show quizzes created by user or for templates they own
        return QuizSession.objects.filter(
            Q(created_by=user) | Q(template__owner=user)
        ).select_related('template', 'template__course').distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return QuizSessionListSerializer
        elif self.action == 'create':
            return QuizSessionCreateSerializer
        return QuizSessionDetailSerializer

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a quiz session."""
        quiz = self.get_object()
        quiz.status = QuizSession.Status.ACTIVE
        quiz.save(update_fields=['status'])
        return Response({'status': 'active', 'access_code': quiz.access_code})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate/close a quiz session."""
        quiz = self.get_object()
        quiz.status = QuizSession.Status.CLOSED
        quiz.save(update_fields=['status'])
        return Response({'status': 'closed'})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a quiz session (alias for deactivate)."""
        return self.deactivate(request, pk)

    @action(detail=True, methods=['post'])
    def regenerate_code(self, request, pk=None):
        """Generate a new access code."""
        quiz = self.get_object()
        new_code = quiz.regenerate_code()
        return Response({'access_code': new_code})

    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        """Get all submissions for this quiz."""
        quiz = self.get_object()
        submissions = quiz.submissions.all()
        serializer = StudentSubmissionListSerializer(submissions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Get all questions for this quiz."""
        from questions.serializers import QuestionListSerializer
        quiz = self.get_object()

        # Get questions from various sources
        questions = list(quiz.questions.all())

        if not questions and quiz.generated_exam:
            questions = list(quiz.generated_exam.questions.all())

        if not questions and quiz.template:
            latest_exam = quiz.template.generated_exams.order_by('-created_at').first()
            if latest_exam:
                questions = list(latest_exam.questions.all())

        serializer = QuestionListSerializer(questions, many=True)
        return Response({
            'questions': serializer.data,
            'source': 'direct' if quiz.questions.exists() else 'generated_exam' if quiz.generated_exam else 'template'
        })

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Export grades as CSV."""
        quiz = self.get_object()
        submissions = quiz.submissions.filter(status__in=['graded', 'reviewed', 'submitted'])

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{quiz.name}_grades.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Student Name', 'Student ID', 'Email',
            'Points Earned', 'Points Possible', 'Percentage',
            'Status', 'Submitted At', 'Late'
        ])

        for sub in submissions:
            writer.writerow([
                sub.student_name,
                sub.student_id,
                sub.student_email,
                sub.total_points_earned,
                sub.total_points_possible,
                sub.percentage_score,
                sub.status,
                sub.submitted_at.isoformat() if sub.submitted_at else '',
                'Yes' if sub.is_late else 'No'
            ])

        return response


class StudentSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing student submissions (instructor)."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return StudentSubmission.objects.filter(
            Q(quiz_session__created_by=user) | Q(quiz_session__template__owner=user)
        ).select_related('quiz_session', 'quiz_session__template')

    def get_serializer_class(self):
        if self.action == 'list':
            return StudentSubmissionListSerializer
        return StudentSubmissionDetailSerializer


class QuestionResponseViewSet(viewsets.ModelViewSet):
    """ViewSet for managing question responses (for grading)."""
    permission_classes = [IsAuthenticated]
    serializer_class = QuestionResponseSerializer

    def get_queryset(self):
        user = self.request.user
        return QuestionResponse.objects.filter(
            Q(submission__quiz_session__created_by=user) |
            Q(submission__quiz_session__template__owner=user)
        ).select_related('submission', 'question')


class GradeOverrideView(APIView):
    """Override a grade for a question response."""
    permission_classes = [IsAuthenticated]

    def post(self, request, response_id):
        response_obj = get_object_or_404(QuestionResponse, id=response_id)

        # Verify ownership
        user = request.user
        quiz = response_obj.submission.quiz_session
        if quiz.created_by != user and (not quiz.template or quiz.template.owner != user):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        score = request.data.get('score')
        feedback = request.data.get('feedback', '')

        if score is None:
            return Response({'error': 'Score is required'}, status=status.HTTP_400_BAD_REQUEST)

        response_obj.override_score = score
        response_obj.override_feedback = feedback
        response_obj.override_by = user
        response_obj.override_at = timezone.now()
        response_obj.grading_status = 'overridden'
        response_obj.save()

        # Recalculate submission total
        response_obj.submission.calculate_score()

        return Response(QuestionResponseSerializer(response_obj).data)


class AIGradeView(APIView):
    """Trigger AI grading for a response."""
    permission_classes = [IsAuthenticated]

    def post(self, request, response_id):
        response_obj = get_object_or_404(QuestionResponse, id=response_id)

        # Verify ownership
        user = request.user
        quiz = response_obj.submission.quiz_session
        if quiz.created_by != user and (not quiz.template or quiz.template.owner != user):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        provider = request.data.get('provider', quiz.ai_grading_provider)

        try:
            grading_service = AIGradingService(provider=provider)
            result = grading_service.grade_response(response_obj)

            # Recalculate submission total
            response_obj.submission.calculate_score()

            return Response({
                'success': True,
                'result': result,
                'response': QuestionResponseSerializer(response_obj).data
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BatchGradeView(APIView):
    """Batch grade multiple responses or a whole submission."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        submission_id = request.data.get('submission_id')
        quiz_session_id = request.data.get('quiz_session_id')
        response_ids = request.data.get('response_ids', [])
        provider = request.data.get('provider', 'claude')

        try:
            grading_service = AIGradingService(provider=provider)
        except Exception as e:
            return Response({'error': f'AI service unavailable: {str(e)}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            if quiz_session_id:
                # Grade all pending responses in a quiz session
                quiz = get_object_or_404(QuizSession, id=quiz_session_id)
                if quiz.created_by != request.user and (quiz.template and quiz.template.owner != request.user):
                    return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

                graded_count = 0
                errors = []
                for submission in quiz.submissions.filter(status__in=['submitted', 'grading']):
                    try:
                        result = grading_service.grade_submission(submission)
                        graded_count += result.get('graded', 0)
                        if result.get('errors'):
                            errors.extend(result['errors'])
                    except Exception as e:
                        errors.append(str(e))

                return Response({
                    'success': True,
                    'graded_count': graded_count,
                    'submission_count': quiz.submissions.count(),
                    'errors': errors if errors else None
                })

            elif submission_id:
                submission = get_object_or_404(StudentSubmission, id=submission_id)
                # Verify ownership
                quiz = submission.quiz_session
                if quiz.created_by != request.user and (quiz.template and quiz.template.owner != request.user):
                    return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

                grading_service.grade_submission(submission)
                graded_count = submission.responses.filter(grading_status__in=['auto_graded', 'ai_graded']).count()
                return Response({
                    'success': True,
                    'graded_count': graded_count,
                    'submission': StudentSubmissionDetailSerializer(submission).data
                })

            elif response_ids:
                responses = QuestionResponse.objects.filter(id__in=response_ids)
                results = grading_service.batch_grade(responses)
                return Response({'success': True, 'results': results})
        except Exception as e:
            return Response({'error': f'Grading failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'error': 'submission_id, quiz_session_id, or response_ids required'}, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# Public Views (Student Quiz Taking)
# ==========================================

class QuizAccessView(APIView):
    """Get quiz info by access code or invitation code (public)."""
    permission_classes = [AllowAny]

    def _is_instructor_preview(self, request, quiz):
        """Check if this is a valid instructor preview request."""
        if request.query_params.get('preview') != 'true':
            return False
        if not request.user.is_authenticated:
            return False
        # Verify ownership
        if quiz.created_by == request.user:
            return True
        if quiz.template and quiz.template.owner == request.user:
            return True
        return False

    def get(self, request, code):
        code = code.upper()
        invitation = None

        # Check if this is an invitation code (8 chars) or access code (6 chars)
        if len(code) == 8:
            invitation = QuizInvitation.objects.filter(code=code).select_related('quiz_session').first()
            if not invitation:
                return Response({'error': 'Invalid invitation code'}, status=status.HTTP_404_NOT_FOUND)
            quiz = invitation.quiz_session
        else:
            quiz = get_object_or_404(QuizSession, access_code=code)

        # Check availability (skip for instructor preview)
        is_preview = self._is_instructor_preview(request, quiz)
        if not is_preview and not quiz.is_available():
            if quiz.status == QuizSession.Status.DRAFT:
                return Response({'error': 'Quiz is not yet available'}, status=status.HTTP_404_NOT_FOUND)
            elif quiz.status == QuizSession.Status.CLOSED:
                return Response({'error': 'Quiz is closed'}, status=status.HTTP_410_GONE)
            elif quiz.start_time and timezone.now() < quiz.start_time:
                return Response({
                    'error': 'Quiz has not started yet',
                    'starts_at': quiz.start_time.isoformat()
                }, status=status.HTTP_425_TOO_EARLY)
            elif quiz.end_time and timezone.now() > quiz.end_time:
                return Response({'error': 'Quiz has ended'}, status=status.HTTP_410_GONE)

        data = QuizInfoSerializer(quiz).data

        # If invitation, include student info (pre-filled)
        if invitation:
            data['invitation'] = {
                'student_name': invitation.student_name,
                'student_email': invitation.student_email,
                'student_id': invitation.student_id,
                'is_used': invitation.is_used
            }
            if invitation.is_used:
                data['invitation']['already_submitted'] = True

        # Mark as preview mode
        if is_preview:
            data['preview_mode'] = True

        return Response(data)


class QuizStartView(APIView):
    """Start a quiz attempt (public)."""
    permission_classes = [AllowAny]

    def _is_instructor_preview(self, request, quiz):
        """Check if this is a valid instructor preview request."""
        preview_data = request.data.get('preview')
        preview_param = request.query_params.get('preview')
        is_preview = preview_data in (True, 'true', 'True') or preview_param in ('true', 'True', '1')
        if not is_preview:
            return False
        if not request.user.is_authenticated:
            return False
        # Verify ownership
        if quiz.created_by == request.user:
            return True
        if quiz.template and quiz.template.owner == request.user:
            return True
        return False

    def post(self, request, code):
        code = code.upper()
        invitation = None

        # Check if this is an invitation code (8 chars) or access code (6 chars)
        if len(code) == 8:
            invitation = QuizInvitation.objects.filter(code=code).select_related('quiz_session').first()
            if not invitation:
                return Response({'error': 'Invalid invitation code'}, status=status.HTTP_404_NOT_FOUND)
            quiz = invitation.quiz_session

            # Check if invitation already used
            if invitation.is_used:
                return Response({'error': 'This quiz invitation has already been used'}, status=status.HTTP_403_FORBIDDEN)

            # Use invitation data for student info
            student_name = invitation.student_name
            student_id = invitation.student_id
            student_email = invitation.student_email
        else:
            quiz = get_object_or_404(QuizSession, access_code=code)

            student_name = request.data.get('student_name', '').strip()
            student_id = request.data.get('student_id', '').strip()
            student_email = request.data.get('student_email', '').strip()

            if not student_name:
                return Response({'error': 'Student name is required'}, status=status.HTTP_400_BAD_REQUEST)

            if quiz.require_student_id and not student_id:
                return Response({'error': 'Student ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Check availability (skip for instructor preview)
        is_preview = self._is_instructor_preview(request, quiz)
        if not is_preview and not quiz.is_available():
            return Response({'error': 'Quiz is not available'}, status=status.HTTP_400_BAD_REQUEST)

        # Check max attempts (skip for invitation-based access - they get 1 attempt)
        if not invitation:
            existing_attempts = StudentSubmission.objects.filter(
                quiz_session=quiz,
                student_id=student_id if student_id else None,
                student_name=student_name
            ).count()

            if existing_attempts >= quiz.max_attempts:
                return Response({'error': 'Maximum attempts reached'}, status=status.HTTP_403_FORBIDDEN)

        # Get questions
        questions = list(quiz.questions.all())
        if not questions and quiz.template:
            # Try generated_exam first
            if quiz.generated_exam and quiz.generated_exam.questions.exists():
                questions = list(quiz.generated_exam.questions.all())
            # Then try latest generated exam from template
            if not questions:
                latest_exam = quiz.template.generated_exams.order_by('-created_at').first()
                if latest_exam and latest_exam.questions.exists():
                    questions = list(latest_exam.questions.all())
            # Then try filter_banks
            if not questions and quiz.template.filter_banks.exists():
                from django.db.models import Q
                for bank in quiz.template.filter_banks.all():
                    bank_questions = list(bank.questions.filter(deleted_at__isnull=True).filter(
                        Q(block__isnull=True) | Q(variant_number=1)
                    )[:50])
                    if bank_questions:
                        questions = bank_questions
                        break

        if not questions:
            return Response({'error': 'No questions configured for this quiz'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Shuffle if enabled
        if quiz.shuffle_questions:
            random.shuffle(questions)

        question_ids = [q.id for q in questions]

        # Calculate expiry time
        expires_at = timezone.now() + timedelta(minutes=quiz.time_limit_minutes)

        # Create submission
        attempt_number = 1 if invitation else (existing_attempts + 1)
        submission = StudentSubmission.objects.create(
            quiz_session=quiz,
            student_name=student_name,
            student_id=student_id,
            student_email=student_email,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            expires_at=expires_at,
            attempt_number=attempt_number,
            question_order=question_ids
        )

        # Link invitation to submission and mark as used
        if invitation:
            invitation.used_at = timezone.now()
            invitation.submission = submission
            invitation.save(update_fields=['used_at', 'submission'])

        # Create empty responses for each question
        total_points = 0
        for i, question in enumerate(questions, 1):
            QuestionResponse.objects.create(
                submission=submission,
                question=question,
                question_number=i,
                points_possible=question.points
            )
            total_points += question.points

        submission.total_points_possible = total_points
        submission.save(update_fields=['total_points_possible'])

        return Response({
            'session_token': submission.session_token,
            'expires_at': expires_at.isoformat(),
            'time_limit_minutes': quiz.time_limit_minutes,
            'question_count': len(questions)
        })

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class QuizQuestionsView(APIView):
    """Get questions for an active quiz (requires session token)."""
    permission_classes = [AllowAny]

    def get(self, request, code):
        token = request.META.get('HTTP_X_QUIZ_SESSION')
        if not token:
            return Response({'error': 'Session token required'}, status=status.HTTP_401_UNAUTHORIZED)

        submission = get_object_or_404(
            StudentSubmission,
            session_token=token,
            quiz_session__access_code=code.upper()
        )

        # Check if expired
        if submission.status != StudentSubmission.Status.IN_PROGRESS:
            return Response({'error': 'Quiz already submitted'}, status=status.HTTP_400_BAD_REQUEST)

        if submission.expires_at and timezone.now() > submission.expires_at:
            # Auto-submit
            self._auto_submit(submission)
            return Response({'error': 'Time expired, quiz has been submitted'}, status=status.HTTP_410_GONE)

        # Get questions in order
        from questions.models import Question
        questions = Question.objects.filter(id__in=submission.question_order)
        question_map = {q.id: q for q in questions}
        ordered_questions = [question_map[qid] for qid in submission.question_order if qid in question_map]

        # Get existing answers
        responses = {r.question_id: r.response_data for r in submission.responses.all()}

        serializer = QuizQuestionSerializer(
            ordered_questions,
            many=True,
            context={'shuffle_answers': submission.quiz_session.shuffle_answers}
        )

        return Response({
            'questions': serializer.data,
            'answers': responses,
            'expires_at': submission.expires_at.isoformat() if submission.expires_at else None,
            'time_remaining_seconds': max(0, int((submission.expires_at - timezone.now()).total_seconds())) if submission.expires_at else None
        })

    def _auto_submit(self, submission):
        submission.status = StudentSubmission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.auto_submitted = True
        submission.time_spent_seconds = int((timezone.now() - submission.started_at).total_seconds())
        submission.save()

        # Grade objective questions
        self._grade_objective_questions(submission)

    def _grade_objective_questions(self, submission):
        """Auto-grade MC and TF questions."""
        grading_service = AIGradingService()
        for response in submission.responses.filter(
            question__question_type__in=['multipleChoice', 'trueFalse'],
            grading_status='pending'
        ):
            grading_service.grade_response(response)
        submission.calculate_score()


class QuizAnswerView(APIView):
    """Save an answer for a question (auto-save)."""
    permission_classes = [AllowAny]

    def post(self, request, code):
        token = request.META.get('HTTP_X_QUIZ_SESSION')
        if not token:
            return Response({'error': 'Session token required'}, status=status.HTTP_401_UNAUTHORIZED)

        submission = get_object_or_404(
            StudentSubmission,
            session_token=token,
            quiz_session__access_code=code.upper()
        )

        if submission.status != StudentSubmission.Status.IN_PROGRESS:
            return Response({'error': 'Quiz already submitted'}, status=status.HTTP_400_BAD_REQUEST)

        # Check expiry (with small grace period)
        grace_period = timedelta(seconds=30)
        if submission.expires_at and timezone.now() > submission.expires_at + grace_period:
            return Response({'error': 'Time expired'}, status=status.HTTP_410_GONE)

        question_id = request.data.get('question_id')
        answer_data = request.data.get('answer')

        if not question_id:
            return Response({'error': 'question_id required'}, status=status.HTTP_400_BAD_REQUEST)

        response_obj = get_object_or_404(
            QuestionResponse,
            submission=submission,
            question_id=question_id
        )

        response_obj.response_data = answer_data
        response_obj.answered_at = timezone.now()
        response_obj.save(update_fields=['response_data', 'answered_at'])

        return Response({'saved': True})


class QuizSubmitView(APIView):
    """Submit the quiz."""
    permission_classes = [AllowAny]

    def post(self, request, code):
        token = request.META.get('HTTP_X_QUIZ_SESSION')
        if not token:
            return Response({'error': 'Session token required'}, status=status.HTTP_401_UNAUTHORIZED)

        submission = get_object_or_404(
            StudentSubmission,
            session_token=token,
            quiz_session__access_code=code.upper()
        )

        if submission.status != StudentSubmission.Status.IN_PROGRESS:
            return Response({'error': 'Quiz already submitted'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if late
        quiz = submission.quiz_session
        is_late = False
        if submission.expires_at and timezone.now() > submission.expires_at:
            is_late = True
            if not quiz.allow_late_submissions:
                # Still accept but mark as late
                pass

        # Update submission
        submission.status = StudentSubmission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.is_late = is_late
        submission.time_spent_seconds = int((timezone.now() - submission.started_at).total_seconds())
        submission.save()

        # Grade objective questions immediately (fast, no API calls)
        grading_service = AIGradingService(provider=quiz.ai_grading_provider)
        for response in submission.responses.filter(
            question__question_type__in=['multipleChoice', 'trueFalse'],
            grading_status='pending'
        ):
            grading_service.grade_response(response)

        # Mark text answers for AI grading (done asynchronously to avoid timeout)
        # AI grading will be done via batch grading endpoint by instructor
        text_responses = submission.responses.filter(
            question__question_type__in=['shortAnswer', 'longAnswer'],
            grading_status='pending'
        )
        if text_responses.exists() and quiz.ai_grading_enabled:
            submission.status = StudentSubmission.Status.SUBMITTED
            submission.save(update_fields=['status'])
            # Note: AI grading deferred to avoid request timeout
            # Instructor can trigger batch grading from dashboard

        # Recalculate score
        submission.calculate_score()

        # Update status
        pending = submission.responses.filter(grading_status='pending').count()
        if pending == 0:
            submission.status = StudentSubmission.Status.GRADED
        else:
            submission.status = StudentSubmission.Status.SUBMITTED
        submission.save(update_fields=['status'])

        result = {
            'submitted': True,
            'is_late': is_late,
            'status': submission.status
        }

        if quiz.show_score_immediately:
            # Only show score if fully graded (no pending responses)
            if submission.status == StudentSubmission.Status.GRADED:
                result['score'] = {
                    'points_earned': float(submission.total_points_earned),
                    'points_possible': float(submission.total_points_possible),
                    'percentage': float(submission.percentage_score) if submission.percentage_score else None
                }
            else:
                result['grading_pending'] = True
                result['grading_message'] = 'Your submission is being graded. Check back later for your score.'

        return Response(result)


class QuizResultsView(APIView):
    """View quiz results (if enabled)."""
    permission_classes = [AllowAny]

    def get(self, request, code):
        token = request.META.get('HTTP_X_QUIZ_SESSION')
        if not token:
            return Response({'error': 'Session token required'}, status=status.HTTP_401_UNAUTHORIZED)

        submission = get_object_or_404(
            StudentSubmission,
            session_token=token,
            quiz_session__access_code=code.upper()
        )

        if submission.status == StudentSubmission.Status.IN_PROGRESS:
            return Response({'error': 'Quiz not yet submitted'}, status=status.HTTP_400_BAD_REQUEST)

        quiz = submission.quiz_session

        result = {
            'student_name': submission.student_name,
            'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
            'is_late': submission.is_late,
            'status': submission.status,
        }

        # Only show score if fully graded
        if submission.status in [StudentSubmission.Status.GRADED, StudentSubmission.Status.REVIEWED]:
            result['score'] = {
                'points_earned': float(submission.total_points_earned),
                'points_possible': float(submission.total_points_possible),
                'percentage': float(submission.percentage_score) if submission.percentage_score else None
            }
        else:
            result['grading_pending'] = True
            result['grading_message'] = 'Your submission is being graded. Check back later for your score.'

        if quiz.show_correct_answers:
            responses = []
            for resp in submission.responses.select_related('question').order_by('question_number'):
                # Format student's answer for display
                response_data = resp.response_data or {}
                if resp.question.question_type == 'multipleChoice':
                    your_answer = response_data.get('selected', '')
                elif resp.question.question_type == 'trueFalse':
                    selected = response_data.get('selected')
                    your_answer = 'True' if selected else 'False' if selected is not None else ''
                else:
                    your_answer = response_data.get('text', '')

                resp_data = {
                    'question_number': resp.question_number,
                    'question_text': resp.question.text,
                    'question_type': resp.question.question_type,
                    'your_answer': your_answer,
                    'points_earned': float(resp.get_final_score()) if resp.get_final_score() else 0,
                    'points_possible': float(resp.points_possible),
                    'is_correct': resp.is_correct,
                    'feedback': resp.ai_feedback or resp.override_feedback
                }

                # Include correct answer
                answer_data = resp.question.answer_data or {}
                if resp.question.question_type == 'multipleChoice':
                    resp_data['correct_answer'] = answer_data.get('correct')
                elif resp.question.question_type == 'trueFalse':
                    correct = answer_data.get('correct')
                    resp_data['correct_answer'] = 'True' if correct else 'False' if correct is not None else ''
                else:
                    resp_data['correct_answer'] = answer_data.get('solution')

                responses.append(resp_data)

            result['responses'] = responses

        return Response(result)


# ==========================================
# Scanned Exam Upload & OCR
# ==========================================

class ScannedExamUploadView(APIView):
    """Upload and process a scanned exam PDF."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        from .services.ocr import OCRService, create_submission_from_scan

        quiz_session_id = request.data.get('quiz_session')
        pdf_file = request.FILES.get('pdf_file')

        if not pdf_file:
            return Response({'error': 'PDF file is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not quiz_session_id:
            return Response({'error': 'quiz_session is required'}, status=status.HTTP_400_BAD_REQUEST)

        quiz = get_object_or_404(QuizSession, id=quiz_session_id)

        # Verify ownership
        if quiz.created_by != request.user and (quiz.template and quiz.template.owner != request.user):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        # Create scanned exam record
        scanned = ScannedExam.objects.create(
            quiz_session=quiz,
            template=quiz.template,
            pdf_file=pdf_file,
            uploaded_by=request.user,
            status='processing'
        )

        try:
            # Process the PDF
            ocr_service = OCRService()
            result = ocr_service.process_scanned_exam(scanned.pdf_file.path)

            # Update scanned exam with results
            scanned.student_name = result['student_info'].get('name')
            scanned.student_id = result['student_info'].get('student_id')
            scanned.ocr_text = result['ocr_text']
            scanned.ocr_confidence = result['confidence']
            scanned.extracted_answers = result['answers']
            scanned.page_count = result['page_count']
            scanned.status = 'extracted'
            scanned.processed_at = timezone.now()
            scanned.save()

            # Create submission from extracted data
            grading_service = AIGradingService(provider=quiz.ai_grading_provider)
            submission = create_submission_from_scan(scanned, grading_service if quiz.ai_grading_enabled else None)

            scanned.status = 'graded' if quiz.ai_grading_enabled else 'extracted'
            scanned.save(update_fields=['status'])

            return Response({
                'success': True,
                'scanned_exam': ScannedExamSerializer(scanned).data,
                'submission': StudentSubmissionDetailSerializer(submission).data
            })

        except Exception as e:
            scanned.status = 'error'
            scanned.error_message = str(e)
            scanned.save(update_fields=['status', 'error_message'])
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ScannedExamViewSet(viewsets.ModelViewSet):
    """ViewSet for managing scanned exams."""
    permission_classes = [IsAuthenticated]
    serializer_class = ScannedExamSerializer

    def get_queryset(self):
        user = self.request.user
        return ScannedExam.objects.filter(
            Q(uploaded_by=user) |
            Q(quiz_session__created_by=user) |
            Q(template__owner=user)
        ).select_related('quiz_session', 'template', 'submission')

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """Reprocess OCR for a scanned exam."""
        from .services.ocr import OCRService

        scanned = self.get_object()

        try:
            ocr_service = OCRService()
            result = ocr_service.process_scanned_exam(scanned.pdf_file.path)

            scanned.ocr_text = result['ocr_text']
            scanned.ocr_confidence = result['confidence']
            scanned.extracted_answers = result['answers']
            scanned.status = 'extracted'
            scanned.error_message = ''
            scanned.processed_at = timezone.now()
            scanned.save()

            return Response({
                'success': True,
                'scanned_exam': ScannedExamSerializer(scanned).data
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# Quiz Invitations (Roster Management)
# ==========================================

class QuizInvitationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing quiz invitations."""
    permission_classes = [IsAuthenticated]
    serializer_class = QuizInvitationSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = QuizInvitation.objects.filter(
            Q(quiz_session__created_by=user) | Q(quiz_session__template__owner=user)
        ).select_related('quiz_session', 'submission')

        # Filter by quiz_session if provided
        quiz_session_id = self.request.query_params.get('quiz_session')
        if quiz_session_id:
            queryset = queryset.filter(quiz_session_id=quiz_session_id)

        return queryset


class RosterImportView(APIView):
    """Import a roster of students and create invitations."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(QuizSession, id=quiz_id)

        # Verify ownership
        if quiz.created_by != request.user and (not quiz.template or quiz.template.owner != request.user):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        # Get CSV file or JSON data
        csv_file = request.FILES.get('file')
        json_data = request.data.get('students')

        students = []

        if csv_file:
            # Parse CSV
            try:
                decoded = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded)
                for row in reader:
                    # Support various column name formats
                    name = row.get('name') or row.get('Name') or row.get('student_name') or row.get('Student Name', '')
                    email = row.get('email') or row.get('Email') or row.get('student_email') or row.get('Student Email', '')
                    student_id = row.get('id') or row.get('ID') or row.get('student_id') or row.get('Student ID', '')

                    if email:  # Email is required
                        students.append({
                            'name': name.strip(),
                            'email': email.strip().lower(),
                            'student_id': str(student_id).strip()
                        })
            except Exception as e:
                return Response({'error': f'CSV parse error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        elif json_data:
            # JSON array of students
            import json
            if isinstance(json_data, str):
                json_data = json.loads(json_data)
            for s in json_data:
                if s.get('email'):
                    students.append({
                        'name': s.get('name', '').strip(),
                        'email': s.get('email', '').strip().lower(),
                        'student_id': s.get('student_id', '').strip()
                    })
        else:
            return Response({'error': 'No file or students data provided'}, status=status.HTTP_400_BAD_REQUEST)

        if not students:
            return Response({'error': 'No valid students found in import'}, status=status.HTTP_400_BAD_REQUEST)

        # Create invitations
        created = 0
        skipped = 0
        errors = []

        for student in students:
            try:
                invitation, was_created = QuizInvitation.objects.get_or_create(
                    quiz_session=quiz,
                    student_email=student['email'],
                    defaults={
                        'student_name': student['name'] or student['email'].split('@')[0],
                        'student_id': student['student_id']
                    }
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append(f"{student['email']}: {str(e)}")

        return Response({
            'success': True,
            'created': created,
            'skipped': skipped,
            'total': len(students),
            'errors': errors
        })


class SendInvitationsView(APIView):
    """Send email invitations to students."""
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        quiz = get_object_or_404(QuizSession, id=quiz_id)

        # Verify ownership
        if quiz.created_by != request.user and (not quiz.template or quiz.template.owner != request.user):
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        # Get invitations to send
        invitation_ids = request.data.get('invitation_ids')  # Optional: specific invitations
        resend_all = request.data.get('resend', False)  # Resend to already sent

        queryset = quiz.invitations.all()

        if invitation_ids:
            queryset = queryset.filter(id__in=invitation_ids)

        if not resend_all:
            queryset = queryset.filter(email_sent_at__isnull=True)

        invitations = list(queryset)

        if not invitations:
            return Response({'error': 'No invitations to send'}, status=status.HTTP_400_BAD_REQUEST)

        # Send emails
        from .services.email import send_quiz_invitations
        results = send_quiz_invitations(quiz, invitations, request)

        return Response({
            'success': True,
            'sent': results['sent'],
            'failed': results['failed'],
            'errors': results['errors']
        })


# ==========================================
# Quiz Taking Page (HTML)
# ==========================================

def quiz_take_page(request, code):
    """Render the quiz taking page."""
    # Check if this is an invitation code (8 chars) or access code (6 chars)
    if len(code) == 8:
        invitation = get_object_or_404(QuizInvitation, code=code.upper())
        quiz = invitation.quiz_session
        return render(request, 'quiz_take.html', {
            'quiz': quiz,
            'code': code,
            'invitation': invitation
        })
    else:
        quiz = get_object_or_404(QuizSession, access_code=code.upper())
        return render(request, 'quiz_take.html', {'quiz': quiz, 'code': code})


def quiz_preview_page(request, quiz_id):
    """Render the quiz preview page for instructors."""
    if not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect(f'/login/?next=/quiz/preview/{quiz_id}/')

    quiz = get_object_or_404(QuizSession, id=quiz_id)

    # Verify ownership
    if quiz.created_by != request.user and (not quiz.template or quiz.template.owner != request.user):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Not authorized to preview this quiz')

    return render(request, 'quiz_take.html', {
        'quiz': quiz,
        'code': quiz.access_code,
        'preview_mode': True
    })
