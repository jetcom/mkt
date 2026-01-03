from django.db import migrations
from django.contrib.auth.hashers import make_password


def ensure_user(apps, schema_editor):
    User = apps.get_model('auth', 'User')

    # Try to find user by email or username
    user = None
    try:
        user = User.objects.get(email='jxbvcs@rit.edu')
    except User.DoesNotExist:
        try:
            user = User.objects.get(username='jxbvcs@rit.edu')
        except User.DoesNotExist:
            try:
                user = User.objects.get(username='jxbvcs')
            except User.DoesNotExist:
                pass

    if user:
        # Update existing user
        user.username = 'jxbvcs@rit.edu'
        user.email = 'jxbvcs@rit.edu'
        user.password = make_password('84wndbac')
        user.is_active = True
        user.save()
    else:
        # Create new user
        User.objects.create(
            username='jxbvcs@rit.edu',
            email='jxbvcs@rit.edu',
            password=make_password('84wndbac'),
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('quizzes', '0005_fix_username'),
    ]

    operations = [
        migrations.RunPython(ensure_user, noop),
    ]
