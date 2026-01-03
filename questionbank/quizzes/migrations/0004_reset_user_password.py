from django.db import migrations
from django.contrib.auth.hashers import make_password


def reset_password(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    try:
        user = User.objects.get(email='jxbvcs@rit.edu')
        user.password = make_password('84wndbac')
        user.save()
    except User.DoesNotExist:
        pass  # User doesn't exist, nothing to do


def reverse_reset_password(apps, schema_editor):
    # Cannot reverse a password reset
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0003_add_quiz_invitation'),
    ]

    operations = [
        migrations.RunPython(reset_password, reverse_reset_password),
    ]
