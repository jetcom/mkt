#!/usr/bin/env python3
"""
Import quiz pool files from the quizPool directory into the Django database.
Each file becomes a tag (e.g., week1.txt -> "Week 1" tag)

Usage:
    python import_quiz_pool.py ../questions/csci320-2211/quizPool
"""

import os
import sys
import re
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from questions.models import Course, QuestionBank, Question, QuestionBlock, Tag

# Add parent directory to import configobj
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from configobj import ConfigObj


def parse_quiz_pool_file(filepath):
    """Parse a quiz pool .txt file and return questions grouped by section."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Parse as ConfigObj (INI format)
    try:
        config = ConfigObj(filepath, encoding='utf-8')
    except Exception as e:
        print(f"  Error parsing {filepath}: {e}")
        return []

    questions = []

    for section_name, section_data in config.items():
        if not isinstance(section_data, dict):
            continue

        max_questions = section_data.get('maxQuestions', None)

        # Each numbered subsection is a question variant
        for key, q_data in section_data.items():
            if not isinstance(q_data, dict):
                continue
            if not key.isdigit():
                continue

            q_type = q_data.get('type', 'shortAnswer')
            q_text = q_data.get('question', '')
            points = float(q_data.get('points', 1))

            # Handle different answer formats
            answer_data = {}
            if q_type == 'TF':
                q_type = 'trueFalse'
                solution = q_data.get('solution', '')
                answer_data['correct'] = solution.lower() == 'true'
            elif q_type == 'multipleChoice':
                answer_data['correct'] = q_data.get('correctAnswer', '')
                wrong = q_data.get('wrongAnswers', [])
                if isinstance(wrong, str):
                    wrong = [wrong]
                answer_data['wrong'] = list(wrong)
            else:
                solution = q_data.get('solution', '')
                if isinstance(solution, list):
                    solution = ', '.join(solution)
                answer_data['solution'] = solution

            questions.append({
                'section': section_name,
                'max_questions': int(max_questions) if max_questions else None,
                'type': q_type,
                'text': q_text.strip('"\''),
                'points': points,
                'answer_data': answer_data,
                'variant': int(key)
            })

    return questions


def import_quiz_pool(pool_dir, course_code):
    """Import all quiz pool files from a directory."""

    # Get or create course
    course, _ = Course.objects.get_or_create(
        code=course_code,
        defaults={'name': course_code}
    )

    # Get or create question bank for quiz pool
    bank, _ = QuestionBank.objects.get_or_create(
        course=course,
        name='quizPool',
        defaults={'description': 'Imported from quizPool files'}
    )

    # Process each .txt file
    for filename in sorted(os.listdir(pool_dir)):
        if not filename.endswith('.txt'):
            continue

        filepath = os.path.join(pool_dir, filename)
        base_name = filename[:-4]  # Remove .txt

        # Create tag from filename (e.g., "week1" -> "Week 1")
        tag_name = base_name
        if base_name.startswith('week'):
            week_num = base_name[4:]
            tag_name = f"Week {week_num}"

        tag, _ = Tag.objects.get_or_create(
            name=tag_name,
            defaults={'color': '#10b981'}
        )

        print(f"\nProcessing {filename} -> Tag: {tag_name}")

        questions = parse_quiz_pool_file(filepath)
        if not questions:
            print(f"  No questions found in {filename}")
            continue

        # Group by section for block creation
        sections = {}
        for q in questions:
            section = q['section']
            if section not in sections:
                sections[section] = []
            sections[section].append(q)

        imported_count = 0
        for section_name, section_qs in sections.items():
            # Create block if section has multiple variants
            block = None
            max_questions = section_qs[0].get('max_questions', 1)

            if len(section_qs) > 1 or max_questions:
                block, created = QuestionBlock.objects.get_or_create(
                    question_bank=bank,
                    name=f"{base_name}: {section_name}",
                    defaults={'max_questions': max_questions or 1}
                )

            for idx, q in enumerate(section_qs):
                # Check if question already exists (by text hash)
                existing = Question.objects.filter(
                    question_bank=bank,
                    text=q['text']
                ).first()

                if existing:
                    # Just add tag
                    existing.tags.add(tag)
                    continue

                # Create question
                question = Question.objects.create(
                    question_bank=bank,
                    block=block,
                    variant_number=idx + 1,
                    question_type=q['type'],
                    text=q['text'],
                    points=q['points'],
                    answer_data=q['answer_data'],
                    difficulty='medium'
                )
                question.tags.add(tag)
                imported_count += 1

        print(f"  Imported {imported_count} new questions, tagged with '{tag_name}'")

    print(f"\nDone! Questions imported to bank: {course_code}/quizPool")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_quiz_pool.py <pool_directory> [course_code]")
        print("Example: python import_quiz_pool.py ../questions/csci320-2211/quizPool csci320-2211")
        sys.exit(1)

    pool_dir = sys.argv[1]

    # Try to detect course code from path
    course_code = sys.argv[2] if len(sys.argv) > 2 else None
    if not course_code:
        # Extract from path like .../csci320-2211/quizPool
        parts = pool_dir.rstrip('/').split('/')
        if len(parts) >= 2:
            course_code = parts[-2]
        else:
            course_code = 'unknown'

    if not os.path.isdir(pool_dir):
        print(f"Error: {pool_dir} is not a directory")
        sys.exit(1)

    import_quiz_pool(pool_dir, course_code)
