from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.decorators import action
from django.http import FileResponse, HttpResponse
from django.conf import settings
from .models import ExamTemplate, GeneratedExam, ExamQuestion
from .serializers import ExamTemplateSerializer, ExamTemplateListSerializer, GeneratedExamSerializer, GeneratedExamDetailSerializer
from questions.models import Question, Course
import subprocess
import tempfile
import os
import uuid
import random
import markdown
import re
import zipfile
import io


def latex_to_html(text):
    """Convert common LaTeX constructs to HTML"""
    if not text:
        return text

    # Handle itemize lists
    def replace_itemize(match):
        content = match.group(1)
        items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', content, flags=re.DOTALL)
        html_items = ''.join(f'<li>{item.strip()}</li>' for item in items if item.strip())
        return f'<ul>{html_items}</ul>'

    text = re.sub(r'\\begin\{itemize\}(.*?)\\end\{itemize\}', replace_itemize, text, flags=re.DOTALL)

    # Handle enumerate lists
    def replace_enumerate(match):
        content = match.group(1)
        items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', content, flags=re.DOTALL)
        html_items = ''.join(f'<li>{item.strip()}</li>' for item in items if item.strip())
        return f'<ol>{html_items}</ol>'

    text = re.sub(r'\\begin\{enumerate\}(.*?)\\end\{enumerate\}', replace_enumerate, text, flags=re.DOTALL)

    # Handle texttt (monospace)
    text = re.sub(r'\\texttt\{([^}]*)\}', r'<code>\1</code>', text)

    # Handle textbf (bold)
    text = re.sub(r'\\textbf\{([^}]*)\}', r'<strong>\1</strong>', text)

    # Handle textit (italic)
    text = re.sub(r'\\textit\{([^}]*)\}', r'<em>\1</em>', text)

    # Handle special characters
    text = text.replace('\\#', '#')
    text = text.replace('\\$', '$')
    text = text.replace('\\%', '%')
    text = text.replace('\\&', '&')
    text = text.replace('\\_', '_')
    text = text.replace('\\{', '{')
    text = text.replace('\\}', '}')

    return text


def markdown_to_latex(text):
    """Convert Markdown text to LaTeX for PDF generation"""
    if not text:
        return ''

    # Replace \includegraphics with a placeholder since images may not exist
    # Match both \includegraphics[options]{file} and \includegraphics{file}
    text = re.sub(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}',
                  r'\\textit{[Image: \1]}', text)

    def escape_latex_smart(s):
        """
        Escape special LaTeX characters while preserving:
        - LaTeX math mode ($...$)
        - LaTeX commands (\cmd{...})
        - Already-escaped characters
        """
        result = []
        i = 0
        in_math = False

        while i < len(s):
            ch = s[i]

            # Handle math mode toggle
            if ch == '$':
                # Check if it's an escaped dollar sign
                if i > 0 and s[i-1] == '\\':
                    result.append('$')  # Already escaped
                    i += 1
                    continue
                # Toggle math mode and keep the $
                in_math = not in_math
                result.append(ch)
                i += 1
                continue

            # In math mode, pass everything through unchanged
            if in_math:
                result.append(ch)
                i += 1
                continue

            # Handle backslash sequences
            if ch == '\\' and i + 1 < len(s):
                next_ch = s[i + 1]
                # If it's a known LaTeX escape, keep both chars
                if next_ch in '#$%&_{}^~':
                    result.append(ch)
                    result.append(next_ch)
                    i += 2
                    continue
                # If it's a LaTeX command (backslash + letters), preserve the whole command
                elif next_ch.isalpha():
                    # Extract the full command
                    cmd_start = i
                    i += 1  # skip backslash
                    while i < len(s) and s[i].isalpha():
                        i += 1
                    cmd = s[cmd_start:i]

                    # Check if followed by braced argument(s)
                    while i < len(s) and s[i] == '{':
                        brace_depth = 1
                        i += 1
                        while i < len(s) and brace_depth > 0:
                            if s[i] == '{':
                                brace_depth += 1
                            elif s[i] == '}':
                                brace_depth -= 1
                            i += 1
                        cmd = s[cmd_start:i]

                    result.append(cmd)
                    continue
                else:
                    # Standalone backslash followed by non-alpha - escape it
                    result.append('\\textbackslash{}')
                    i += 1
                    continue

            # Escape special characters outside of LaTeX constructs
            elif ch == '#':
                result.append('\\#')
            elif ch == '%':
                result.append('\\%')
            elif ch == '&':
                result.append('\\&')
            elif ch == '_':
                result.append('\\_')
            elif ch == '^':
                result.append('\\^{}')
            elif ch == '~':
                result.append('\\~{}')
            # Don't escape { } as they may be part of LaTeX structure
            # that wasn't detected (e.g., {\tt ...})
            elif ch == '{':
                # Check if this looks like a LaTeX group
                if i + 1 < len(s) and s[i + 1] == '\\':
                    result.append(ch)  # Keep as-is
                else:
                    result.append(ch)  # Keep as-is, LaTeX will handle
            elif ch == '}':
                result.append(ch)  # Keep as-is
            else:
                result.append(ch)
            i += 1

        return ''.join(result)

    # Process the text line by line to handle Markdown constructs
    lines = text.split('\n')
    result_lines = []
    in_code_block = False
    in_list = False
    list_type = None  # 'itemize' or 'enumerate'

    for line in lines:
        stripped = line.strip()

        # Handle code blocks
        if stripped.startswith('```'):
            if in_code_block:
                result_lines.append('\\end{lstlisting}')
                in_code_block = False
            else:
                result_lines.append('\\begin{lstlisting}')
                in_code_block = True
            continue

        if in_code_block:
            result_lines.append(line)  # Don't escape code
            continue

        # Handle unordered list items
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list or list_type != 'itemize':
                if in_list:
                    result_lines.append(f'\\end{{{list_type}}}')
                result_lines.append('\\begin{itemize}')
                in_list = True
                list_type = 'itemize'
            item_text = escape_latex_smart(stripped[2:])
            result_lines.append(f'\\item {item_text}')
            continue

        # Handle ordered list items
        if re.match(r'^\d+\.\s', stripped):
            if not in_list or list_type != 'enumerate':
                if in_list:
                    result_lines.append(f'\\end{{{list_type}}}')
                result_lines.append('\\begin{enumerate}')
                in_list = True
                list_type = 'enumerate'
            item_text = escape_latex_smart(re.sub(r'^\d+\.\s', '', stripped))
            result_lines.append(f'\\item {item_text}')
            continue

        # End list if we hit a non-list line
        if in_list and stripped:
            result_lines.append(f'\\end{{{list_type}}}')
            in_list = False
            list_type = None

        # Handle headers
        if stripped.startswith('### '):
            result_lines.append(f'\\subsubsection*{{{escape_latex_smart(stripped[4:])}}}')
            continue
        if stripped.startswith('## '):
            result_lines.append(f'\\subsection*{{{escape_latex_smart(stripped[3:])}}}')
            continue
        if stripped.startswith('# '):
            result_lines.append(f'\\section*{{{escape_latex_smart(stripped[2:])}}}')
            continue

        # Handle inline formatting
        processed = stripped

        # Bold **text** -> \textbf{text}
        processed = re.sub(r'\*\*([^*]+)\*\*', lambda m: f'\\textbf{{{escape_latex_smart(m.group(1))}}}', processed)

        # Italic *text* -> \textit{text}
        processed = re.sub(r'\*([^*]+)\*', lambda m: f'\\textit{{{escape_latex_smart(m.group(1))}}}', processed)

        # Inline code `code` -> \texttt{code}
        processed = re.sub(r'`([^`]+)`', lambda m: f'\\texttt{{{escape_latex_smart(m.group(1))}}}', processed)

        # If not a special construct, escape the text
        if not any([
            processed.startswith('\\textbf'),
            processed.startswith('\\textit'),
            processed.startswith('\\texttt'),
            processed.startswith('\\section'),
            processed.startswith('\\subsection'),
            processed.startswith('\\begin'),
            processed.startswith('\\item'),
        ]):
            processed = escape_latex_smart(processed)

        result_lines.append(processed)

    # Close any open list
    if in_list:
        result_lines.append(f'\\end{{{list_type}}}')

    # Close any open code block
    if in_code_block:
        result_lines.append('\\end{lstlisting}')

    return '\n'.join(result_lines)


