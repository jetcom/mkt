from django.db import migrations
from django.contrib.auth.hashers import make_password


def fix_username_and_password(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    try:
        user = User.objects.get(email='jxbvcs@rit.edu')
        user.username = 'jxbvcs@rit.edu'
        user.password = make_password('84wndbac')
        user.save()
    except User.DoesNotExist:
        pass  # User doesn't exist, nothing to do


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0004_reset_user_password'),
    ]

    operations = [
        migrations.RunPython(fix_username_and_password, noop),
    ]
