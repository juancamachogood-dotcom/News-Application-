#!/usr/bin/env python
"""Django's command-line utility."""
import os
import sys


def main():
    """Run commands, using SQLite tests unless MariaDB testing is requested."""
    # NEWS_TEST_DATABASE=mariadb leaves the configured MariaDB backend active.
    if (len(sys.argv) > 1 and sys.argv[1] == "test"
            and os.getenv("NEWS_TEST_DATABASE", "sqlite") == "sqlite"):
        os.environ["DB_ENGINE"] = "sqlite"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "news_project.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