class ExamTemplateViewSet(viewsets.ModelViewSet):
    queryset = ExamTemplate.objects.select_related('course').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ExamTemplateListSerializer
        return ExamTemplateSerializer

    def get_queryset(self):
        from django.db.models import Q
        user = self.request.user
        if not user.is_authenticated:
            return ExamTemplate.objects.none()

        queryset = ExamTemplate.objects.select_related('course', 'owner').prefetch_related(
            'filter_banks', 'filter_tags'
        )

        # Filter by ownership or sharing
        queryset = queryset.filter(
            Q(owner=user) | Q(shares__shared_with=user) | Q(course__owner=user) | Q(course__shares__shared_with=user)
        ).distinct()

        course = self.request.query_params.get('course')
        if course:
            queryset = queryset.filter(course__code=course)
        is_quiz = self.request.query_params.get('is_quiz')
        if is_quiz is not None:
            queryset = queryset.filter(is_quiz=is_quiz.lower() == 'true')
        return queryset.order_by('course__code', 'name')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share this template with another user (collaboration)"""
        from django.contrib.auth.models import User
        from .models import ExamTemplateShare
        from .serializers import ExamTemplateShareSerializer

        template = self.get_object()
        if template.owner != request.user:
            return Response({'error': 'Only the owner can share'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        permission = request.data.get('permission', 'view')

        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        share, created = ExamTemplateShare.objects.update_or_create(
            template=template,
            shared_with=target_user,
            defaults={'permission': permission, 'shared_by': request.user}
        )
        return Response(ExamTemplateShareSerializer(share).data)

    @action(detail=True, methods=['post'])
    def copy(self, request, pk=None):
        """Create a copy of this template for the current user"""
        template = self.get_object()
        new_name = request.data.get('name', f"{template.name} (copy)")
        new_template = template.copy_to_user(request.user, new_name)
        return Response(ExamTemplateSerializer(new_template).data)

    @action(detail=True, methods=['delete'])
    def unshare(self, request, pk=None):
        """Remove sharing for a user"""
        from .models import ExamTemplateShare
        template = self.get_object()
        if template.owner != request.user:
            return Response({'error': 'Only the owner can manage sharing'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        ExamTemplateShare.objects.filter(template=template, shared_with__username=username).delete()
        return Response({'status': 'unshared'})

    @action(detail=True, methods=['get'])
    def shares(self, request, pk=None):
        """List all shares for this template"""
        from .serializers import ExamTemplateShareSerializer
        template = self.get_object()
        if template.owner != request.user:
            return Response({'error': 'Only the owner can view shares'}, status=status.HTTP_403_FORBIDDEN)
        shares = template.shares.all()
        return Response(ExamTemplateShareSerializer(shares, many=True).data)

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        """Get questions matching this template's filter settings"""
        from questions.models import Question
        from questions.serializers import QuestionListSerializer

        template = self.get_object()

        # Start with questions from the template's course
        queryset = Question.objects.select_related(
            'question_bank__course', 'block'
        ).prefetch_related('tags').filter(
            question_bank__course=template.course,
            canonical__isnull=True  # Only canonical questions
        )

        # Apply filter_banks if set
        if template.filter_banks.exists():
            queryset = queryset.filter(question_bank__in=template.filter_banks.all())

        # Apply filter_weeks if set
        if template.filter_weeks:
            queryset = queryset.filter(week_id__in=template.filter_weeks)

        # Apply filter_question_types if set
        if template.filter_question_types:
            queryset = queryset.filter(question_type__in=template.filter_question_types)

        # Apply filter_tags if set
        if template.filter_tags.exists():
            queryset = queryset.filter(tags__in=template.filter_tags.all()).distinct()

        # Apply filter_difficulty if set
        if template.filter_difficulty:
            queryset = queryset.filter(difficulty=template.filter_difficulty)

        # Order by block/variant for consistent results
        queryset = queryset.order_by('question_bank__name', 'block__name', 'variant_number', 'id')

        # Limit results if max_questions is set
        if template.max_questions:
            queryset = queryset[:template.max_questions]

        return Response(QuestionListSerializer(queryset, many=True).data)


