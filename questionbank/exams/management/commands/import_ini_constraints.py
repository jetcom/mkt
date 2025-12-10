import os
import re
import configparser
from django.core.management.base import BaseCommand
from exams.models import ExamTemplate


class Command(BaseCommand):
    help = 'Import constraints from INI files to update templates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--ini-dir',
            default='/Users/jsb/Library/CloudStorage/Dropbox/src/mkt/questions',
            help='Directory containing course question folders with INI files',
        )

    def parse_ini_file(self, filepath):
        """Parse an INI file and extract section constraints."""
        config = configparser.ConfigParser()
        # Handle files that might not have proper section headers
        try:
            with open(filepath, 'r') as f:
                content = f.read()

            # Parse global settings (before any [section])
            global_settings = {}
            lines = content.split('\n')
            in_section = False
            sections = {}
            current_section = None

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith(';'):
                    continue

                # Check for section header
                section_match = re.match(r'\[(\w+)\]', line)
                if section_match:
                    in_section = True
                    current_section = section_match.group(1)
                    sections[current_section] = {}
                    continue

                # Parse key=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"\'')

                    if in_section and current_section:
                        sections[current_section][key] = value
                    else:
                        global_settings[key] = value

            return global_settings, sections
        except Exception as e:
            self.stderr.write(f"Error parsing {filepath}: {e}")
            return {}, {}

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        ini_dir = options['ini_dir']

        # Map course folders to course codes
        course_folders = {}
        for folder in os.listdir(ini_dir):
            folder_path = os.path.join(ini_dir, folder)
            if os.path.isdir(folder_path):
                course_folders[folder] = folder_path

        updated = 0

        for course_code, folder_path in course_folders.items():
            ini_files = [f for f in os.listdir(folder_path) if f.endswith('.ini')]

            for ini_file in ini_files:
                filepath = os.path.join(folder_path, ini_file)
                global_settings, sections = self.parse_ini_file(filepath)

                if not global_settings.get('test'):
                    continue

                test_name = global_settings.get('test', '')

                # Find matching template
                templates = ExamTemplate.objects.filter(
                    course__code__iexact=course_code,
                    name__iexact=test_name
                )

                if not templates.exists():
                    # Try partial match
                    templates = ExamTemplate.objects.filter(
                        course__code__icontains=course_code.replace('-', ''),
                        name__iexact=test_name
                    )

                if not templates.exists():
                    continue

                template = templates.first()

                # Extract global constraints
                max_points = global_settings.get('maxPoints')
                max_tf_points = global_settings.get('maxTFPoints')
                max_mc_points = global_settings.get('maxMCPoints')

                # Update template-level constraints
                if max_points and not template.max_points:
                    if not dry_run:
                        template.max_points = int(max_points)

                # Update section constraints
                selection_rules = template.selection_rules
                if isinstance(selection_rules, list):
                    changed = False
                    for section in selection_rules:
                        section_name = section.get('name', '')

                        # Try to match section to INI section
                        # e.g., "Week 1" -> "week1"
                        ini_section_name = section_name.lower().replace(' ', '')

                        if ini_section_name in sections:
                            ini_section = sections[ini_section_name]

                            # Extract constraints from INI section
                            if 'maxLongPoints' in ini_section:
                                section['maxLongPoints'] = int(ini_section['maxLongPoints'])
                                changed = True
                            if 'maxMCPoints' in ini_section:
                                section['maxMCPoints'] = int(ini_section['maxMCPoints'])
                                changed = True
                            if 'maxTFPoints' in ini_section:
                                section['maxTFPoints'] = int(ini_section['maxTFPoints'])
                                changed = True
                            if 'maxShortPoints' in ini_section:
                                section['maxShortPoints'] = int(ini_section['maxShortPoints'])
                                changed = True
                            if 'maxPoints' in ini_section:
                                section['maxPoints'] = int(ini_section['maxPoints'])
                                changed = True

                    # Also apply global type constraints to all sections if present
                    if max_tf_points or max_mc_points:
                        for section in selection_rules:
                            if max_tf_points and not section.get('maxTFPoints'):
                                section['maxTFPoints'] = int(max_tf_points) // len(selection_rules) if len(selection_rules) > 1 else int(max_tf_points)
                                changed = True
                            if max_mc_points and not section.get('maxMCPoints'):
                                section['maxMCPoints'] = int(max_mc_points) // len(selection_rules) if len(selection_rules) > 1 else int(max_mc_points)
                                changed = True

                    if changed:
                        if dry_run:
                            self.stdout.write(
                                self.style.SUCCESS(f"Would update {template.name} ({course_code})")
                            )
                            self.stdout.write(f"  From INI: {ini_file}")
                            self.stdout.write(f"  Sections: {sections}")
                        else:
                            template.selection_rules = selection_rules
                            template.save()
                            self.stdout.write(
                                self.style.SUCCESS(f"Updated {template.name} ({course_code})")
                            )
                        updated += 1

        self.stdout.write('')
        if dry_run:
            self.stdout.write(f"Dry run: {updated} templates would be updated")
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated {updated} templates"))
