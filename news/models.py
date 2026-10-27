"""Define database models for users, publishers, article and newsletters."""

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class Publisher(models.Model):
    """A news organisation with an optional owner and assigned staff."""

    owner = models.ForeignKey(
        "User", on_delete=models.SET_NULL, related_name="owned_publishers",
        null=True, blank=True,
    )
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    editors = models.ManyToManyField(
        "User", related_name="edited_publishers", blank=True
    )
    journalists = models.ManyToManyField(
        "User", related_name="publisher_memberships", blank=True
    )

    def __str__(self):
        """Return the organisation name for display."""
        return self.name


class User(AbstractUser):
    """Extend Django users with newsroom roles and reader subscriptions."""

    class Role(models.TextChoices):
        """Supported public account roles used by the permission checks."""

        READER = "reader", "Reader"
        EDITOR = "editor", "Editor"
        JOURNALIST = "journalist", "Journalist"
        PUBLISHER = "publisher", "Publisher"

    role = models.CharField(
        max_length=12, choices=Role.choices, default=Role.READER
    )
    subscribed_publishers = models.ManyToManyField(
        Publisher, related_name="subscribers", blank=True
    )
    subscribed_journalists = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="journalist_subscribers",
        blank=True,
    )

    def clean(self):
        """Reject subscriptions on accounts whose role is not reader."""
        super().clean()
        if self.pk and self.role != self.Role.READER:
            if (
                self.subscribed_publishers.exists()
                or self.subscribed_journalists.exists()
            ):
                raise ValidationError("Only readers may have subscriptions.")


class Article(models.Model):
    """Represent a news article and its editorial approval status.
    
    Store the article's title, content, author and optional publisher.
    New articles start unapproved. Queries use newest-first ordering
    unless another order is requested.
    
    Model validation checks that the author is a journalist and belongs 
    to the selected publisher when a publisher is provided.
    """

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="articles"
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.CASCADE,
        related_name="articles",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)

    class Meta:
        """Configure Django metadata for Article."""

        ordering = ["-created_at"]
        permissions = [("approve_article", "Can approve article")]

    def clean(self):
        """Validate the article's author and publisher relationship.
        
        :raises django.core.exceptions.ValidationError:
            If the author is not a journalist or does not belong to 
            the selected publisher.
        """
        
        super().clean()
        if self.author_id and self.author.role != User.Role.JOURNALIST:
            raise ValidationError(
                {"author": "Article authors must be journalists."}
            )
        if self.publisher_id and self.author_id:
            if not self.publisher.journalists.filter(
                pk=self.author_id
            ).exists():
                raise ValidationError(
                    {"publisher": "The author must belong to this publisher."}
                )

    def __str__(self):
        """Return the article title for display."""
        return self.title


class Newsletter(models.Model):
    """A curated collection of articles authored by newsroom staff."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="newsletters"
    )
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.CASCADE,
        related_name="newsletter",
        null=True,
        blank=True,
    )
    articles = models.ManyToManyField(
        Article, related_name="newsletters", blank=True
    )

    class Meta:
        """Configure Django metadata for Newsletter."""

        ordering = ["-created_at"]

    def clean(self):
        """Restrict newsletter authorship to journalists and editors."""
        super().clean()
        allowed = {User.Role.JOURNALIST, User.Role.EDITOR}
        if self.author_id and self.author.role not in allowed:
            raise ValidationError(
                {
                    "author": (
                        "Newsletters may only be authored by journalist or "
                        "editors."
                    )
                }
            )

    def __str__(self):
        """Return the newsletter title for display."""
        return self.title


class ApprovedArticleDelivery(models.Model):
    """Local log of approved articles shared through the integration
    endpoint.
    """

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="delivery_logs"
    )
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Identify the delivered article for display."""
        return f"Delivery: {self.article}"