class GeneratedExamViewSet(viewsets.ReadOnlyModelViewSet):
    """View exam generation history"""
    queryset = GeneratedExam.objects.select_related('template__course', 'created_by').all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return GeneratedExamDetailSerializer
        return GeneratedExamSerializer

    def get_queryset(self):
        from django.db.models import Q
        user = self.request.user
        if not user.is_authenticated:
            return GeneratedExam.objects.none()

        queryset = GeneratedExam.objects.select_related(
            'template__course', 'created_by'
        ).filter(
            Q(created_by=user) |
            Q(template__owner=user) |
            Q(template__course__owner=user)
        ).distinct()

        # Filter by template
        template = self.request.query_params.get('template')
        if template:
            queryset = queryset.filter(template_id=template)

        # Filter by course
        course = self.request.query_params.get('course')
        if course:
            queryset = queryset.filter(template__course__code=course)

        return queryset.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent exam generations (last 10)"""
        queryset = self.get_queryset()[:10]
        serializer = GeneratedExamSerializer(queryset, many=True)
        return Response(serializer.data)


class GenerateExamView(APIView):
    """Generate an exam from selected questions"""

    def _latex_to_html(self, text):
        """Convert common LaTeX constructs to HTML"""
        if not text:
            return text

        # Handle lstlisting code blocks
        def replace_lstlisting(match):
            code = match.group(1)
            # Clean up the code
            code = code.strip()
            return f'<pre><code>{code}</code></pre>'

        text = re.sub(r'\\begin\{lstlisting\}(.*?)\\end\{lstlisting\}', replace_lstlisting, text, flags=re.DOTALL)

        # Handle verbatim blocks
        text = re.sub(r'\\begin\{verbatim\}(.*?)\\end\{verbatim\}',
                      lambda m: f'<pre><code>{m.group(1).strip()}</code></pre>', text, flags=re.DOTALL)

        # Handle itemize lists
        def replace_itemize(match):
            content = match.group(1)
            items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', content, flags=re.DOTALL)
            html_items = ''.join(f'<li>{item.strip()}</li>' for item in items if item.strip())
            return f'<ul>{html_items}</ul>'

        text = re.sub(r'\\begin\{itemize\}(.*?)\\end\{itemize\}', replace_itemize, text, flags=re.DOTALL)

        # Handle enumerate lists
        def replace_enumerate(match):
            content = match.group(1)
            items = re.findall(r'\\item\s*(.*?)(?=\\item|$)', content, flags=re.DOTALL)
            html_items = ''.join(f'<li>{item.strip()}</li>' for item in items if item.strip())
            return f'<ol>{html_items}</ol>'

        text = re.sub(r'\\begin\{enumerate\}(.*?)\\end\{enumerate\}', replace_enumerate, text, flags=re.DOTALL)

        # Handle images - convert to placeholder note
        text = re.sub(r'\\includegraphics\[.*?\]\{(.*?)\}',
                      r'<em>[Image: \1]</em>', text)

        # Handle texttt (monospace)
        text = re.sub(r'\\texttt\{([^}]*)\}', r'<code>\1</code>', text)

        # Handle textbf (bold)
        text = re.sub(r'\\textbf\{([^}]*)\}', r'<strong>\1</strong>', text)

        # Handle textit (italic)
        text = re.sub(r'\\textit\{([^}]*)\}', r'<em>\1</em>', text)

        # Handle emph (italic)
        text = re.sub(r'\\emph\{([^}]*)\}', r'<em>\1</em>', text)

        # Handle underline
        text = re.sub(r'\\underline\{([^}]*)\}', r'<u>\1</u>', text)

        # Handle line breaks
        text = text.replace('\\\\', '<br>')

        # Handle special characters
        text = text.replace('\\#', '#')
        text = text.replace('\\$', '$')
        text = text.replace('\\%', '%')
        text = text.replace('\\&', '&amp;')
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

        # Clean up any remaining simple LaTeX commands
        text = re.sub(r'\\[a-zA-Z]+\s*', '', text)

        return text

    def post(self, request):
        question_ids = request.data.get('question_ids', [])
        title = request.data.get('title', 'Exam')
        course_code = request.data.get('course', '')
        instructor = request.data.get('instructor', '')
        term = request.data.get('term', '')
        date = request.data.get('date', '')
        instructions = self._latex_to_html(request.data.get('instructions', ''))
        shuffle = request.data.get('shuffle', True)
        include_answers = request.data.get('include_answers', False)
        output_format = request.data.get('format', 'pdf')  # 'pdf', 'html', 'markdown'
        # Quiz mode options
        is_quiz = request.data.get('is_quiz', False)
        include_id = request.data.get('include_id', False)
        split_mc = request.data.get('split_mc', False)
        # Answer formatting options
        default_line_length = request.data.get('line_length', '3in')
        default_solution_space = request.data.get('solution_space', '1.5in')
        question_overrides = request.data.get('question_overrides', {})

        if not question_ids:
            return Response({'error': 'No questions selected'}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch questions
        questions = list(Question.objects.filter(id__in=question_ids))
        if shuffle:
            random.shuffle(questions)

        # Get template ID if provided (for history tracking)
        template_id = request.data.get('template_id')

        # Generate exam content
        if output_format == 'markdown':
            content = self._generate_markdown(questions, title, course_code, instructor, term, date, instructions, include_answers)
            return Response({'content': content, 'format': 'markdown'})

        elif output_format == 'html':
            html_content = self._generate_professional_html(
                questions, title, course_code, instructor, term, date,
                instructions, include_answers, department=request.data.get('department', '')
            )
            return Response({'content': html_content, 'format': 'html'})

        elif output_format == 'pdf':
            # Use LaTeX exam class for professional output
            # Convert markdown instructions to LaTeX
            raw_instructions = markdown_to_latex(request.data.get('instructions', ''))
            num_versions = int(request.data.get('versions', 1))
            version_letters = 'ABCDEFGHIJ'

            try:
                if num_versions == 1:
                    if include_answers:
                        # Single version with answer key - return ZIP with exam and key
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            # Generate exam PDF (without answers)
                            exam_latex = self._generate_latex(
                                questions, title, course_code, instructor, term, date,
                                raw_instructions, False,
                                department=request.data.get('department', ''),
                                school=request.data.get('school', ''),
                                course_name=request.data.get('course_name', ''),
                                is_quiz=is_quiz,
                                include_id=include_id,
                                split_mc=split_mc,
                                default_line_length=default_line_length,
                                default_solution_space=default_solution_space,
                                question_overrides=question_overrides
                            )
                            exam_pdf_path = self._latex_to_pdf_compile(exam_latex, title)
                            with open(exam_pdf_path, 'rb') as f:
                                zip_file.writestr(f"{title.replace(' ', '_')}.pdf", f.read())

                            # Generate answer key PDF
                            key_latex = self._generate_latex(
                                questions, title, course_code, instructor, term, date,
                                raw_instructions, True,
                                department=request.data.get('department', ''),
                                school=request.data.get('school', ''),
                                course_name=request.data.get('course_name', ''),
                                is_quiz=is_quiz,
                                include_id=include_id,
                                split_mc=split_mc,
                                default_line_length=default_line_length,
                                default_solution_space=default_solution_space,
                                question_overrides=question_overrides
                            )
                            key_pdf_path = self._latex_to_pdf_compile(key_latex, f"{title}_key")
                            with open(key_pdf_path, 'rb') as f:
                                zip_file.writestr(f"{title.replace(' ', '_')}_key.pdf", f.read())

                        # Record the generated exam for history
                        self._record_generated_exam(
                            request, template_id, title, questions,
                            version=None, include_answers=include_answers
                        )

                        zip_buffer.seek(0)
                        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
                        response['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}.zip"'
                        return response
                    else:
                        # Single version without answer key - return PDF directly
                        latex_content = self._generate_latex(
                            questions, title, course_code, instructor, term, date,
                            raw_instructions, False,
                            department=request.data.get('department', ''),
                            school=request.data.get('school', ''),
                            course_name=request.data.get('course_name', ''),
                            is_quiz=is_quiz,
                            include_id=include_id,
                            split_mc=split_mc,
                            default_line_length=default_line_length,
                            default_solution_space=default_solution_space,
                            question_overrides=question_overrides
                        )
                        pdf_path = self._latex_to_pdf_compile(latex_content, title)

                        # Record the generated exam for history
                        self._record_generated_exam(
                            request, template_id, title, questions,
                            version=None, include_answers=False
                        )

                        response = FileResponse(
                            open(pdf_path, 'rb'),
                            content_type='application/pdf',
                            as_attachment=True,
                            filename=f"{title.replace(' ', '_')}.pdf"
                        )
                        return response
                else:
                    # Multiple versions - create ZIP with all PDFs
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for v in range(num_versions):
                            version = version_letters[v]
                            # Shuffle questions for each version
                            version_questions = list(questions)
                            if shuffle:
                                random.shuffle(version_questions)

                            # Generate exam PDF
                            latex_content = self._generate_latex(
                                version_questions, title, course_code, instructor, term, date,
                                raw_instructions, False,  # Exam without answers
                                department=request.data.get('department', ''),
                                school=request.data.get('school', ''),
                                course_name=request.data.get('course_name', ''),
                                is_quiz=is_quiz,
                                include_id=include_id,
                                split_mc=split_mc,
                                default_line_length=default_line_length,
                                default_solution_space=default_solution_space,
                                question_overrides=question_overrides,
                                version=version
                            )
                            pdf_path = self._latex_to_pdf_compile(latex_content, f"{title}_v{version}")
                            with open(pdf_path, 'rb') as f:
                                zip_file.writestr(f"{title.replace(' ', '_')}_v{version}.pdf", f.read())

                            # Generate answer key PDF
                            if include_answers:
                                key_latex = self._generate_latex(
                                    version_questions, title, course_code, instructor, term, date,
                                    raw_instructions, True,  # With answers
                                    department=request.data.get('department', ''),
                                    school=request.data.get('school', ''),
                                    course_name=request.data.get('course_name', ''),
                                    is_quiz=is_quiz,
                                    include_id=include_id,
                                    split_mc=split_mc,
                                    default_line_length=default_line_length,
                                    default_solution_space=default_solution_space,
                                    question_overrides=question_overrides,
                                    version=version
                                )
                                key_pdf_path = self._latex_to_pdf_compile(key_latex, f"{title}_v{version}_key")
                                with open(key_pdf_path, 'rb') as f:
                                    zip_file.writestr(f"{title.replace(' ', '_')}_v{version}_key.pdf", f.read())

                    # Record each version for history
                    for v in range(num_versions):
                        version = version_letters[v]
                        version_questions = list(questions)
                        self._record_generated_exam(
                            request, template_id, title, version_questions,
                            version=version, include_answers=include_answers
                        )

                    zip_buffer.seek(0)
                    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
                    response['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}_versions.zip"'
                    return response

            except Exception as e:
                return Response({'error': f'PDF generation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'error': 'Invalid format'}, status=status.HTTP_400_BAD_REQUEST)

    def _generate_markdown(self, questions, title, course_code, instructor, term, date, instructions, include_answers):
        """Generate exam in Markdown format"""
        lines = []

        # Header
        lines.append(f"# {title}")
        lines.append("")
        if course_code:
            lines.append(f"**Course:** {course_code}")
        if instructor:
            lines.append(f"**Instructor:** {instructor}")
        if term:
            lines.append(f"**Term:** {term}")
        if date:
            lines.append(f"**Date:** {date}")
        lines.append("")

        # Calculate total points
        total_points = sum(float(q.points) for q in questions)
        lines.append(f"**Total Points:** {total_points}")
        lines.append("")

        # Instructions
        if instructions:
            lines.append("## Instructions")
            lines.append(instructions)
            lines.append("")

        # Name field
        lines.append("---")
        lines.append("")
        lines.append("**Name:** ________________________________")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Group questions by type
        mc_questions = [q for q in questions if q.question_type == 'multipleChoice']
        tf_questions = [q for q in questions if q.question_type == 'trueFalse']
        sa_questions = [q for q in questions if q.question_type == 'shortAnswer']
        la_questions = [q for q in questions if q.question_type == 'longAnswer']
        other_questions = [q for q in questions if q.question_type not in ['multipleChoice', 'trueFalse', 'shortAnswer', 'longAnswer']]

        question_num = 1

        # Multiple Choice
        if mc_questions:
            lines.append("## Multiple Choice")
            lines.append("")
            for q in mc_questions:
                lines.extend(self._format_mc_question(q, question_num, include_answers))
                question_num += 1
            lines.append("")

        # True/False
        if tf_questions:
            lines.append("## True/False")
            lines.append("")
            for q in tf_questions:
                lines.extend(self._format_tf_question(q, question_num, include_answers))
                question_num += 1
            lines.append("")

        # Short Answer
        if sa_questions:
            lines.append("## Short Answer")
            lines.append("")
            for q in sa_questions:
                lines.extend(self._format_sa_question(q, question_num, include_answers))
                question_num += 1
            lines.append("")

        # Long Answer
        if la_questions:
            lines.append("## Long Answer / Essay")
            lines.append("")
            for q in la_questions:
                lines.extend(self._format_la_question(q, question_num, include_answers))
                question_num += 1
            lines.append("")

        # Other types
        if other_questions:
            lines.append("## Other Questions")
            lines.append("")
            for q in other_questions:
                lines.extend(self._format_generic_question(q, question_num, include_answers))
                question_num += 1

        return "\n".join(lines)

    def _format_mc_question(self, q, num, include_answers):
        lines = []
        lines.append(f"**{num}.** ({q.points} pts) {q.text}")
        lines.append("")

        answer_data = q.answer_data or {}
        correct = answer_data.get('correct', '')
        wrong = answer_data.get('wrong', [])

        # Combine and shuffle answers
        all_answers = [correct] + wrong
        random.shuffle(all_answers)

        for i, ans in enumerate(all_answers):
            letter = chr(65 + i)  # A, B, C, D...
            marker = ""
            if include_answers and ans == correct:
                marker = " **[CORRECT]**"
            lines.append(f"   {letter}. {ans}{marker}")

        lines.append("")
        return lines

    def _format_tf_question(self, q, num, include_answers):
        lines = []
        lines.append(f"**{num}.** ({q.points} pts) {q.text}")
        lines.append("")

        answer_data = q.answer_data or {}
        correct = answer_data.get('correct', True)

        if include_answers:
            answer_str = "True" if correct else "False"
            lines.append(f"   **Answer: {answer_str}**")
        else:
            lines.append("   [ ] True    [ ] False")

        lines.append("")
        return lines

    def _format_sa_question(self, q, num, include_answers):
        lines = []
        lines.append(f"**{num}.** ({q.points} pts) {q.text}")
        lines.append("")

        if include_answers:
            answer_data = q.answer_data or {}
            solution = answer_data.get('solution', '')
            lines.append(f"   **Answer:** {solution}")
        else:
            lines.append("   _____________________________________________")
            lines.append("")
            lines.append("   _____________________________________________")

        lines.append("")
        return lines

    def _format_la_question(self, q, num, include_answers):
        lines = []
        lines.append(f"**{num}.** ({q.points} pts) {q.text}")
        lines.append("")

        if include_answers:
            answer_data = q.answer_data or {}
            solution = answer_data.get('solution', '')
            lines.append(f"   **Answer:** {solution}")
        else:
            # Add blank lines for writing
            for _ in range(8):
                lines.append("")
                lines.append("   _____________________________________________")

        lines.append("")
        lines.append("")
        return lines

    def _format_generic_question(self, q, num, include_answers):
        lines = []
        lines.append(f"**{num}.** ({q.points} pts) {q.text}")
        lines.append("")

        if include_answers and q.answer_data:
            lines.append(f"   **Answer Data:** {q.answer_data}")

        lines.append("")
        return lines

    def _generate_professional_html(self, questions, title, course_code, instructor, term, date, instructions, include_answers, department=''):
        """Generate professional exam HTML that looks like LaTeX exam class output"""
        total_points = sum(float(q.points) for q in questions)

        # Group questions by type
        mc_questions = [q for q in questions if q.question_type == 'multipleChoice']
        tf_questions = [q for q in questions if q.question_type == 'trueFalse']
        sa_questions = [q for q in questions if q.question_type == 'shortAnswer']
        la_questions = [q for q in questions if q.question_type == 'longAnswer']
        other_questions = [q for q in questions if q.question_type not in ['multipleChoice', 'trueFalse', 'shortAnswer', 'longAnswer']]

        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        @page {{
            size: letter;
            margin: 0.75in;
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 11pt;
            line-height: 1.4;
            max-width: 8in;
            margin: 0 auto;
            padding: 0.5in;
            color: #000;
        }}

        /* Cover Page */
        .cover-page {{
            text-align: center;
            page-break-after: always;
            min-height: 90vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .institution {{
            font-variant: small-caps;
            font-size: 18pt;
            margin-bottom: 1.5cm;
        }}
        .course-name {{
            font-variant: small-caps;
            font-size: 18pt;
            margin-bottom: 1cm;
        }}
        .term {{
            font-variant: small-caps;
            font-size: 18pt;
            margin-bottom: 2cm;
        }}
        .exam-title {{
            font-size: 32pt;
            font-weight: bold;
            margin-bottom: 3cm;
        }}
        .score-box {{
            font-size: 14pt;
            margin-bottom: 4cm;
        }}
        .name-line {{
            font-size: 12pt;
            text-align: left;
            margin-top: 2cm;
        }}
        .name-line span {{
            display: inline-block;
            width: 4in;
            border-bottom: 1px solid #000;
            margin-left: 0.5em;
        }}

        /* Section Headers */
        .section-header {{
            font-size: 14pt;
            font-weight: bold;
            text-align: center;
            margin: 30px 0 20px 0;
            page-break-before: always;
        }}
        .section-header:first-of-type {{
            page-break-before: auto;
        }}
        .section-instructions {{
            border: 2px solid #000;
            padding: 15px;
            margin: 0 auto 25px auto;
            max-width: 5.5in;
            text-align: center;
            font-size: 10pt;
        }}

        /* Questions */
        .question {{
            margin-bottom: 25px;
            page-break-inside: avoid;
        }}
        .question-header {{
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .question-number {{
            font-weight: bold;
        }}
        .points {{
            font-weight: normal;
        }}
        .question-text {{
            margin-bottom: 12px;
            white-space: pre-wrap;
        }}

        /* Multiple Choice */
        .choices {{
            margin-left: 20px;
            list-style: none;
            padding: 0;
        }}
        .choices li {{
            margin: 6px 0;
            display: flex;
            align-items: flex-start;
        }}
        .choice-letter {{
            font-weight: bold;
            margin-right: 8px;
            min-width: 20px;
        }}
        .checkbox {{
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 1.5px solid #000;
            margin-right: 8px;
            flex-shrink: 0;
        }}

        /* True/False */
        .tf-choices {{
            margin-left: 20px;
            margin-top: 10px;
        }}
        .tf-choice {{
            display: inline-block;
            margin-right: 30px;
        }}

        /* Answer Lines */
        .answer-line {{
            border-bottom: 1px solid #000;
            min-width: 3in;
            display: inline-block;
            margin: 8px 0;
        }}
        .answer-space {{
            min-height: 2in;
            border: 1px solid #ccc;
            margin: 10px 0;
            background: #fafafa;
        }}
        .long-answer-lines {{
            margin-top: 15px;
        }}
        .long-answer-lines .answer-line {{
            display: block;
            width: 100%;
            margin: 20px 0;
        }}

        /* Code blocks */
        pre, code {{
            font-family: 'Courier New', Courier, monospace;
            font-size: 10pt;
            background: #f5f5f5;
            padding: 2px 4px;
        }}
        pre {{
            padding: 12px;
            border: 1px solid #ddd;
            overflow-x: auto;
            white-space: pre;
            margin: 10px 0;
        }}

        /* Answers (for answer key) */
        .answer {{
            color: #c00;
            font-weight: bold;
            margin-top: 8px;
            padding: 8px;
            background: #fff0f0;
            border-left: 3px solid #c00;
        }}
        .correct-marker {{
            color: #c00;
            font-weight: bold;
        }}

        /* Footer */
        .page-footer {{
            position: fixed;
            bottom: 0.5in;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 9pt;
            border-top: 1px solid #000;
            padding-top: 5px;
        }}

        /* Print styles */
        @media print {{
            body {{
                padding: 0;
            }}
            .section-header {{
                page-break-before: always;
            }}
            .question {{
                page-break-inside: avoid;
            }}
            .answer-space {{
                background: white;
                border: none;
            }}
            .long-answer-lines .answer-line {{
                margin: 25px 0;
            }}
        }}
    </style>
</head>
<body>
    <!-- Cover Page -->
    <div class="cover-page">
        <div class="institution">{department or 'Department of Computer Science'}</div>
        <div class="course-name">{course_code}</div>
        <div class="term">{term}</div>
        <div class="exam-title">{title}</div>
        <div class="score-box">
            Score: <span style="display:inline-block;width:1in;border-bottom:1px solid #000;"></span> / {int(total_points)}
        </div>
        <div class="name-line">
            Name: <span></span>
        </div>
    </div>
'''

        question_num = 1

        # Long Answer Section
        if la_questions:
            html += '''
    <div class="section-header">Long Answer Questions</div>
    <div class="section-instructions">
        Answer the questions in the spaces provided. If you run out of room, continue on the back of the page.
    </div>
'''
            for q in la_questions:
                html += self._format_html_la_question(q, question_num, include_answers)
                question_num += 1

        # Short Answer Section
        if sa_questions:
            html += '''
    <div class="section-header">Short Answer Questions</div>
    <div class="section-instructions">
        Write the correct answer in the space provided next to the question.
    </div>
'''
            for q in sa_questions:
                html += self._format_html_sa_question(q, question_num, include_answers)
                question_num += 1

        # Multiple Choice Section
        if mc_questions:
            html += '''
    <div class="section-header">Multiple Choice Questions</div>
    <div class="section-instructions">
        Select the best answer for each question.
    </div>
'''
            for q in mc_questions:
                html += self._format_html_mc_question(q, question_num, include_answers)
                question_num += 1

        # True/False Section
        if tf_questions:
            html += '''
    <div class="section-header">True/False Questions</div>
    <div class="section-instructions">
        Mark True or False for each statement.
    </div>
'''
            for q in tf_questions:
                html += self._format_html_tf_question(q, question_num, include_answers)
                question_num += 1

        # Other questions
        if other_questions:
            html += '''
    <div class="section-header">Additional Questions</div>
'''
            for q in other_questions:
                html += self._format_html_generic_question(q, question_num, include_answers)
                question_num += 1

        html += '''
</body>
</html>'''
        return html

    def _markdown_to_html_content(self, text):
        """Convert Markdown text to HTML for display in exam"""
        if not text:
            return text
        # Use the markdown library to convert
        return markdown.markdown(text, extensions=['fenced_code', 'tables'])

    def _format_html_mc_question(self, q, num, include_answers):
        """Format multiple choice question as HTML"""
        answer_data = q.answer_data or {}
        correct = answer_data.get('correct', '')
        wrong = answer_data.get('wrong', [])

        # Combine and shuffle answers
        all_answers = [(correct, True)] + [(w, False) for w in wrong]
        random.shuffle(all_answers)

        choices_html = ''
        for i, (ans, is_correct) in enumerate(all_answers):
            letter = chr(65 + i)
            marker = ' <span class="correct-marker">[CORRECT]</span>' if include_answers and is_correct else ''
            ans_html = self._markdown_to_html_content(str(ans))
            # Remove <p> tags for inline display
            ans_html = re.sub(r'^<p>(.*)</p>$', r'\1', ans_html.strip())
            choices_html += f'''
            <li><span class="checkbox"></span><span class="choice-letter">{letter}.</span> {ans_html}{marker}</li>'''

        question_text = self._markdown_to_html_content(q.text)

        return f'''
    <div class="question">
        <div class="question-header">
            <span class="question-number">{num}.</span> <span class="points">({q.points} pts)</span>
        </div>
        <div class="question-text">{question_text}</div>
        <ul class="choices">{choices_html}
        </ul>
    </div>
'''

    def _format_html_tf_question(self, q, num, include_answers):
        """Format true/false question as HTML"""
        answer_data = q.answer_data or {}
        correct = answer_data.get('correct', True)

        answer_html = ''
        if include_answers:
            answer_str = "True" if correct else "False"
            answer_html = f'<div class="answer">Answer: {answer_str}</div>'
        else:
            answer_html = '''
        <div class="tf-choices">
            <span class="tf-choice"><span class="checkbox"></span> True</span>
            <span class="tf-choice"><span class="checkbox"></span> False</span>
        </div>'''

        question_text = self._markdown_to_html_content(q.text)

        return f'''
    <div class="question">
        <div class="question-header">
            <span class="question-number">{num}.</span> <span class="points">({q.points} pts)</span>
        </div>
        <div class="question-text">{question_text}</div>
        {answer_html}
    </div>
'''

    def _format_html_sa_question(self, q, num, include_answers):
        """Format short answer question as HTML"""
        answer_data = q.answer_data or {}
        solution = answer_data.get('solution', '')

        if include_answers:
            solution_html = self._markdown_to_html_content(str(solution))
            answer_html = f'<div class="answer">Answer: {solution_html}</div>'
        else:
            answer_html = '<div class="answer-line"></div>'

        question_text = self._markdown_to_html_content(q.text)

        return f'''
    <div class="question">
        <div class="question-header">
            <span class="question-number">{num}.</span> <span class="points">({q.points} pts)</span>
        </div>
        <div class="question-text">{question_text}</div>
        {answer_html}
    </div>
'''

    def _format_html_la_question(self, q, num, include_answers):
        """Format long answer question as HTML"""
        answer_data = q.answer_data or {}
        solution = answer_data.get('solution', '')

        if include_answers:
            solution_html = self._markdown_to_html_content(str(solution))
            answer_html = f'<div class="answer">Answer: {solution_html}</div>'
        else:
            # Multiple answer lines for writing
            answer_html = '<div class="long-answer-lines">'
            for _ in range(6):
                answer_html += '<div class="answer-line"></div>'
            answer_html += '</div>'

        question_text = self._markdown_to_html_content(q.text)

        return f'''
    <div class="question">
        <div class="question-header">
            <span class="question-number">{num}.</span> <span class="points">({q.points} pts)</span>
        </div>
        <div class="question-text">{question_text}</div>
        {answer_html}
    </div>
'''

    def _format_html_generic_question(self, q, num, include_answers):
        """Format generic question as HTML"""
        import html as html_module
        answer_html = ''
        if include_answers and q.answer_data:
            answer_html = f'<div class="answer">Answer: {html_module.escape(str(q.answer_data))}</div>'
        else:
            answer_html = '<div class="answer-line"></div>'

        question_text = self._markdown_to_html_content(q.text)

        return f'''
    <div class="question">
        <div class="question-header">
            <span class="question-number">{num}.</span> <span class="points">({q.points} pts)</span>
        </div>
        <div class="question-text">{question_text}</div>
        {answer_html}
    </div>
'''

    def _markdown_to_html(self, md_content, title):
        """Convert Markdown to styled HTML (legacy, kept for compatibility)"""
        html_body = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Georgia', serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            line-height: 1.6;
        }}
        h1 {{
            text-align: center;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }}
        h2 {{
            margin-top: 30px;
            color: #333;
            border-bottom: 1px solid #ccc;
        }}
        p {{
            margin: 10px 0;
        }}
        hr {{
            margin: 20px 0;
        }}
        pre, code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            padding: 15px;
            overflow-x: auto;
        }}
        @media print {{
            body {{
                margin: 0;
                padding: 20px;
            }}
            h2 {{
                page-break-before: auto;
            }}
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""
        return html

    def _html_to_pdf(self, html_content, title):
        """Convert HTML to PDF using available tools"""
        import shutil

        # Create temp HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as html_file:
            html_file.write(html_content)
            html_path = html_file.name

        pdf_path = html_path.replace('.html', '.pdf')
        errors = []

        try:
            # Try wkhtmltopdf first (best CSS support)
            if shutil.which('wkhtmltopdf'):
                result = subprocess.run(
                    [
                        'wkhtmltopdf',
                        '--page-size', 'Letter',
                        '--margin-top', '0.75in',
                        '--margin-bottom', '0.75in',
                        '--margin-left', '0.75in',
                        '--margin-right', '0.75in',
                        '--enable-local-file-access',
                        html_path,
                        pdf_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0 and os.path.exists(pdf_path):
                    return pdf_path
                errors.append(f"wkhtmltopdf: {result.stderr}")

            # Try weasyprint (good CSS support, Python-based)
            if shutil.which('weasyprint'):
                result = subprocess.run(
                    ['weasyprint', html_path, pdf_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0 and os.path.exists(pdf_path):
                    return pdf_path
                errors.append(f"weasyprint: {result.stderr}")

            # Try pandoc with different engines
            if shutil.which('pandoc'):
                # Try pdflatex first (most common)
                for engine in ['pdflatex', 'xelatex', 'lualatex']:
                    result = subprocess.run(
                        [
                            'pandoc',
                            html_path,
                            '-o', pdf_path,
                            f'--pdf-engine={engine}',
                            '-V', 'geometry:margin=1in',
                        ],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0 and os.path.exists(pdf_path):
                        return pdf_path
                    errors.append(f"pandoc/{engine}: {result.stderr[:200]}")

            # No tool worked
            raise Exception(f"No PDF tool available. Install wkhtmltopdf: brew install wkhtmltopdf. Errors: {'; '.join(errors)}")

        finally:
            # Clean up HTML file
            if os.path.exists(html_path):
                os.unlink(html_path)

    def _generate_latex(self, questions, title, course_code, instructor, term, date, instructions, include_answers, department='', school='', course_name='', is_quiz=False, include_id=False, split_mc=False, default_line_length='3in', default_solution_space='1.5in', question_overrides=None, version=None):
        """Generate LaTeX source using the exam document class - matches mkt.py output"""
        if question_overrides is None:
            question_overrides = {}
        total_points = sum(int(float(q.points)) for q in questions)

        # Version string for headers
        version_str = f" - Version {version}" if version else ""

        # Use course_name if provided, otherwise fall back to course_code
        cover_course_name = course_name or course_code or ''

        # Group questions by type
        mc_questions = [q for q in questions if q.question_type == 'multipleChoice']
        tf_questions = [q for q in questions if q.question_type == 'trueFalse']
        sa_questions = [q for q in questions if q.question_type == 'shortAnswer']
        la_questions = [q for q in questions if q.question_type == 'longAnswer']

        # Build LaTeX document
        answers_opt = 'answers,' if include_answers else ''

        latex = f'''% Generated by Question Bank
\\documentclass[10pt,{answers_opt}addpoints]{{exam}}

\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{textcomp}}
\\usepackage{{amssymb}}
\\usepackage{{graphicx}}
\\usepackage{{listings}}
\\usepackage{{tabularx}}
\\usepackage{{mathtools}}
\\usepackage{{wasysym}}
\\usepackage{{color}}
\\DeclareUnicodeCharacter{{03C3}}{{\\ensuremath{{\\sigma}}}}
\\DeclareUnicodeCharacter{{03C0}}{{\\ensuremath{{\\pi}}}}
\\DeclareUnicodeCharacter{{2192}}{{\\ensuremath{{\\rightarrow}}}}
\\DeclareUnicodeCharacter{{2190}}{{\\ensuremath{{\\leftarrow}}}}
\\DeclareUnicodeCharacter{{2019}}{{'}}
\\DeclareUnicodeCharacter{{2018}}{{`}}
\\DeclareUnicodeCharacter{{201C}}{{``}}
\\DeclareUnicodeCharacter{{201D}}{{''}}

\\makeatletter
\\ifcase \\@ptsize \\relax % 10pt
\\newcommand{{\\miniscule}}{{\\@setfontsize\\miniscule{{4}}{{5}}}}% \\tiny: 5/6
\\or% 11pt
\\newcommand{{\\miniscule}}{{\\@setfontsize\\miniscule{{5}}{{6}}}}% \\tiny: 6/7
\\or% 12pt
\\newcommand{{\\miniscule}}{{\\@setfontsize\\miniscule{{5}}{{6}}}}% \\tiny: 6/7
\\fi
\\makeatother
\\pagestyle{{headandfoot}}
\\firstpageheader{{{title}{version_str}}} {{}} {{}}
\\runningheader{{{title}{version_str}}} {{}} {{}}
\\firstpagefooter{{{course_code}}} {{Page \\thepage\\ of \\numpages}} {{\\makebox[.5in]{{\\hrulefill}}/\\pointsonpage{{\\thepage}}}}
\\runningfooter{{{course_code}}} {{Page \\thepage\\ of \\numpages}} {{\\makebox[.5in]{{\\hrulefill}}/\\pointsonpage{{\\thepage}}}}

\\CorrectChoiceEmphasis{{\\color{{red}}}}
\\SolutionEmphasis{{\\color{{red}}}}
\\renewcommand{{\\questionshook}}{{\\setlength{{\\itemsep}}{{.35in}}}}
\\bonuspointpoints{{bonus point}}{{bonus points}}
\\colorsolutionboxes
\\definecolor{{SolutionBoxColor}}{{gray}}{{1.0}}

\\begin{{document}}
'''

        if is_quiz:
            # Quiz mode: compact header matching mkt.py format
            # Override headers for quiz format
            latex = f'''% Generated by Question Bank - Quiz Mode
\\documentclass[10pt,{answers_opt}addpoints]{{exam}}

\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{textcomp}}
\\usepackage{{amssymb}}
\\usepackage{{graphicx}}
\\usepackage{{listings}}
\\usepackage{{tabularx}}
\\usepackage{{mathtools}}
\\usepackage{{wasysym}}
\\usepackage{{color}}
\\DeclareUnicodeCharacter{{03C3}}{{\\ensuremath{{\\sigma}}}}
\\DeclareUnicodeCharacter{{03C0}}{{\\ensuremath{{\\pi}}}}
\\DeclareUnicodeCharacter{{2192}}{{\\ensuremath{{\\rightarrow}}}}
\\DeclareUnicodeCharacter{{2190}}{{\\ensuremath{{\\leftarrow}}}}
\\DeclareUnicodeCharacter{{2019}}{{'}}
\\DeclareUnicodeCharacter{{2018}}{{`}}
\\DeclareUnicodeCharacter{{201C}}{{``}}
\\DeclareUnicodeCharacter{{201D}}{{''}}

\\makeatletter
\\ifcase \\@ptsize \\relax % 10pt
\\newcommand{{\\miniscule}}{{\\@setfontsize\\miniscule{{4}}{{5}}}}% \\tiny: 5/6
\\or% 11pt
\\newcommand{{\\miniscule}}{{\\@setfontsize\\miniscule{{5}}{{6}}}}% \\tiny: 6/7
\\or% 12pt
\\newcommand{{\\miniscule}}{{\\@setfontsize\\miniscule{{5}}{{6}}}}% \\tiny: 6/7
\\fi
\\makeatother
\\pagestyle{{headandfoot}}
'''
            # Quiz header with name line - matching mkt.py format
            title_with_version = f"{title}{version_str}"
            if include_answers:
                latex += f'\\firstpageheader{{Name: \\textcolor{{red}}{{KEY}} }} {{}} {{{title_with_version}}}\n'
                latex += f'\\runningheader{{}} {{ \\textcolor{{red}}{{KEY}} }} {{{title_with_version}}}\n'
            else:
                if include_id:
                    latex += f'\\firstpageheader{{ Name: \\makebox[3in]{{\\hrulefill}}}} {{\\hspace{{3in}}ID: \\makebox[1.5in]{{\\hrulefill}}}} {{{title_with_version}}}\n'
                else:
                    latex += f'\\firstpageheader{{ Name: \\makebox[5in]{{\\hrulefill}}}} {{}} {{{title_with_version}}}\n'
                latex += f'\\runningheader{{}} {{}} {{{title_with_version}}}\n'

            latex += f'''\\firstpagefooter{{{course_code}}} {{Page \\thepage\\ of \\numpages}} {{\\makebox[.5in]{{\\hrulefill}}/\\pointsonpage{{\\thepage}}}}
\\runningfooter{{{course_code}}} {{Page \\thepage\\ of \\numpages}} {{\\makebox[.5in]{{\\hrulefill}}/\\pointsonpage{{\\thepage}}}}

\\checkedchar{{\\textcolor{{red}}{{$\\CIRCLE$}}}}
\\SolutionEmphasis{{\\color{{red}}}}
\\renewcommand{{\\questionshook}}{{\\setlength{{\\itemsep}}{{.35in}}}}
\\bonuspointpoints{{bonus point}}{{bonus points}}
\\colorsolutionboxes
\\definecolor{{SolutionBoxColor}}{{gray}}{{1.0}}

\\begin{{document}}
'''
            # Add note/instructions if provided
            if instructions:
                latex += f'{instructions}\n'

            latex += '\\begin{questions}\n'
        else:
            # Full exam mode: cover page
            latex += '''\\begin{coverpages}
\\begin{center}
\\vspace*{1in}


'''
            # Build cover page dynamically to avoid LaTeX errors with empty fields
            # School and Department line
            if school or department:
                if school and department:
                    latex += f'\\textsc{{\\LARGE {school} \\\\{department} }}\\\\[1.5cm]\n'
                elif school:
                    latex += f'\\textsc{{\\LARGE {school} }}\\\\[1.5cm]\n'
                else:
                    latex += f'\\textsc{{\\LARGE {department} }}\\\\[1.5cm]\n'

            # Course name line
            if cover_course_name:
                latex += f'\\textsc{{\\LARGE {cover_course_name}}}\\\\[1cm]\n'

            # Term line
            if term:
                latex += f'\\textsc{{\\LARGE {term}}}\\\\[1cm]\n'

            # Instructor line (no line break spacing after - mkt.py style)
            if instructor:
                latex += f'{instructor}\n'

            # Title (always required) - Huge with 1cm spacing
            latex += f'\\textsc{{\\Huge {title}}}\\\\[1cm]\n'

            # Version line (if multiple versions)
            if version:
                latex += f'\\textsc{{\\LARGE Version: {version}}}\\\\[1cm]\n'

            # Instructions/Note
            if instructions:
                latex += f'{instructions}\n'

            latex += '''\\vfill


'''
            if include_answers:
                latex += '{\\Large { Score: \\makebox[1in]{\\underline{\\hspace{5mm}\\textcolor{red}{KEY} \\hspace{5mm}}} / \\numpoints }} \\\\[4cm]\n'
            else:
                latex += '{\\Large { Score: \\makebox[1in]{\\hrulefill} / \\numpoints }} \\\\[4cm]\n'

            latex += '''\\end{center}
'''
            if include_answers:
                latex += '\\makebox[\\textwidth]{\\textcolor{red}{KEY}}\n'
            elif include_id:
                latex += '\\makebox[0.60\\textwidth]{Name: \\enspace\\hrulefill}\n'
                latex += '\\makebox[0.40\\textwidth]{ID: \\enspace\\hrulefill}\n'
            else:
                latex += '\\makebox[\\textwidth]{Name: \\enspace\\hrulefill}\n'

            # Exam ID at bottom (miniscule)
            exam_uuid = str(uuid.uuid4())
            latex += f'\\covercfoot{{\\miniscule{{ Exam ID: {exam_uuid}}}}}\n'

            latex += '''\\end{coverpages}

\\shipout\\null
\\begin{questions}
'''

        # Long Answer Questions
        if la_questions:
            if not is_quiz:
                latex += '''\\newpage
\\fullwidth{\\centering\\Large\\textbf{Long Answer Questions}}
\\fullwidth{\\fbox{\\fbox{\\parbox{5.5in}{\\centering
Answer the questions in the spaces provided on the question sheets.
If you run out of room for an answer, continue on the back page.
}}}}
\\vspace{1em}

'''
            latex += '\\begingradingrange{longanswer}\n'
            for q in la_questions:
                points = int(float(q.points))
                question_text = markdown_to_latex(q.text)
                solution = (q.answer_data or {}).get('solution', '')
                # Use exam builder override first, then question-specific, then default
                q_override = question_overrides.get(str(q.id), {})
                solution_space = q_override.get('solutionSpace') or (q.answer_data or {}).get('solutionSpace') or default_solution_space

                # Wrap in minipage to prevent page breaks
                latex += '\\par\\vspace{0.1in}\\begin{minipage}{\\linewidth}\n'
                latex += f'\\question[{points}]\n{question_text}\n'

                if solution:
                    solution_text = markdown_to_latex(solution)
                    latex += f'\\begin{{solutionbox}}{{{solution_space}}}\n{solution_text}\n\\end{{solutionbox}}\n'
                else:
                    latex += f'\\begin{{solutionbox}}{{{solution_space}}}\n\\end{{solutionbox}}\n'

                latex += '\\end{minipage}\n\n'

            latex += '\\endgradingrange{longanswer}\n\n'

        # Short Answer Questions
        if sa_questions:
            if not is_quiz:
                latex += '''\\newpage
\\fullwidth{\\centering\\Large\\textbf{Short Answer Questions}}
\\fullwidth{\\fbox{\\fbox{\\parbox{5.5in}{\\centering
Write the correct answer in the space provided next to the question.
Answers that are not legible or not made in the space provided will result in a 0 for that question.
}}}}
\\vspace{1em}

'''
            latex += '\\begingradingrange{shortAnswer}\n'
            for q in sa_questions:
                points = int(float(q.points))
                question_text = markdown_to_latex(q.text)
                answer_data = q.answer_data or {}
                solution = answer_data.get('solution', '')
                # Use exam builder override first, then question-specific, then default
                q_override = question_overrides.get(str(q.id), {})
                line_length = q_override.get('lineLength') or answer_data.get('lineLength') or default_line_length
                line_count = q_override.get('lineCount') or answer_data.get('lineCount') or 1

                # Wrap in minipage
                latex += '\\par\\vspace{0.1in}\\begin{minipage}{\\linewidth}\n'
                latex += '\\vspace{.35cm}'
                latex += f'\\question[{points}]\n{question_text}\n'
                latex += '\\vspace{.25cm}'
                latex += f'\\setlength\\answerlinelength{{{line_length}}}\n'

                if solution:
                    # If multiple lines expected, split solution by comma for display
                    if line_count > 1 and ',' in solution:
                        solutions = [s.strip() for s in solution.split(',')]
                        for sol in solutions:
                            solution_text = markdown_to_latex(str(sol))
                            latex += f'\\answerline[\\textcolor{{red}}{{{solution_text}}}]\n'
                    else:
                        solution_text = markdown_to_latex(str(solution))
                        latex += f'\\answerline[\\textcolor{{red}}{{{solution_text}}}]\n'
                else:
                    # Render multiple blank answer lines if lineCount specified
                    for _ in range(int(line_count)):
                        latex += '\\answerline\n'

                latex += '\\end{minipage}\n\n'

            latex += '\\endgradingrange{shortanswer}\n\n'

        # True/False Questions
        if tf_questions:
            if not is_quiz:
                latex += '''\\newpage
\\fullwidth{\\centering\\Large\\textbf{True/False Questions}}
\\fullwidth{\\fbox{\\fbox{\\parbox{5.5in}{\\centering
Circle either 'True' or 'False' at the beginning of the line. If you make an
incorrect mark, erase your mark and clearly mark the correct answer.
If the intended mark is not clear, you will receive a 0 for that question.
}}}}
\\vspace{1em}

'''
            latex += '\\begingradingrange{TF}\n'
            for q in tf_questions:
                points = int(float(q.points))
                correct = (q.answer_data or {}).get('correct', True)
                question_text = markdown_to_latex(q.text)

                # Wrap in minipage
                latex += '\\par\\vspace{0.1in}\\begin{minipage}{\\linewidth}\n'
                latex += f'\\question[{points}]\n'

                if is_quiz:
                    # Quiz mode: compact inline True/False with bubbles on the right
                    latex += f'{question_text}\n'
                    latex += '\\ifprintanswers\n'
                    if correct:
                        latex += '\\hfill\\textbf{\\textcolor{red}{$\\CIRCLE$} True \\hspace{2mm}$\\ocircle$ False}\n'
                    else:
                        latex += '\\hfill\\textbf{$\\ocircle$ True \\hspace{2mm}\\textcolor{red}{$\\CIRCLE$} False}\n'
                    latex += '\\else\n'
                    latex += '\\hfill\\textbf{$\\ocircle$ True \\hspace{2mm}$\\ocircle$ False}\n'
                    latex += '\\fi\n'
                else:
                    # Exam mode: Circle True/False at beginning
                    latex += '\\ifprintanswers\n'
                    if correct:
                        latex += '\\textbf{[ \\textcolor{red}{True} / False ]} '
                    else:
                        latex += '\\textbf{[ True / \\textcolor{red}{False} ]} '
                    latex += '\\else\n'
                    latex += '\\textbf{[ True / False ]} '
                    latex += '\\fi\n'
                    latex += f'{question_text}\n'
                latex += '\\medskip\n'
                latex += '\\end{minipage}\n\n'

            latex += '\\endgradingrange{TF}\n\n'

        # Multiple Choice Questions
        if mc_questions:
            if not is_quiz:
                latex += '''\\newpage
\\fullwidth{\\centering\\Large\\textbf{Multiple Choice Questions}}
\\fullwidth{\\fbox{\\fbox{\\parbox{5.5in}{\\centering
Write the \\textit{best} answer in the space provided next to the question.
Answers that are not legible or not made in the space provided will result in a 0 for that question.
}}}}
\\vspace{1em}

'''
            latex += '\\begingradingrange{multipleChoice}\n'
            for q in mc_questions:
                points = int(float(q.points))
                answer_data = q.answer_data or {}
                correct = answer_data.get('correct', '')
                wrong = answer_data.get('wrong', [])

                question_text = markdown_to_latex(q.text)

                # Wrap in minipage
                latex += '\\par\\vspace{0.1in}\\begin{minipage}{\\linewidth}\n'
                latex += f'\\question[{points}]\n{question_text}\n'
                latex += '\\medskip\n'

                # Combine and shuffle answers, track correct answer letter
                all_answers = [(correct, True)] + [(w, False) for w in wrong]
                random.shuffle(all_answers)

                if is_quiz:
                    # Quiz mode: use checkboxes with 2-column layout (matching mkt.py)
                    latex += '\\\\ \\begin{oneparcheckboxes}\n'

                    # Check if any answer is long (needs full-width)
                    line_break_on_each = any(len(str(ans)) > 30 for ans, _ in all_answers)

                    count = 0
                    for ans, is_correct in all_answers:
                        count += 1
                        ans_text = markdown_to_latex(str(ans))
                        if is_correct:
                            latex += f'\\CorrectChoice \\makebox[5cm][l]{{{ans_text}}}\n'
                        else:
                            latex += f'\\choice \\makebox[5cm][l]{{{ans_text}}}\n'
                        # Line break after every 2 answers (or each if long answers)
                        if (count % 2 == 0 or line_break_on_each) and count != len(all_answers):
                            latex += '\\\\\n'

                    latex += '\\end{oneparcheckboxes}\n'
                else:
                    # Exam mode: regular choices with answer line
                    latex += '\\begin{choices}\n'

                    current_letter = 'A'
                    correct_letter = 'A'
                    for ans, is_correct in all_answers:
                        ans_text = markdown_to_latex(str(ans))
                        latex += f'\\choice {ans_text}\n'
                        if is_correct:
                            correct_letter = current_letter
                        current_letter = chr(ord(current_letter) + 1)

                    latex += '\\end{choices}\n'

                    # Add answer line for exam mode
                    latex += '\\setlength\\answerlinelength{1in}\n'
                    latex += f'\\answerline[{correct_letter}]\n'

                latex += '\\end{minipage}\n\n'

            latex += '\\endgradingrange{multiplechoice}\n\n'

        latex += '''\\end{questions}
\\end{document}
'''
        return latex

    def _latex_to_pdf_compile(self, latex_content, title):
        """Compile LaTeX to PDF using pdflatex"""
        import shutil

        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        tex_path = os.path.join(temp_dir, 'exam.tex')
        pdf_path = os.path.join(temp_dir, 'exam.pdf')

        try:
            # Write LaTeX file
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)

            # Find pdflatex
            pdflatex = shutil.which('pdflatex')
            if not pdflatex:
                # Try common locations (macOS and Linux)
                for path in [
                    '/Library/TeX/texbin/pdflatex',  # macOS MacTeX
                    '/usr/local/texlive/2023/bin/x86_64-darwin/pdflatex',  # macOS alternate
                    '/usr/bin/pdflatex',  # Linux texlive
                ]:
                    if os.path.exists(path):
                        pdflatex = path
                        break

            if not pdflatex:
                raise Exception("pdflatex not found. Install texlive (Linux) or MacTeX (macOS)")

            # Run pdflatex twice (for cross-references)
            for _ in range(2):
                result = subprocess.run(
                    [pdflatex, '-halt-on-error', '-interaction=nonstopmode', 'exam.tex'],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode != 0:
                    # Read log for error details
                    log_path = os.path.join(temp_dir, 'exam.log')
                    error_msg = result.stderr
                    if os.path.exists(log_path):
                        with open(log_path, 'r') as f:
                            log_content = f.read()
                            # Find error lines
                            import re
                            errors = re.findall(r'!.*', log_content)
                            if errors:
                                error_msg = '\n'.join(errors[:5])
                    raise Exception(f"pdflatex error: {error_msg}")

            if not os.path.exists(pdf_path):
                raise Exception("PDF file was not created")

            # Copy to a more permanent temp location
            final_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            final_pdf.close()
            shutil.copy2(pdf_path, final_pdf.name)

            return final_pdf.name

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _markdown_to_pdf(self, md_content, title):
        """Convert Markdown to PDF using pandoc (legacy, kept for compatibility)"""
        # Create temp files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as md_file:
            md_file.write(md_content)
            md_path = md_file.name

        pdf_path = md_path.replace('.md', '.pdf')

        try:
            # Try pandoc first
            result = subprocess.run(
                [
                    'pandoc',
                    md_path,
                    '-o', pdf_path,
                    '--pdf-engine=xelatex',
                    '-V', 'geometry:margin=1in',
                    '-V', 'fontsize=11pt',
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                # Try with pdflatex if xelatex not available
                result = subprocess.run(
                    [
                        'pandoc',
                        md_path,
                        '-o', pdf_path,
                        '--pdf-engine=pdflatex',
                        '-V', 'geometry:margin=1in',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

            if result.returncode != 0:
                raise Exception(f"Pandoc error: {result.stderr}")

            return pdf_path

        finally:
            # Clean up markdown file
            if os.path.exists(md_path):
                os.unlink(md_path)

    def _record_generated_exam(self, request, template_id, title, questions, version=None, include_answers=False):
        """Record a generated exam in the database for history tracking"""
        try:
            template = None
            if template_id:
                template = ExamTemplate.objects.filter(id=template_id).first()

            # If no template, try to find or create one based on course
            if not template and questions:
                course = questions[0].question_bank.course
                # Try to find an existing template with this title
                template = ExamTemplate.objects.filter(
                    name=title,
                    course=course
                ).first()

            if not template:
                return  # Skip recording if no template context

            # Create the generated exam record
            generated = GeneratedExam.objects.create(
                template=template,
                version=version or '',
                total_points=sum(float(q.points) for q in questions),
                question_count=len(questions),
                created_by=request.user if request.user.is_authenticated else None
            )

            # Link questions with ordering
            for i, q in enumerate(questions):
                ExamQuestion.objects.create(
                    exam=generated,
                    question=q,
                    order=i + 1
                )

            # Update question usage stats
            from django.utils import timezone
            now = timezone.now()
            for q in questions:
                q.times_used += 1
                q.last_used = now
                q.save(update_fields=['times_used', 'last_used'])

        except Exception as e:
            # Log but don't fail the exam generation
            print(f"Failed to record generated exam: {e}")


class ExamPreviewView(APIView):
    """Preview exam without generating file"""

    def post(self, request):
        question_ids = request.data.get('question_ids', [])

        if not question_ids:
            return Response({'error': 'No questions selected'}, status=status.HTTP_400_BAD_REQUEST)

        questions = Question.objects.filter(id__in=question_ids).select_related('question_bank__course')

        preview_data = {
            'question_count': questions.count(),
            'total_points': sum(float(q.points) for q in questions),
            'by_type': {},
            'questions': []
        }

        for q in questions:
            qtype = q.question_type
            if qtype not in preview_data['by_type']:
                preview_data['by_type'][qtype] = {'count': 0, 'points': 0}
            preview_data['by_type'][qtype]['count'] += 1
            preview_data['by_type'][qtype]['points'] += float(q.points)

            preview_data['questions'].append({
                'id': q.id,
                'type': q.question_type,
                'text': q.text[:200] + '...' if len(q.text) > 200 else q.text,
                'points': float(q.points),
                'course': q.question_bank.course.code,
            })

        return Response(preview_data)
