from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Prefetch, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import (
    ArticleForm,
    NewsletterForm,
    SignUpForm,
    SubscriptionForm,
    PublisherTeamForm,
)
from .models import (
    ApprovedArticleDelivery,
    Article,
    Newsletter,
    Publisher,
    User,
)
from .permissions import (
    ArticlePermission,
    NewsletterPermission,
    can_edit_content,
)
from .serializers import (
    ArticleSerializer,
    NewsletterSerializer,
    PublisherSerializer,
)
from .services import notify_article_subscribers, share_approved_article


def signup(request):
    """Register a public account and send successful applicants to login."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, "Your account is ready. You can sign in now."
        )
        return redirect("login")

    return render(request, "news/signup.html", {"form": form})


def visible_articles_for(user):
    """Return stories visible to the user, filtering subscriptions and
    drafts.
    """
    articles = Article.objects.select_related("author", "publisher")
    if user.role == User.Role.READER:
        return articles.filter(approved=True).filter(
            Q(publisher__in=user.subscribed_publishers.all())
            | Q(author__in=user.subscribed_journalists.all())
        ).distinct()
    if user.role == User.Role.JOURNALIST:
        return articles.filter(Q(approved=True) | Q(author=user)).distinct()
    if user.role == User.Role.PUBLISHER:
        return articles.filter(approved=True)
    return articles


def visible_newsletters_for(user):
    """Return newsletters, limiting readers to their subscribed sources."""
    newsletters = Newsletter.objects.select_related(
        "author", "publisher"
    ).prefetch_related(Prefetch(
        "articles", queryset=visible_articles_for(user).filter(approved=True),
    ))
    if user.role == User.Role.READER:
        return newsletters.filter(
            Q(publisher__in=user.subscribed_publishers.all())
            | Q(author__in=user.subscribed_journalists.all())
        ).distinct()
    return newsletters


@login_required
def dashboard(request):
    """Render the signed-in user's recent content and role-specific counts."""
    articles = visible_articles_for(request.user)
    newsletters = visible_newsletters_for(request.user)
    context = {
        "recent_articles": articles[:6],
        "article_count": articles.count(),
        "newsletter_count": newsletters.count(),
    }
    if request.user.role == User.Role.READER:
        context["publisher_count"] = request.user.subscribed_publishers.count()
    elif request.user.role == User.Role.JOURNALIST:
        context["draft_count"] = Article.objects.filter(
            author=request.user, approved=False
        ).count()
    else:
        context["pending_count"] = Article.objects.filter(
            approved=False
        ).count()
    return render(request, "news/dashboard.html", context)


@login_required
def article_list(request):
    """Render the article feed permitted for the signed-in user."""
    return render(
        request,
        "news/article_list.html",
        {"articles": visible_articles_for(request.user)},
    )


@login_required
def article_detail(request, pk):
    """Render a permitted article or return a not-found response."""
    article = get_object_or_404(visible_articles_for(request.user), pk=pk)
    return render(request, "news/article_detail.html", {"article": article})


@login_required
def article_create(request):
    """Let a journalist save a new article as an unapproved draft."""
    if request.user.role != User.Role.JOURNALIST:
        return HttpResponseForbidden("Only journalists can create articles.")
    form = ArticleForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.author = request.user
        article.save()
        return redirect("article-detail", pk=article.pk)
    return render(
        request,
        "news/content_form.html",
        {
            "form": form,
            "page_title": "Write article",
            "submit_label": "Save draft",
        },
    )


