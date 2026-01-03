from django.db import migrations


def transfer_ownership(apps, schema_editor):
    """Transfer all data ownership to jxbvcs@rit.edu"""
    User = apps.get_model('auth', 'User')
    Course = apps.get_model('questions', 'Course')
    QuestionBank = apps.get_model('questions', 'QuestionBank')
    Question = apps.get_model('questions', 'Question')
    ExamTemplate = apps.get_model('exams', 'ExamTemplate')
    QuizSession = apps.get_model('quizzes', 'QuizSession')

    try:
        target_user = User.objects.get(email='jxbvcs@rit.edu')
    except User.DoesNotExist:
        return

    # Transfer ownership of all courses
    Course.objects.all().update(owner=target_user)

    # Transfer ownership of all question banks
    QuestionBank.objects.all().update(owner=target_user)

    # Transfer created_by for questions
    Question.objects.all().update(created_by=target_user)

    # Transfer ownership of exam templates
    ExamTemplate.objects.all().update(owner=target_user, created_by=target_user)

    # Transfer created_by for quiz sessions
    QuizSession.objects.all().update(created_by=target_user)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0006_ensure_user_exists'),
        ('questions', '0008_add_soft_delete'),
        ('exams', '0005_add_type_constraints'),
    ]

    operations = [
        migrations.RunPython(transfer_ownership, noop),
    ]
