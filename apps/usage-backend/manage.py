#!/usr/bin/env python
"""Django management commands; local development is the default."""

import os
import sys


def main():
    # Tell Django which settings configuration to use unless one was already set.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

    # Import Django after selecting settings so its management tools use that configuration.
    from django.core.management import execute_from_command_line

    # Pass the command-line arguments through, for example: manage.py runserver.
    execute_from_command_line(sys.argv)


# Run the command handler only when this file is executed directly.
if __name__ == "__main__":
    main()
