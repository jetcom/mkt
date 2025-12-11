"""
AI Grading Service for quiz responses.
"""
import json
import anthropic
from openai import OpenAI
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


SHORT_ANSWER_GRADING_PROMPT = """You are an expert exam grader. Grade the following short answer response.

## Question
{question_text}

## Expected Answer (from answer key)
{expected_answer}

## Student's Response
{student_response}

## Grading Criteria
- Maximum points: {max_points}
- Evaluate: accuracy, completeness, and correctness
- Partial credit is allowed

## Your Task
Provide a JSON response with:
{{
    "score": <number between 0 and {max_points}>,
    "is_correct": <true if essentially correct, false otherwise>,
    "feedback": "<brief constructive feedback for the student>",
    "reasoning": "<your detailed reasoning for this grade>",
    "confidence": <number between 0 and 1>
}}

Be fair but rigorous. Award partial credit for partially correct answers.
Minor spelling/grammar errors should not affect the grade unless they change meaning.
Return ONLY valid JSON, no other text."""


LONG_ANSWER_GRADING_PROMPT = """You are an expert exam grader evaluating an essay/long answer response.

## Question
{question_text}

## Expected Answer/Key Points (from answer key)
{expected_answer}

## Student's Response
{student_response}

## Grading Guidelines
- Maximum points: {max_points}
- Consider: accuracy, completeness, organization, clarity
- Award partial credit appropriately

## Your Task
Provide a JSON response with:
{{
    "score": <number between 0 and {max_points}>,
    "is_correct": <true if substantially correct, false otherwise>,
    "feedback": "<comprehensive feedback for the student>",
    "reasoning": "<your detailed reasoning for this grade>",
    "strengths": ["<what the student did well>"],
    "improvements": ["<areas for improvement>"],
    "confidence": <number between 0 and 1>
}}

Return ONLY valid JSON, no other text."""


class AIGradingService:
    """Service for AI-powered grading of quiz responses."""

    def __init__(self, provider='claude'):
        self.provider = provider
        if provider == 'claude':
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            self.model = 'claude-sonnet-4-20250514'
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = 'gpt-4o'

    def grade_response(self, response):
        """
        Grade a single QuestionResponse.

        Args:
            response: QuestionResponse model instance

        Returns:
            dict with grading results
        """
        question = response.question

        # Only AI-grade short and long answers
        if question.question_type not in ['shortAnswer', 'longAnswer']:
            return self._auto_grade_objective(response)

        # Get student's answer
        student_answer = response.response_data.get('text', '').strip()
        if not student_answer:
            # Empty response = 0 points
            response.points_earned = 0
            response.is_correct = False
            response.grading_status = 'auto_graded'
            response.ai_feedback = "No answer provided."
            response.save()
            return {'score': 0, 'is_correct': False, 'feedback': 'No answer provided.'}

        # Build and send prompt
        prompt = self._build_prompt(question, response, student_answer)

        try:
            if self.provider == 'claude':
                result = self._call_claude(prompt)
            else:
                result = self._call_openai(prompt)

            # Update response with AI grading
            response.ai_score = Decimal(str(result.get('score', 0)))
            response.points_earned = response.ai_score
            response.ai_feedback = result.get('feedback', '')
            response.ai_reasoning = result.get('reasoning', '')
            response.ai_confidence = Decimal(str(result.get('confidence', 0.5)))
            response.ai_graded_at = timezone.now()
            response.ai_model_used = self.model
            response.grading_status = 'ai_graded'
            response.is_correct = result.get('is_correct', False)
            response.save()

            return result

        except Exception as e:
            # Log error and mark for manual grading
            response.ai_reasoning = f"AI grading error: {str(e)}"
            response.grading_status = 'pending'
            response.save()
            raise

    def _auto_grade_objective(self, response):
        """Auto-grade multiple choice and true/false questions."""
        question = response.question
        answer_data = question.answer_data or {}
        student_answer = response.response_data

        is_correct = False

        if question.question_type == 'multipleChoice':
            # Compare selected answer with correct answer
            correct = answer_data.get('correct', '')
            selected = student_answer.get('selected', '')
            is_correct = selected.strip().lower() == correct.strip().lower()

        elif question.question_type == 'trueFalse':
            # Compare boolean values
            correct = answer_data.get('correct')
            selected = student_answer.get('selected')
            # Handle string "true"/"false" as well as boolean
            if isinstance(selected, str):
                selected = selected.lower() == 'true'
            if isinstance(correct, str):
                correct = correct.lower() == 'true'
            is_correct = selected == correct

        # Update response
        response.is_correct = is_correct
        response.points_earned = response.points_possible if is_correct else Decimal('0')
        response.grading_status = 'auto_graded'
        response.save()

        return {
            'score': float(response.points_earned),
            'is_correct': is_correct,
            'feedback': 'Correct!' if is_correct else 'Incorrect.',
            'confidence': 1.0
        }

    def _build_prompt(self, question, response, student_answer):
        """Build the grading prompt based on question type."""
        expected_answer = question.answer_data.get('solution', '')

        if question.question_type == 'shortAnswer':
            return SHORT_ANSWER_GRADING_PROMPT.format(
                question_text=question.text,
                expected_answer=expected_answer,
                student_response=student_answer,
                max_points=float(response.points_possible)
            )
        else:  # longAnswer
            return LONG_ANSWER_GRADING_PROMPT.format(
                question_text=question.text,
                expected_answer=expected_answer,
                student_response=student_answer,
                max_points=float(response.points_possible)
            )

    def _call_claude(self, prompt):
        """Call Claude API for grading."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(message.content[0].text)

    def _call_openai(self, prompt):
        """Call OpenAI API for grading."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert exam grader. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return json.loads(response.choices[0].message.content)

    def grade_submission(self, submission):
        """
        Grade all responses in a submission.

        Args:
            submission: StudentSubmission model instance

        Returns:
            dict with grading results including any errors
        """
        submission.status = 'grading'
        submission.save(update_fields=['status'])

        graded = 0
        errors = []
        for response in submission.responses.filter(grading_status='pending'):
            try:
                self.grade_response(response)
                graded += 1
            except Exception as e:
                errors.append(f"Response {response.id}: {str(e)}")
                print(f"Error grading response {response.id}: {e}")

        # Recalculate total score
        submission.calculate_score()

        # Check if all responses are graded
        pending = submission.responses.filter(grading_status='pending').count()
        if pending == 0:
            submission.status = 'graded'
        else:
            submission.status = 'submitted'  # Some still need grading
        submission.save(update_fields=['status'])

        return {'graded': graded, 'errors': errors}

    def batch_grade(self, responses):
        """
        Grade multiple responses.

        Args:
            responses: QuerySet or list of QuestionResponse instances
        """
        results = []
        for response in responses:
            try:
                result = self.grade_response(response)
                results.append({'response_id': str(response.id), 'success': True, **result})
            except Exception as e:
                results.append({'response_id': str(response.id), 'success': False, 'error': str(e)})
        return results
