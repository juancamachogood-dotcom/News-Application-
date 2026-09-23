from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from .views import (
    ArticleViewSet,
    NewsletterViewSet,
    PublisherViewSet,
    approved_article_receiver,
    article_create,
    article_delete,
    article_detail,
    article_edit,
    article_list,
    dashboard,
    editor_approve,
    editors_review,
    newsletter_create,
    newsletter_delete,
    newsletter_detail,
    newsletter_edit,
    newsletter_list,
    subscriptions,
    publisher_team,
)

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="api-article")
router.register("newsletters", NewsletterViewSet, basename="api-newsletter")
router.register("publishers", PublisherViewSet, basename="api-publisher")


urlpatterns = [
    path("publishers/<int:pk>/team/", publisher_team, name="publisher-team"),
    path("dashboard/", dashboard, name="dashboard"),
    path("articles/", article_list, name="article-list"),
    path("articles/new/", article_create, name="article-create"),
    path("articles/<int:pk>/edit/", article_edit, name="article-edit"),
    path("articles/<int:pk>/delete/", article_delete, name="article-delete"),
    path("articles/<int:pk>/", article_detail, name="article-detail"),
    path("newsletters/", newsletter_list, name="newsletter-list"),
    path("newsletters/new/", newsletter_create, name="newsletter-create"),
    path(
        "newsletters/<int:pk>/edit/", newsletter_edit, name="newsletter-edit"
    ),
    path(
        "newsletters/<int:pk>/delete/",
        newsletter_delete,
        name="newsletter-delete",
    ),
    path(
        "newsletters/<int:pk>/", newsletter_detail, name="newsletter-detail"
    ),
    path("subscriptions/", subscriptions, name="subscriptions"),
    path("api/token/", obtain_auth_token, name="api-token"),
    path("api/approved/", approved_article_receiver, name="approved-reciver"),
    path("api/", include(router.urls)),
    path("editor/review/", editors_review, name="editor-review"),
    path(
        "editor/articles/<int:pk>/approve",
        editor_approve,
        name="editor-approve",
    ),
]
