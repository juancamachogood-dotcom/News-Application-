from rest_framework import serializers

from .models import Article, Newsletter, Publisher, User


class ApprovedArticleReceiptSerializer(serializers.Serializer):
    """Validate the article ID supplied to the approval receiver."""

    article = serializers.IntegerField(min_value=1)


class UserSerializer(serializers.ModelSerializer):
    """Serialize public account identity and newsroom role fields."""

    class Meta:
        """Configure Django metadata for UserSerializer."""

        model = User
        fields = ["id", "username", "email", "role"]
        read_only_fields = ["id"]


class PublisherSerializer(serializers.ModelSerializer):
    """Serialize publisher details and assigned team identifiers."""

    class Meta:
        """Configure Django metadata for PublisherSerializer."""

        model = Publisher
        fields = ["id", "name", "description", "editors", "journalists"]
        read_only_fields = ["id"]


class ArticleSerializer(serializers.ModelSerializer):
    """Serialize stories while protecting authorship and approval."""

    author = UserSerializer(read_only=True)

    class Meta:
        """Configure Django metadata for ArticleSerializer."""

        model = Article
        fields = [
            "id",
            "title",
            "content",
            "author",
            "publisher",
            "created_at",
            "approved",
        ]
        read_only_fields = ["id", "author", "created_at", "approved"]

    def validate_publisher(self, publisher):
        """Reject publisher selections that violate the caller's role rules."""
        author = (
            self.instance.author
            if self.instance
            else self.context["request"].user
        )
        if publisher and not publisher.journalists.filter(
            pk=author.pk
        ).exists():
            raise serializers.ValidationError(
                "The article author must belong to this publisher."
            )
        return publisher

    def update(self, instance, validated_data):
        """Send journalist revisions through editorial review again."""
        changed = any(
            field in validated_data
            and validated_data[field] != getattr(instance, field)
            for field in ("title", "content", "publisher")
        )
        if (
            self.context["request"].user.role == User.Role.JOURNALIST
            and changed
        ):
            validated_data["approved"] = False
        return super().update(instance, validated_data)


class NewsletterSerializer(serializers.ModelSerializer):
    """Validate and serialize newsletters containing approved stories."""

    author = UserSerializer(read_only=True)

    class Meta:
        """Configure Django metadata for NewsletterSerializer."""

        model = Newsletter
        fields = [
            "id",
            "title",
            "description",
            "created_at",
            "author",
            "publisher",
            "articles",
        ]
        read_only_fields = ["id", "created_at", "author"]

    def validate_articles(self, articles):
        """Reject newsletters containing any unapproved article."""
        if any(not article.approved for article in articles):
            raise serializers.ValidationError(
                "Newsletters may contain only approved articles."
            )
        return articles

    def validate_publisher(self, publisher):
        """Reject publisher selections that violate the caller's role rules."""
        request = self.context["request"]
        if (
            publisher
            and request.user.role == User.Role.JOURNALIST
            and not publisher.journalists.filter(pk=request.user.pk).exists()
        ):
            raise serializers.ValidationError(
                "You are not a journalist for this publisher."
            )
        return publisher
