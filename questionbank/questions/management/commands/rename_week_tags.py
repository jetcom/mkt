"""
Management command to rename week tags that are off by one.

Usage:
    python manage.py rename_week_tags --course csci251-2255 --dry-run
    python manage.py rename_week_tags --course csci251-2255
"""
import re
from django.core.management.base import BaseCommand
from questions.models import Tag, Question


class Command(BaseCommand):
    help = 'Rename week tags that are off by one (e.g., week03-foo -> week2-foo)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course',
            type=str,
            required=True,
            help='Course code to filter tags (e.g., csci251-2255)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be renamed without making changes'
        )

    def handle(self, *args, **options):
        course_code = options['course']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made\n'))

        # Get tags used in this course
        tags = Tag.objects.filter(
            questions__question_bank__course__code=course_code
        ).distinct().order_by('name')

        if not tags.exists():
            self.stdout.write(self.style.ERROR(f'No tags found for course {course_code}'))
            return

        self.stdout.write(f'Found {tags.count()} tags for course {course_code}\n')

        # Pattern: week followed by number(s), optionally with leading zeros
        # e.g., week03-foo, week-03-foo, week04-bar, week10-baz
        pattern = re.compile(r'^week-?(\d+)-?(.*)$', re.IGNORECASE)

        renames = []
        for tag in tags:
            match = pattern.match(tag.name)
            if match:
                week_num = int(match.group(1))
                suffix = match.group(2)

                # Subtract 1 from week number
                new_week_num = week_num - 1

                if new_week_num < 1:
                    self.stdout.write(f'  SKIP: {tag.name} (would become week0 or negative)')
                    continue

                # Preserve original formatting (leading zeros and hyphen style)
                original_num_str = match.group(1)
                new_num_str = str(new_week_num).zfill(len(original_num_str))

                # Detect if original had hyphen after 'week'
                has_hyphen_after_week = tag.name.lower().startswith('week-')

                if has_hyphen_after_week:
                    if suffix:
                        new_name = f'week-{new_num_str}-{suffix}'
                    else:
                        new_name = f'week-{new_num_str}'
                else:
                    if suffix:
                        new_name = f'week{new_num_str}-{suffix}'
                    else:
                        new_name = f'week{new_num_str}'

                if new_name != tag.name:
                    renames.append((tag, tag.name, new_name))

        if not renames:
            self.stdout.write(self.style.WARNING('No tags need renaming'))
            return

        self.stdout.write(f'\nTags to rename ({len(renames)}):')
        for tag, old_name, new_name in renames:
            self.stdout.write(f'  {old_name} -> {new_name}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run complete. Run without --dry-run to apply changes.'))
            return

        # Apply renames
        self.stdout.write('\nApplying renames...')
        for tag, old_name, new_name in renames:
            # Check if target name already exists
            if Tag.objects.filter(name=new_name).exists():
                self.stdout.write(self.style.ERROR(f'  CONFLICT: {new_name} already exists, skipping {old_name}'))
                continue

            tag.name = new_name
            tag.save()
            self.stdout.write(self.style.SUCCESS(f'  Renamed: {old_name} -> {new_name}'))

        self.stdout.write(self.style.SUCCESS('\nDone!'))
