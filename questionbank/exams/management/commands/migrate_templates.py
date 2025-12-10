import re
from django.core.management.base import BaseCommand
from exams.models import ExamTemplate


class Command(BaseCommand):
    help = 'Migrate old INI-based templates to new section-based format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        templates = ExamTemplate.objects.all()
        migrated = 0
        skipped = 0

        for template in templates:
            rules = template.selection_rules

            # Skip if already in new format (array of sections)
            if isinstance(rules, list):
                self.stdout.write(f"  Skipping {template.id}: {template.name} (already migrated)")
                skipped += 1
                continue

            # Skip if empty
            if not rules or rules == {}:
                self.stdout.write(f"  Skipping {template.id}: {template.name} (empty rules)")
                skipped += 1
                continue

            # Get course code from the template's course
            course_code = template.course.code if template.course else ''

            new_sections = []

            # Check for include_files format
            if 'include_files' in rules and rules['include_files']:
                include_files = rules['include_files']
                if not isinstance(include_files, list):
                    include_files = [include_files]

                # Extract tags from file paths
                tags = set()
                for file_path in include_files:
                    # Try to extract week number
                    week_match = re.search(r'week(\d+)', file_path, re.IGNORECASE)
                    if week_match:
                        tags.add(f"Week {week_match.group(1)}")
                    else:
                        # Use basename without extension
                        basename = file_path.split('/')[-1].replace('.txt', '')
                        if basename:
                            tags.add(basename)

                if tags:
                    # Get max_points if available
                    max_points = rules.get('max_points', '100')
                    try:
                        count = int(max_points) // 5  # Rough estimate: 5 points per question
                        count = min(max(count, 5), 50)  # Clamp between 5 and 50
                    except (ValueError, TypeError):
                        count = 10

                    new_sections.append({
                        'name': 'Main',
                        'course': course_code,
                        'tags': sorted(list(tags)),
                        'type': '',
                        'count': count
                    })

            # Check for week-based format (week1, week2, etc. as keys)
            elif any(key.startswith('week') for key in rules.keys() if key != 'include_files'):
                for key, value in rules.items():
                    if key.startswith('week') and isinstance(value, dict):
                        week_match = re.search(r'week(\d+)', key, re.IGNORECASE)
                        if week_match:
                            week_num = week_match.group(1)
                            new_sections.append({
                                'name': f'Week {week_num}',
                                'course': course_code,
                                'tags': [f'Week {week_num}'],
                                'type': '',
                                'count': 5
                            })

            if new_sections:
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Would migrate {template.id}: {template.name}"
                        )
                    )
                    self.stdout.write(f"    Old: {rules}")
                    self.stdout.write(f"    New: {new_sections}")
                else:
                    template.selection_rules = new_sections
                    template.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Migrated {template.id}: {template.name} ({len(new_sections)} section(s))"
                        )
                    )
                migrated += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Could not migrate {template.id}: {template.name} - unrecognized format"
                    )
                )
                self.stdout.write(f"    Rules: {rules}")
                skipped += 1

        self.stdout.write('')
        if dry_run:
            self.stdout.write(f"Dry run complete: {migrated} would be migrated, {skipped} skipped")
        else:
            self.stdout.write(self.style.SUCCESS(f"Migration complete: {migrated} migrated, {skipped} skipped"))
