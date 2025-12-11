"""
OCR service for processing scanned paper exams.

Uses pytesseract for local OCR or can be extended to use
cloud services like Google Cloud Vision for better handwriting recognition.
"""
import re
import os
import tempfile
from typing import Dict, List, Optional, Tuple
from django.conf import settings


class OCRService:
    """Service for extracting text and answers from scanned exams."""

    def __init__(self, use_cloud=False):
        """
        Initialize the OCR service.

        Args:
            use_cloud: If True, use Google Cloud Vision (requires credentials).
                      If False, use pytesseract for local OCR.
        """
        self.use_cloud = use_cloud

    def process_pdf(self, pdf_path: str) -> Dict:
        """
        Process a PDF file and extract text from all pages.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Dictionary with:
                - pages: List of page texts
                - page_count: Number of pages
                - full_text: Combined text from all pages
                - confidence: Overall OCR confidence (0-100)
        """
        try:
            from pdf2image import convert_from_path
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise ImportError(
                f"Missing required package: {e}. "
                "Install with: pip install pdf2image pytesseract Pillow"
            )

        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=300)

        pages = []
        confidences = []

        for i, image in enumerate(images):
            # Get detailed OCR data including confidence
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            # Extract text
            text = pytesseract.image_to_string(image)
            pages.append(text)

            # Calculate average confidence for this page
            valid_confs = [c for c in data['conf'] if c > 0]
            if valid_confs:
                confidences.append(sum(valid_confs) / len(valid_confs))

        return {
            'pages': pages,
            'page_count': len(pages),
            'full_text': '\n\n--- Page Break ---\n\n'.join(pages),
            'confidence': sum(confidences) / len(confidences) if confidences else 0
        }

    def process_image(self, image_path: str) -> Dict:
        """
        Process a single image file.

        Args:
            image_path: Path to the image file.

        Returns:
            Dictionary with text, confidence, and bounding boxes.
        """
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise ImportError(f"Missing required package: {e}")

        image = Image.open(image_path)

        # Get OCR data
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(image)

        # Calculate confidence
        valid_confs = [c for c in data['conf'] if c > 0]
        confidence = sum(valid_confs) / len(valid_confs) if valid_confs else 0

        return {
            'text': text,
            'confidence': confidence,
            'words': self._extract_words_with_positions(data)
        }

    def _extract_words_with_positions(self, data: Dict) -> List[Dict]:
        """Extract words with their bounding box positions."""
        words = []
        for i in range(len(data['text'])):
            if data['text'][i].strip():
                words.append({
                    'text': data['text'][i],
                    'left': data['left'][i],
                    'top': data['top'][i],
                    'width': data['width'][i],
                    'height': data['height'][i],
                    'confidence': data['conf'][i]
                })
        return words

    def extract_answers(self, text: str, question_count: int = None) -> Dict[int, str]:
        """
        Extract answers from OCR text based on common patterns.

        Looks for patterns like:
            - "1. A" or "1) A" or "1: A"
            - "1. True" or "1. False"
            - "1. [answer text]"
            - Numbered answers on answer sheets

        Args:
            text: The OCR text to parse.
            question_count: Expected number of questions (optional).

        Returns:
            Dictionary mapping question numbers to extracted answers.
        """
        answers = {}

        # Pattern for multiple choice (1. A, 1) B, etc.)
        mc_pattern = r'(?:^|\n)\s*(\d+)[.)\]:]\s*([A-Ea-e])\s*(?:\n|$)'
        for match in re.finditer(mc_pattern, text, re.MULTILINE):
            q_num = int(match.group(1))
            answer = match.group(2).upper()
            answers[q_num] = answer

        # Pattern for True/False
        tf_pattern = r'(?:^|\n)\s*(\d+)[.)\]:]\s*(True|False|T|F)\s*(?:\n|$)'
        for match in re.finditer(tf_pattern, text, re.MULTILINE | re.IGNORECASE):
            q_num = int(match.group(1))
            answer = match.group(2).upper()
            if answer in ['T', 'TRUE']:
                answer = 'True'
            elif answer in ['F', 'FALSE']:
                answer = 'False'
            answers[q_num] = answer

        # Pattern for short answers (1. answer text until next number or end)
        # This is more complex and may need refinement
        short_pattern = r'(?:^|\n)\s*(\d+)[.)\]:]\s*(.+?)(?=\n\s*\d+[.)\]:]|\n\n|\Z)'
        for match in re.finditer(short_pattern, text, re.MULTILINE | re.DOTALL):
            q_num = int(match.group(1))
            if q_num not in answers:  # Don't overwrite MC/TF
                answer_text = match.group(2).strip()
                # Skip if it looks like just a letter (already captured as MC)
                if len(answer_text) > 2:
                    answers[q_num] = answer_text

        return answers

    def extract_student_info(self, text: str) -> Dict:
        """
        Extract student name and ID from the exam header.

        Looks for patterns like:
            - "Name: John Doe"
            - "Student ID: 12345"
            - "ID: 12345"

        Args:
            text: The OCR text from the first page.

        Returns:
            Dictionary with 'name' and 'student_id' keys.
        """
        info = {'name': None, 'student_id': None}

        # Look for name
        name_patterns = [
            r'Name[:\s]+([A-Za-z\s\'-]+)',
            r'Student[:\s]+([A-Za-z\s\'-]+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Clean up - remove trailing numbers or other artifacts
                name = re.sub(r'\d+$', '', name).strip()
                if len(name) > 2:
                    info['name'] = name
                    break

        # Look for student ID
        id_patterns = [
            r'(?:Student\s*)?ID[:\s#]+(\d+)',
            r'#\s*(\d{5,10})',
        ]
        for pattern in id_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['student_id'] = match.group(1).strip()
                break

        return info

    def process_scanned_exam(
        self,
        pdf_path: str,
        template_questions: List[Dict] = None
    ) -> Dict:
        """
        Process a complete scanned exam and extract all information.

        Args:
            pdf_path: Path to the scanned exam PDF.
            template_questions: Optional list of question dicts with 'number' and 'type'.

        Returns:
            Dictionary with:
                - student_info: Name and ID
                - answers: Dict mapping question number to answer
                - ocr_text: Raw OCR text by page
                - confidence: Overall OCR confidence
        """
        # Process the PDF
        ocr_result = self.process_pdf(pdf_path)

        # Extract student info from first page
        first_page = ocr_result['pages'][0] if ocr_result['pages'] else ''
        student_info = self.extract_student_info(first_page)

        # Extract answers from all pages
        full_text = ocr_result['full_text']
        question_count = len(template_questions) if template_questions else None
        answers = self.extract_answers(full_text, question_count)

        return {
            'student_info': student_info,
            'answers': answers,
            'ocr_text': ocr_result['pages'],
            'confidence': ocr_result['confidence'],
            'page_count': ocr_result['page_count']
        }


def create_submission_from_scan(scanned_exam, grading_service=None):
    """
    Create a StudentSubmission from a processed ScannedExam.

    This function:
    1. Creates a StudentSubmission record
    2. Creates QuestionResponse records for each answer
    3. Optionally triggers grading

    Args:
        scanned_exam: ScannedExam model instance with extracted_answers populated.
        grading_service: Optional AIGradingService instance for grading.

    Returns:
        The created StudentSubmission instance.
    """
    from quizzes.models import StudentSubmission, QuestionResponse, QuizSession
    from django.utils import timezone

    quiz = scanned_exam.quiz_session
    if not quiz:
        raise ValueError("ScannedExam must have a quiz_session")

    # Create submission
    submission = StudentSubmission.objects.create(
        quiz_session=quiz,
        student_name=scanned_exam.student_name or 'Unknown',
        student_id=scanned_exam.student_id or '',
        status=StudentSubmission.Status.SUBMITTED,
        submitted_at=timezone.now(),
        attempt_number=1
    )

    # Link to scanned exam
    scanned_exam.submission = submission
    scanned_exam.save(update_fields=['submission'])

    # Create responses for each extracted answer
    questions = list(quiz.questions.all())
    extracted = scanned_exam.extracted_answers or {}

    total_points = 0
    for i, question in enumerate(questions, 1):
        answer_data = None
        q_num_str = str(i)

        if q_num_str in extracted or i in extracted:
            raw_answer = extracted.get(q_num_str) or extracted.get(i)

            # Format answer data based on question type
            if question.question_type == 'multipleChoice':
                answer_data = {'selected': raw_answer}
            elif question.question_type == 'trueFalse':
                answer_data = {'selected': raw_answer.lower() == 'true'}
            else:
                answer_data = {'text': raw_answer}

        QuestionResponse.objects.create(
            submission=submission,
            question=question,
            question_number=i,
            response_data=answer_data or {},
            points_possible=question.points,
            answered_at=timezone.now() if answer_data else None
        )
        total_points += question.points

    submission.total_points_possible = total_points
    submission.save(update_fields=['total_points_possible'])

    # Grade if service provided
    if grading_service:
        grading_service.grade_submission(submission)

    return submission
