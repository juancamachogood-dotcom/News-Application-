import logging

import requests
from django.conf import settings
from django.core.mail import send_mass_mail
from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)


def notify_article_subscribers(article):
    """Email each subscribed address once and return the recipient count."""
    recipients = set(
        article.author.journalist_subscribers.exclude(email="").values_list(
            "email", flat=True
        )
    )
    if article.publisher_id:
        recipients.update(
            article.publisher.subscribers.exclude(email="").values_list(
                "email", flat=True
            )
        )

    message = [
        (
            f"New article: {article.title}",
            article.content,
            settings.DEFAULT_FROM_EMAIL,
            [email],
        )
        for email in recipients
    ]
    if message:
        send_mass_mail(message, fail_silently=False)
    return len(message)


def share_approved_article(article):
    """POST approval to the configured API; failure does not undo approval."""
    try:
        token, _ = Token.objects.get_or_create(user=article.author)
        response = requests.post(
            settings.APPROVED_ARTICLE_ENDPOINT,
            json={"article": article.pk},
            headers={"Authorization": f"Token {token.key}"},
            timeout=3,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("Could not share approved article %s", article.pk)
        return False
