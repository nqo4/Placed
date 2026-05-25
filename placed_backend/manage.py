#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    """Run administrative tasks."""
    # Ensure the parent directory is on the path so we can import 'placed_backend'
    current_path = os.path.dirname(os.path.abspath(__file__))
    parent_path = os.path.dirname(current_path)
    if parent_path not in sys.path:
        sys.path.append(parent_path)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'placed_backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