@login_required
def article_edit(request, pk):
    """Let the author or an editor update an existing article."""
    article = get_object_or_404(Article, pk=pk)
    if not can_edit_content(request.user, article):
        return HttpResponseForbidden("You cannot edit this article.")
    form = ArticleForm(
        request.POST or None, instance=article, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        if request.user.role == User.Role.JOURNALIST and form.has_changed():
            form.instance.approved = False
        form.save()
        return redirect("article-detail", pk=article.pk)
    return render(
        request,
        "news/content_form.html",
        {
            "form": form,
            "page_title": "Edit article",
            "submit_label": "Save changes",
        },
    )


@login_required
def article_delete(request, pk):
    """Confirm deletion and remove an article after an authorized POST."""
    article = get_object_or_404(Article, pk=pk)
    if not can_edit_content(request.user, article):
        return HttpResponseForbidden("You cannot delete this article.")
    if request.method == "POST":
        article.delete()
        return redirect("article-list")
    return render(
        request,
        "news/confirm_delete.html",
        {
            "object": article,
            "object_type": "article",
            "cancel_url": reverse("article-detail", args=[article.pk]),
        },
    )


@login_required
def newsletter_list(request):
    """Render the newsletters visible to the signed-in user."""
    return render(
        request,
        "news/newsletter_list.html",
        {"newsletters": visible_newsletters_for(request.user)},
    )


@login_required
def newsletter_detail(request, pk):
    """Render a permitted newsletter or return a not-found response."""
    newsletter = get_object_or_404(
        visible_newsletters_for(request.user), pk=pk
    )
    return render(
        request,
        "news/newsletter_detail.html",
        {"newsletter": newsletter},
    )


@login_required
def newsletter_create(request):
    """Let newsroom staff create a newsletter of approved articles."""
    if request.user.role not in {User.Role.JOURNALIST, User.Role.EDITOR}:
        return HttpResponseForbidden(
            "Only newsroom staff can create newsletters."
        )
    form = NewsletterForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        newsletter = form.save(commit=False)
        newsletter.author = request.user
        newsletter.save()
        form.save_m2m()
        return redirect("newsletter-detail", pk=newsletter.pk)
    return render(
        request,
        "news/content_form.html",
        {
            "form": form,
            "page_title": "Create newsletter",
            "submit_label": "Create",
        },
    )


@login_required
def newsletter_edit(request, pk):
    """Let the author or an editor update a newsletter."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    if not can_edit_content(request.user, newsletter):
        return HttpResponseForbidden("You cannot edit this newsletter.")
    form = NewsletterForm(
        request.POST or None, instance=newsletter, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("newsletter-detail", pk=newsletter.pk)
    return render(
        request,
        "news/content_form.html",
        {
            "form": form,
            "page_title": "Edit newsletter",
            "submit_label": "Save changes",
        },
    )


@login_required
def newsletter_delete(request, pk):
    """Confirm deletion and remove a newsletter after an authorized POST."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    if not can_edit_content(request.user, newsletter):
        return HttpResponseForbidden("You cannot delete this newsletter.")
    if request.method == "POST":
        newsletter.delete()
        return redirect("newsletter-list")
    return render(
        request,
        "news/confirm_delete.html",
        {
            "object": newsletter,
            "object_type": "newsletter",
            "cancel_url": reverse("newsletter-detail", args=[newsletter.pk]),
        },
    )


@login_required
def subscriptions(request):
    """Let readers view and update the sources they follow."""
    if request.user.role != User.Role.READER:
        return HttpResponseForbidden("Only readers manage subscriptions.")
    form = SubscriptionForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your subscriptions were updated.")
        return redirect("subscriptions")
    return render(request, "news/subscriptions.html", {"form": form})


class ArticleViewSet(viewsets.ModelViewSet):
    """Expose article CRUD, subscribed feeds and editorial approval actions."""

    serializer_class = ArticleSerializer
    permission_classes = [IsAuthenticated, ArticlePermission]

    def get_queryset(self):
        """Return the content queryset permitted for the authenticated
        caller.
        """
        queryset = visible_articles_for(self.request.user)
        if self.action == "list":
            return queryset.filter(approved=True)
        return queryset

    @action(detail=False, methods=["get"])
    def drafts(self, request):
        """Keep newsroom drafts separate from the published API feed."""
        if request.user.role not in {User.Role.EDITOR, User.Role.JOURNALIST}:
            return Response(
                {"detail": "Only newsroom staff can view drafts."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(self.get_serializer(
            self.get_queryset().filter(approved=False), many=True
        ).data)

    def perform_create(self, serializer):
        """Save new content with the authenticated caller as its author."""
        serializer.save(author=self.request.user)

    @action(detail=False, methods=["get"])
    def subscribed(self, request):
        """Return subscribed articles for readers and reject other roles."""
        if request.user.role != User.Role.READER:
            return Response(
                {"detail": "Only readers have subscriptions"},
                status=status.HTTP_403_FORBIDDEN,
            )
        articles = self.get_queryset().filter(
            Q(publisher__in=request.user.subscribed_publishers.all())
            | Q(author__in=request.user.subscribed_journalists.all())
        ).distinct()
        return Response(self.get_serializer(articles, many=True).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve once, notify subscribers and report integration results."""
        article = self.get_object()
        if article.approved:
            return Response(
                {"detail": "Article is already approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        article.approved = True
        article.save(update_fields=["approved"])
        email_count = notify_article_subscribers(article)
        shared = share_approved_article(article)
        return Response(
            {
                "detail": "Article approved.",
                "subscriber_emails": email_count,
                "shared_with_api": shared,
            }
        )


class NewsletterViewSet(viewsets.ModelViewSet):
    """Expose newsletter CRUD subject to role and subscription rules."""

    serializer_class = NewsletterSerializer
    permission_classes = [IsAuthenticated, NewsletterPermission]

    def get_queryset(self):
        """Return the content queryset permitted for the authenticated
        caller.
        """
        return visible_newsletters_for(self.request.user)

    def perform_create(self, serializer):
        """Save new content with the authenticated caller as its author."""
        serializer.save(author=self.request.user)


class PublisherViewSet(viewsets.ReadOnlyModelViewSet):
    """Expose read-only publisher records to authenticated accounts."""

    queryset = Publisher.objects.prefetch_related("editors", "journalists")
    serializer_class = PublisherSerializer
    permission_classes = [IsAuthenticated]


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approved_article_receiver(request):
    """Log receipt of an approved article without duplicating its delivery."""
    if request.user.role not in {User.Role.EDITOR, User.Role.JOURNALIST}:
        return Response(
            {"detail": "Only newsroom staff can log approved articles."},
            status=status.HTTP_403_FORBIDDEN,
        )
    article = get_object_or_404(
        Article, pk=request.data.get("article"), approved=True
    )
    if not can_edit_content(request.user, article):
        return Response(
            {"detail": "You cannot log this article."},
            status=status.HTTP_403_FORBIDDEN,
        )
    delivery, created = ApprovedArticleDelivery.objects.get_or_create(
        article=article
    )
    code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return Response(
        {"article": delivery.article_id, "logged": created}, status=code
    )


def is_editors(user):
    """Return whether the user is authenticated and has the editor role."""
    return user.is_authenticated and user.role == User.Role.EDITOR


@login_required
@user_passes_test(is_editors)
def editors_review(request):
    """Render the pending article queue for an authenticated editor."""
    return render(
        request,
        "news/editor_review.html",
        {
            "articles": Article.objects.filter(approved=False).select_related(
                "author"
            )
        },
    )


@require_POST
@login_required
@user_passes_test(is_editors)
def editor_approve(request, pk):
    """Approve a draft, notify subscribers and call the sharing integration."""
    article = get_object_or_404(Article, pk=pk, approved=False)
    article.approved = True
    article.save(update_fields=["approved"])
    notify_article_subscribers(article)
    share_approved_article(article)
    return redirect("editor-review")


@login_required
def publisher_team(request, pk):
    """Display and update only the signed-in publisher's own team."""
    if request.user.role != User.Role.PUBLISHER:
        return HttpResponseForbidden(
            "Only publisher accounts can manage teams."
        )
    publisher = get_object_or_404(Publisher, pk=pk, owner=request.user)
    form = PublisherTeamForm(
        request.POST if request.method == "POST" else None, instance=publisher
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your publisher team was updated.")
        return redirect("publisher-team", pk=publisher.pk)
    return render(request, "news/publisher_team.html", {
        "form": form, "publisher": publisher,
    })
