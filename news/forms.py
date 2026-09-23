from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Article, Newsletter, Publisher, User


class SignUpForm(UserCreationForm):
    """Register a news account and optionally create its owned publisher."""

    publisher_name = forms.CharField(
        max_length=150, required=False,
        help_text="Required only when registering as a publisher.",
    )

    class Meta(UserCreationForm.Meta):
        """Configure Django metadata for SignUpForm."""

        model = User
        fields = ("username", "email", "role")

    def __init__(self, *args, **kwargs):
        """Require email and configure browser autocomplete for signup
        fields.
        """
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username", "autofocus": True}
        )
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email"}
        )
        self.fields["password1"].widget.attrs.update(
            {"autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"autocomplete": "new-password"}
        )

    def clean_email(self):
        """Normalize the address and reject case-insensitive duplicates."""
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "An account with this email address already exists."
            )
        return email

    def clean(self):
        """Require a unique organisation name for publisher registrations."""
        cleaned = super().clean()
        if cleaned.get("role") == User.Role.PUBLISHER:
            name = cleaned.get("publisher_name", "").strip()
            if not name:
                self.add_error("publisher_name", "Enter your publisher name.")
            elif Publisher.objects.filter(name__iexact=name).exists():
                self.add_error(
                    "publisher_name",
                    "This publisher name is already registered.",
                )
            cleaned["publisher_name"] = name
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        """Save the chosen role and create its publisher in one transaction.

        With commit=False, the caller must also create the publisher after
        saving the returned user; the public registration view uses
        commit=True.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            if user.role == User.Role.PUBLISHER:
                Publisher.objects.create(
                    name=self.cleaned_data["publisher_name"], owner=user
                )
        return user


class ArticleForm(forms.ModelForm):
    """Edit article content and restrict publisher choices for journalists."""

    class Meta:
        """Configure Django metadata for ArticleForm."""

        model = Article
        fields = ("title", "content", "publisher")

    def __init__(self, *args, user, **kwargs):
        """Limit publisher choices to the journalist's memberships."""
        super().__init__(*args, **kwargs)
        self.user = user
        if user.role == User.Role.JOURNALIST:
            self.fields["publisher"].queryset = (
                user.publisher_memberships.all()
            )
        else:
            self.fields["publisher"].queryset = Publisher.objects.all()

    def clean_publisher(self):
        """Reject publishers outside a journalist's assigned memberships."""
        publisher = self.cleaned_data.get("publisher")
        if (
            publisher
            and self.user.role == User.Role.JOURNALIST
            and not publisher.journalists.filter(pk=self.user.pk).exists()
        ):
            raise ValidationError(
                "You are not a journalist for this publisher."
            )
        return publisher


class NewsletterForm(forms.ModelForm):
    """Edit newsletters using approved articles and permitted publishers."""

    class Meta:
        """Configure Django metadata for NewsletterForm."""

        model = Newsletter
        fields = ("title", "description", "publisher", "articles")
        widgets = {"articles": forms.CheckboxSelectMultiple()}

    def __init__(self, *args, user, **kwargs):
        """Offer approved articles and restrict journalist publisher
        choices.
        """
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["articles"].queryset = Article.objects.filter(
            approved=True
        )
        if user.role == User.Role.JOURNALIST:
            self.fields["publisher"].queryset = (
                user.publisher_memberships.all()
            )
        else:
            self.fields["publisher"].queryset = Publisher.objects.all()

    def clean_publisher(self):
        """Reject publishers outside a journalist's assigned memberships."""
        publisher = self.cleaned_data.get("publisher")
        if (
            publisher
            and self.user.role == User.Role.JOURNALIST
            and not publisher.journalists.filter(pk=self.user.pk).exists()
        ):
            raise ValidationError(
                "You are not a journalist for this publisher."
            )
        return publisher


class SubscriptionForm(forms.ModelForm):
    """Let readers choose publishers and journalist accounts to follow."""

    class Meta:
        """Configure Django metadata for SubscriptionForm."""

        model = User
        fields = ("subscribed_publishers", "subscribed_journalists")
        labels = {
            "subscribed_publishers": "Publishers",
            "subscribed_journalists": "Journalists",
        }
        widgets = {
            "subscribed_publishers": forms.CheckboxSelectMultiple(),
            "subscribed_journalists": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        """Limit followable users to accounts with the journalist role."""
        super().__init__(*args, **kwargs)
        self.fields["subscribed_journalists"].queryset = User.objects.filter(
            role=User.Role.JOURNALIST
        )


class PublisherTeamForm(forms.ModelForm):
    """Let a publisher owner assign active editors and journalists."""

    class Meta:
        """Expose team membership without allowing ownership changes."""

        model = Publisher
        fields = ("editors", "journalists")
        widgets = {
            "editors": forms.CheckboxSelectMultiple(),
            "journalists": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        """Restrict each team field to accounts with its matching role."""
        super().__init__(*args, **kwargs)
        self.fields["editors"].queryset = User.objects.filter(
            role=User.Role.EDITOR, is_active=True
        )
        self.fields["journalists"].queryset = User.objects.filter(
            role=User.Role.JOURNALIST, is_active=True
        )
