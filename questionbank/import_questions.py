#!/usr/bin/env python3
"""
Import existing questions from the old INI format into the new Django database.

Usage:
    python import_questions.py ../questions
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


def latex_to_markdown(text):
    """Convert common LaTeX constructs to Markdown"""
    if not text:
        return text

    # Handle lstlisting code blocks
    def replace_lstlisting(match):
        code = match.group(1).strip()
        return f'```\n{code}\n```'

    text = re.sub(r'\\begin\{lstlisting\}(.*?)\\end\{lstlisting\}', replace_lstlisting, text, flags=re.DOTALL)

    # Handle verbatim blocks
    text = re.sub(r'\\begin\{verbatim\}(.*?)\\end\{verbatim\}',
                  lambda m: f'```\n{m.group(1).strip()}\n```', text, flags=re.DOTALL)

    # Handle itemize lists
    def replace_itemize(match):
        content = match.group(1)
        items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', content, flags=re.DOTALL)
        md_items = '\n'.join(f'- {item.strip()}' for item in items if item.strip())
        return '\n\n' + md_items  # Add blank line before list for proper Markdown

    text = re.sub(r'\\begin\{itemize\}(.*?)\\end\{itemize\}', replace_itemize, text, flags=re.DOTALL)

    # Handle enumerate lists
    def replace_enumerate(match):
        content = match.group(1)
        items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', content, flags=re.DOTALL)
        md_items = '\n'.join(f'{i+1}. {item.strip()}' for i, item in enumerate(items) if item.strip())
        return '\n\n' + md_items  # Add blank line before list for proper Markdown

    text = re.sub(r'\\begin\{enumerate\}(.*?)\\end\{enumerate\}', replace_enumerate, text, flags=re.DOTALL)

    # Handle images - convert to markdown image syntax
    text = re.sub(r'\\includegraphics\[.*?\]\{(.*?)\}', r'![Image](\1)', text)

    # Handle texttt (monospace)
    text = re.sub(r'\\texttt\{([^}]*)\}', r'`\1`', text)

    # Handle textbf (bold)
    text = re.sub(r'\\textbf\{([^}]*)\}', r'**\1**', text)

    # Handle textit (italic)
    text = re.sub(r'\\textit\{([^}]*)\}', r'*\1*', text)

    # Handle emph (italic)
    text = re.sub(r'\\emph\{([^}]*)\}', r'*\1*', text)

    # Handle underline (markdown doesn't have underline, use bold)
    text = re.sub(r'\\underline\{([^}]*)\}', r'**\1**', text)

    # Handle line breaks
    text = text.replace('\\\\', '  \n')

    # Handle special characters
    text = text.replace('\\#', '#')
    text = text.replace('\\$', '$')
    text = text.replace('\\%', '%')
    text = text.replace('\\&', '&')
    text = text.replace('\\_', '_')
    text = text.replace('\\{', '{')
    text = text.replace('\\}', '}')
    text = text.replace('\\textbackslash', '\\')

    # Handle quotes
    text = text.replace('``', '"')
    text = text.replace("''", '"')

    # Handle horizontal space commands (just remove them)
    text = re.sub(r'\\hspace\{[^}]*\}', ' ', text)
    text = re.sub(r'\\vspace\{[^}]*\}', '', text)

    # Clean up any remaining simple LaTeX commands (but not backslash escapes)
    text = re.sub(r'\\[a-zA-Z]+(?:\{[^}]*\})?', '', text)

    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def parse_question_type(qtype):
    """Map old question types to new ones"""
    type_map = {
        'multiplechoice': 'multipleChoice',
        'tf': 'trueFalse',
        'shortanswer': 'shortAnswer',
        'longanswer': 'longAnswer',
        'matching': 'matching',
        'multipart': 'multipart',
    }
    return type_map.get(qtype.lower(), qtype)


def parse_answer_data(qtype, data):
    """Extract answer data based on question type"""
    qtype = qtype.lower()
    answer_data = {}

    if qtype == 'multiplechoice':
        correct = data.get('correctAnswer', '')
        if isinstance(correct, list):
            correct = correct[0] if correct else ''
        correct = correct.strip('"\'') if isinstance(correct, str) else correct
        answer_data['correct'] = latex_to_markdown(correct) if isinstance(correct, str) else correct

        wrong = data.get('wrongAnswers', [])
        if isinstance(wrong, str):
            wrong = [wrong]
        answer_data['wrong'] = [latex_to_markdown(w.strip('"\'')) for w in wrong]

    elif qtype == 'tf' or qtype == 'truefalse':
        solution = data.get('solution', 'true')
        if isinstance(solution, str):
            answer_data['correct'] = solution.lower() == 'true'
        else:
            answer_data['correct'] = bool(solution)

    elif qtype in ['shortanswer', 'longanswer']:
        # Try 'solution' first, then 'solutions' (both are used in source files)
        solution = data.get('solution', '') or data.get('solutions', '')
        if isinstance(solution, list):
            solution = '\n'.join(solution)
        solution = solution.strip('"\'') if isinstance(solution, str) else str(solution)
        answer_data['solution'] = latex_to_markdown(solution)

    elif qtype == 'matching':
        choices = data.get('choices', [])
        solutions = data.get('solutions', [])
        if isinstance(choices, str):
            choices = [choices]
        if isinstance(solutions, str):
            solutions = [solutions]
        answer_data['choices'] = [latex_to_markdown(c.strip('"\'')) for c in choices]
        answer_data['solutions'] = [latex_to_markdown(s.strip('"\'')) for s in solutions]

    return answer_data


def create_question(bank, text, qtype, points, value, block=None, variant_number=1):
    """Create a single question from parsed data"""
    # Convert LaTeX to Markdown
    text = latex_to_markdown(text)

    # Get answer data
    answer_data = parse_answer_data(qtype, value)

    # Get flags
    is_bonus = str(value.get('bonus', 'false')).lower() == 'true'
    is_required = str(value.get('required', 'false')).lower() == 'true'
    quiz_only = str(value.get('quizOnly', 'false')).lower() == 'true'
    exam_only = str(value.get('examOnly', 'false')).lower() == 'true'

    # Create question
    question, created = Question.objects.get_or_create(
        question_bank=bank,
        text=text,
        defaults={
            'question_type': qtype,
            'points': points,
            'answer_data': answer_data,
            'is_bonus': is_bonus,
            'is_required': is_required,
            'quiz_only': quiz_only,
            'exam_only': exam_only,
            'difficulty': 'medium',
            'block': block,
            'variant_number': variant_number,
        }
    )
    # Update block if it was created before but now we have a block
    if not created and block and not question.block:
        question.block = block
        question.variant_number = variant_number
        question.save(update_fields=['block', 'variant_number'])

    return question, created


def import_questions_from_file(file_path, course, bank):
    """Import questions from a single INI file"""
    try:
        config = ConfigObj(file_path, interpolation=False)
    except Exception as e:
        print(f"  Error parsing {file_path}: {e}")
        return 0

    count = 0
    for key, value in config.items():
        if not isinstance(value, dict):
            continue

        # Check if this is a block with maxQuestions (has nested variants)
        max_questions = value.get('maxQuestions')

        if max_questions is not None:
            # This is a question block with variants
            block, _ = QuestionBlock.objects.get_or_create(
                question_bank=bank,
                name=key,
                defaults={'max_questions': int(max_questions) if max_questions else 1}
            )

            # Look for numbered subsections [[1]], [[2]], etc.
            for subkey, subvalue in value.items():
                if not isinstance(subvalue, dict):
                    continue
                if 'question' not in subvalue:
                    continue

                try:
                    variant_num = int(subkey)
                except ValueError:
                    variant_num = 1

                text = subvalue.get('question', '')
                if isinstance(text, list):
                    text = '\n'.join(text)
                text = text.strip('"\'')

                qtype = subvalue.get('type', 'shortAnswer')
                qtype = parse_question_type(qtype)

                points = subvalue.get('points', subvalue.get('point', 2))
                try:
                    points = float(points)
                except:
                    points = 2.0

                try:
                    question, created = create_question(bank, text, qtype, points, subvalue, block, variant_num)
                    if created:
                        count += 1
                except Exception as e:
                    print(f"  Error creating variant '{key}[{subkey}]': {e}")

        elif 'question' in value:
            # Regular question without variants
            text = value.get('question', '')
            if isinstance(text, list):
                text = '\n'.join(text)
            text = text.strip('"\'')

            qtype = value.get('type', 'shortAnswer')
            qtype = parse_question_type(qtype)

            points = value.get('points', value.get('point', 2))
            try:
                points = float(points)
            except:
                points = 2.0

            try:
                question, created = create_question(bank, text, qtype, points, value)
                if created:
                    count += 1
            except Exception as e:
                print(f"  Error creating question '{key}': {e}")

    return count


def import_course(course_path):
    """Import all questions for a course"""
    course_name = os.path.basename(course_path)

    # Create or get course
    course, _ = Course.objects.get_or_create(
        code=course_name,
        defaults={'name': course_name}
    )
    print(f"\nCourse: {course_name}")

    total = 0

    # Walk through question pool
    pool_path = os.path.join(course_path, 'questionPool')
    if os.path.exists(pool_path):
        for filename in os.listdir(pool_path):
            if filename.startswith('.'):
                continue
            file_path = os.path.join(pool_path, filename)
            if os.path.isfile(file_path):
                # Create question bank for this file
                bank_name = os.path.splitext(filename)[0]
                bank, _ = QuestionBank.objects.get_or_create(
                    course=course,
                    name=bank_name,
                )

                count = import_questions_from_file(file_path, course, bank)
                total += count
                print(f"  {bank_name}: {count} questions")

    # Also check root of course directory
    for filename in os.listdir(course_path):
        if filename.startswith('.') or filename == 'questionPool':
            continue
        file_path = os.path.join(course_path, filename)
        if os.path.isfile(file_path):
            bank_name = os.path.splitext(filename)[0]
            bank, _ = QuestionBank.objects.get_or_create(
                course=course,
                name=bank_name,
            )

            count = import_questions_from_file(file_path, course, bank)
            total += count
            if count > 0:
                print(f"  {bank_name}: {count} questions")

    return total


def main():
    if len(sys.argv) < 2:
        questions_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'questions')
    else:
        questions_path = sys.argv[1]

    if not os.path.exists(questions_path):
        print(f"Error: Questions path not found: {questions_path}")
        sys.exit(1)

    print(f"Importing questions from: {questions_path}")
    print("=" * 50)

    total = 0
    for item in os.listdir(questions_path):
        course_path = os.path.join(questions_path, item)
        if os.path.isdir(course_path) and not item.startswith('.'):
            count = import_course(course_path)
            total += count

    print("=" * 50)
    print(f"Total questions imported: {total}")


if __name__ == '__main__':
    main()
