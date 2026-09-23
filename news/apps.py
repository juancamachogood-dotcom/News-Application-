from django.apps import AppConfig


class NewsConfig(AppConfig):
    """Configure the news app and register its role-maintenance signals."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "news"

    def ready(self):
        """Register signal handlers after Django loads the app registry."""
        from . import signals  # noqa: F401
