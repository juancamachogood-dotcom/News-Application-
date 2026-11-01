"""Send subscriber notifications and share article approvals."""
import logging

import requests
from django.conf import settings
from django.core.mail import send_mass_mail
from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)


def notify_article_subscribers(article):
    """Send article notifications to unique subscriber email addresses.

    Collect subscribers of the author and, when present, the publisher.
    Exclude empty addresses and remove duplicates. Email delivery errors
    propagate to the caller.

    :param article: Article whose title and content will be emailed.
    :return: Number of unique recipient addresses.
    :rtype: int
    """

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
    """Send an article's ID to the configured approval API.

    Authenticate using the author's API token. Log request failures
    and return False when they occur.

    :param article: Approved article to share with the API.
    :return: True when the request succeeds; False on a request error.
    :rtype: bool
    """

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
