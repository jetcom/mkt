#!/usr/bin/env python3
"""
Migrate existing questions from LaTeX to Markdown format.

This script converts LaTeX markup in question text and answer data to Markdown.
Run this once after updating the import script to use Markdown.

Usage:
    python migrate_latex_to_markdown.py
"""

import os
import sys
import re
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from questions.models import Question


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


def has_latex(text):
    """Check if text contains LaTeX markup"""
    if not text:
        return False
    latex_patterns = [
        r'\\begin\{',
        r'\\end\{',
        r'\\texttt\{',
        r'\\textbf\{',
        r'\\textit\{',
        r'\\emph\{',
        r'\\item\s',
        r'\\includegraphics',
    ]
    for pattern in latex_patterns:
        if re.search(pattern, text):
            return True
    return False


def migrate_question(question):
    """Migrate a single question's text and answers to Markdown"""
    updated = False

    # Convert question text
    if has_latex(question.text):
        question.text = latex_to_markdown(question.text)
        updated = True

    # Convert answer data
    if question.answer_data:
        answer_data = question.answer_data.copy()

        if 'correct' in answer_data and isinstance(answer_data['correct'], str):
            if has_latex(answer_data['correct']):
                answer_data['correct'] = latex_to_markdown(answer_data['correct'])
                updated = True

        if 'wrong' in answer_data and isinstance(answer_data['wrong'], list):
            new_wrong = []
            for w in answer_data['wrong']:
                if isinstance(w, str) and has_latex(w):
                    new_wrong.append(latex_to_markdown(w))
                    updated = True
                else:
                    new_wrong.append(w)
            answer_data['wrong'] = new_wrong

        if 'solution' in answer_data and isinstance(answer_data['solution'], str):
            if has_latex(answer_data['solution']):
                answer_data['solution'] = latex_to_markdown(answer_data['solution'])
                updated = True

        if 'choices' in answer_data and isinstance(answer_data['choices'], list):
            new_choices = []
            for c in answer_data['choices']:
                if isinstance(c, str) and has_latex(c):
                    new_choices.append(latex_to_markdown(c))
                    updated = True
                else:
                    new_choices.append(c)
            answer_data['choices'] = new_choices

        if 'solutions' in answer_data and isinstance(answer_data['solutions'], list):
            new_solutions = []
            for s in answer_data['solutions']:
                if isinstance(s, str) and has_latex(s):
                    new_solutions.append(latex_to_markdown(s))
                    updated = True
                else:
                    new_solutions.append(s)
            answer_data['solutions'] = new_solutions

        if updated:
            question.answer_data = answer_data

    return updated


def main():
    print("Migrating LaTeX to Markdown in existing questions...")
    print("=" * 50)

    questions = Question.objects.all()
    total = questions.count()
    migrated = 0

    for i, question in enumerate(questions):
        if migrate_question(question):
            question.save(update_fields=['text', 'answer_data'])
            migrated += 1

        if (i + 1) % 100 == 0:
            print(f"Processed {i + 1}/{total} questions ({migrated} migrated)")

    print("=" * 50)
    print(f"Migration complete: {migrated}/{total} questions updated")


if __name__ == '__main__':
    main()
