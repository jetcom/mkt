#!/usr/bin/env python
"""Import exam templates from INI files into Django database."""

import os
import sys
import re
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from questions.models import Course, QuestionBank
from exams.models import ExamTemplate
from configobj import ConfigObj
from decimal import Decimal


def clean_latex(text):
    """Remove LaTeX formatting from text."""
    if not text:
        return ''
    # Remove LaTeX commands like \vspace{.5cm}
    text = re.sub(r'\\vspace\{[^}]*\}', '', text)
    text = re.sub(r'\\\\', '', text)  # Remove line breaks
    text = text.strip("'")  # Remove surrounding quotes
    return text.strip()


def parse_bool(value):
    """Parse boolean from INI value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', 'yes', '1')
    return bool(value)


def import_exam_templates(questions_dir):
    """Import all exam templates from INI files."""
    imported = 0
    updated = 0
    errors = []

    # Find all INI files
    for root, dirs, files in os.walk(questions_dir):
        for filename in files:
            if not filename.endswith('.ini'):
                continue

            ini_path = os.path.join(root, filename)
            relative_path = os.path.relpath(ini_path, questions_dir)

            try:
                config = ConfigObj(ini_path, encoding='utf-8')

                # Get course number
                course_number = config.get('courseNumber', '')
                if not course_number:
                    continue

                # Get the directory name as potential course code
                dir_name = os.path.basename(root)

                # Normalize course code (CSCI.320 -> csci320)
                course_code = course_number.replace('.', '').lower()

                # Find course - try multiple strategies
                course = None

                # 1. Try directory name first (e.g., csci320-2211)
                try:
                    course = Course.objects.get(code=dir_name)
                except Course.DoesNotExist:
                    pass

                # 2. Try exact match on course number from INI
                if not course:
                    try:
                        course = Course.objects.get(code=course_code)
                    except Course.DoesNotExist:
                        pass

                # 3. Try case-insensitive match
                if not course:
                    try:
                        course = Course.objects.get(code__iexact=course_code)
                    except Course.DoesNotExist:
                        pass

                if not course:
                    errors.append(f"Course {course_code} (dir: {dir_name}) not found for {filename}")
                    continue

                # Extract exam name
                test_name = config.get('test', filename.replace('.ini', ''))

                # Check if template already exists
                template, created = ExamTemplate.objects.update_or_create(
                    course=course,
                    name=test_name,
                    defaults={
                        'instructor': clean_latex(config.get('instructor', '')),
                        'term': config.get('term', ''),
                        'school': config.get('school', 'Rochester Institute of Technology'),
                        'department': config.get('department', 'Department of Computer Science'),
                        'is_quiz': parse_bool(config.get('quiz', False)),
                        'default_points': Decimal(str(config.get('defaultPoints', '2'))),
                        'max_points': Decimal(str(config.get('maxPoints'))) if config.get('maxPoints') else None,
                        'use_checkboxes': parse_bool(config.get('useCheckboxes', True)),
                        'include_id_field': parse_bool(config.get('includeID', True)),
                        'instructions': config.get('note', ''),
                        'default_solution_space': config.get('defaultSolutionSpace', '2.5in'),
                        'default_line_length': config.get('defaultLineLength', '3in'),
                        'source_file': relative_path,
                        'selection_rules': extract_selection_rules(config),
                    }
                )

                if created:
                    imported += 1
                    print(f"  Imported: {course_code} - {test_name}")
                else:
                    updated += 1
                    print(f"  Updated: {course_code} - {test_name}")

            except Exception as e:
                errors.append(f"Error processing {filename}: {str(e)}")

    return imported, updated, errors


def extract_selection_rules(config):
    """Extract question selection rules from INI sections."""
    rules = {}

    # Get the [main] section for includes
    main_section = config.get('main', {})
    if isinstance(main_section, dict):
        include = main_section.get('include', '')
        if include:
            # Parse include paths
            if isinstance(include, list):
                rules['include_files'] = include
            else:
                rules['include_files'] = [f.strip() for f in include.split(',')]

        # Get max points from main section
        if 'maxPoints' in main_section:
            rules['max_points'] = main_section['maxPoints']

    # Look for other sections that might have selection rules
    for section_name in config.sections:
        section = config[section_name]
        if isinstance(section, dict):
            section_rules = {}
            for key in ['maxPoints', 'maxLongPoints', 'maxShortPoints', 'maxTFPoints', 'maxMCPoints', 'include']:
                if key in section:
                    section_rules[key] = section[key]
            if section_rules:
                rules[section_name] = section_rules

    return rules


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python import_exam_templates.py <questions_directory>")
        sys.exit(1)

    questions_dir = sys.argv[1]
    if not os.path.isdir(questions_dir):
        print(f"Directory not found: {questions_dir}")
        sys.exit(1)

    print(f"Importing exam templates from: {questions_dir}")
    print()

    imported, updated, errors = import_exam_templates(questions_dir)

    print()
    print(f"Summary:")
    print(f"  Imported: {imported}")
    print(f"  Updated: {updated}")

    if errors:
        print(f"  Errors: {len(errors)}")
        for err in errors[:10]:
            print(f"    - {err}")
        if len(errors) > 10:
            print(f"    ... and {len(errors) - 10} more")
