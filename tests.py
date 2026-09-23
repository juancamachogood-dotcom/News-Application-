from unittest.mock import Mock, patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from news.models import Article, Newsletter, Publisher, User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class NewsAPITests(APITestCase):
    """Verify API authentication, role permissions and approval
    integrations.
    """

    def setUp(self):
        """Create accounts, memberships and content used by each test."""
        self.reader = User.objects.create_user(
            "reader",
            email="reader@example.com",
            password="pass",
            role=User.Role.READER,
        )
        self.other_reader = User.objects.create_user(
            "other",
            email="other@example.com",
            password="pass",
            role=User.Role.READER,
        )
        self.journalist = User.objects.create_user(
            "journalist", password="pass", role=User.Role.JOURNALIST
        )
        self.other_journalist = User.objects.create_user(
            "other_journalist", password="pass", role=User.Role.JOURNALIST
        )
        self.editor = User.objects.create_user(
            "editor", password="pass", role=User.Role.EDITOR
        )
        self.publisher = Publisher.objects.create(name="Daily Test")
        self.other_publisher = Publisher.objects.create(name="Other News")
        self.publisher.journalists.add(self.journalist)
        self.publisher.editors.add(self.editor)
        self.reader.subscribed_publishers.add(self.publisher)
        self.reader.subscribed_journalists.add(self.journalist)
        self.approved = Article.objects.create(
            title="Subscribed article",
            content="Content",
            author=self.journalist,
            publisher=self.publisher,
            approved=True,
        )
        self.unsubscribed = Article.objects.create(
            title="Other article",
            content="Other",
            author=self.other_journalist,
            publisher=self.other_publisher,
            approved=True,
        )

    def authenticate(self, user):
        """Set the API client token header for the supplied user."""
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_unauthenticated_request_is_rejected(self):
        """Verify that unauthenticated request is rejected."""
        response = self.client.get("/api/articles/")
        self.assertEqual(response.status_code, 401)

    def test_required_plural_api_routes_are_available(self):
        """Verify that required plural api routes are available."""
        self.authenticate(self.reader)
        for url in (
            "/api/articles/",
            "/api/articles/subscribed/",
            "/api/newsletters/",
            "/api/publishers/",
        ):
            with self.subTest(url=url):
                self.assertNotEqual(self.client.get(url).status_code, 404)

    def test_reader_only_receives_subscribed_articles(self):
        """Verify that reader only receives subscribed articles."""
        self.authenticate(self.reader)
        response = self.client.get("/api/articles/subscribed/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["title"] for item in response.data], ["Subscribed article"]
        )

    def test_main_article_list_is_also_filtered_for_reader(self):
        """Verify that main article list is also filtered for reader."""
        self.authenticate(self.reader)
        response = self.client.get("/api/articles/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["title"] for item in response.data], ["Subscribed article"]
        )

    def test_non_reader_cannot_use_subscribed_endpoint(self):
        """Verify that non reader cannot use subscribed endpoint."""
        self.authenticate(self.journalist)
        response = self.client.get("/api/articles/subscribed/")
        self.assertEqual(response.status_code, 403)

    def test_reader_cannot_create_article(self):
        """Verify that reader cannot create article."""
        self.authenticate(self.reader)
        response = self.client.post(
            "/api/articles/",
            {"title": "No", "content": "Denied"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_journalist_can_create_article(self):
        """Verify that journalist can create article."""
        self.authenticate(self.journalist)
        response = self.client.post(
            "/api/articles/",
            {
                "title": "Draft",
                "content": "Draft content",
                "publisher": self.publisher.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        article = Article.objects.get(title="Draft")
        self.assertEqual(article.author, self.journalist)
        self.assertFalse(article.approved)

    def test_journalist_cannot_create_for_unrelated_publisher(self):
        """Verify that journalist cannot create for unrelated publisher."""
        self.authenticate(self.journalist)
        response = self.client.post(
            "/api/articles/",
            {
                "title": "No",
                "content": "Denied",
                "publisher": self.other_publisher.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("news.services.requests.post")
    def test_editor_approves_and_notifies_subscribers(self, mock_post):
        """Verify that editor approves and notifies subscribers."""
        mock_post.return_value = Mock(raise_for_status=Mock())
        draft = Article.objects.create(
            title="Breaking", content="Details", author=self.journalist
        )
        self.authenticate(self.editor)
        response = self.client.post(f"/api/articles/{draft.pk}/approve/")
        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertTrue(draft.approved)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["reader@example.com"])
        mock_post.assert_called_once()

    def test_journalist_cannot_approve(self):
        """Verify that journalist cannot approve."""
        draft = Article.objects.create(
            title="Draft", content="Details", author=self.journalist
        )
        self.authenticate(self.journalist)
        response = self.client.post(f"/api/articles/{draft.pk}/approve/")
        self.assertEqual(response.status_code, 403)

    def test_editor_can_delete_article(self):
        """Verify that editor can delete article."""
        self.authenticate(self.editor)
        repsonse = self.client.delete(f"/api/articles/{self.unsubscribed.pk}/")
        self.assertEqual(repsonse.status_code, 204)

    def test_reader_cannot_delete_article(self):
        """Verify that reader cannot delete article."""
        self.authenticate(self.reader)
        response = self.client.delete(f"/api/articles/{self.approved.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_newsletter_rejects_unapproved_article(self):
        """Verify that newsletter rejects unapproved article."""
        draft = Article.objects.create(
            title="Draft", content="Text", author=self.journalist
        )
        self.authenticate(self.journalist)
        response = self.client.post(
            "/api/newsletters/",
            {
                "title": "Weekly",
                "description": "Round-up",
                "articles": [draft.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_readers_sees_subscribed_newsletters(self):
        """Verify that readers sees subscribed newsletters."""
        subscribed = Newsletter.objects.create(
            title="Subscribed digest",
            author=self.journalist,
            publisher=self.publisher,
        )
        subscribed.articles.add(self.approved)
        Newsletter.objects.create(
            title="Other digest",
            author=self.other_journalist,
            publisher=self.other_publisher,
        )
        self.authenticate(self.reader)
        response = self.client.get("/api/newsletters/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["title"] for item in response.data], ["Subscribed digest"]
        )

    def test_non_reader_cannot_be_given_subscriptions(self):
        """Verify that non reader cannot be given subscriptions."""
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.journalist.subscribed_publishers.add(self.publisher)

        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.editor.subscribed_journalists.add(self.journalist)

    def test_changing_reader_role_clears_subscriptions(self):
        """Verify that changing reader role clears subscriptions."""
        self.reader.role = User.Role.EDITOR
        self.reader.save()

        self.assertFalse(self.reader.subscribed_publishers.exists())
        self.assertFalse(self.reader.subscribed_journalists.exists())


class FrontendTests(TestCase):
    """Verify browser content workflows and reader subscription controls."""

    def setUp(self):
        """Create accounts, memberships and content used by each test."""
        self.reader = User.objects.create_user(
            "web_reader", password="pass", role=User.Role.READER
        )
        self.journalist = User.objects.create_user(
            "web_journalist", password="pass", role=User.Role.JOURNALIST
        )
        self.editor = User.objects.create_user(
            "web_editor", password="pass", role=User.Role.EDITOR
        )
        self.publisher = Publisher.objects.create(name="Fronted Times")
        self.publisher.journalists.add(self.journalist)
        self.publisher.editors.add(self.editor)
        self.reader.subscribed_publishers.add(self.publisher)
        self.article = Article.objects.create(
            title="Frontend story",
            content="A complete article for the browser interface.",
            author=self.journalist,
            publisher=self.publisher,
            approved=True,
        )

    def test_anonymous_user_is_sent_to_login(self):
        """Verify that anonymous user is sent to login."""
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(
            response, f'{reverse("login")}?next={reverse("dashboard")}'
        )

    def test_reader_dashboard_and_subscribed_article_render(self):
        """Verify that reader dashboard and subscribed article render."""
        self.client.force_login(self.reader)
        dashboard_response = self.client.get(reverse("dashboard"))
        article_response = self.client.get(
            reverse("article-detail", args=[self.article.pk])
        )
        self.assertContains(dashboard_response, "Reader workspace")
        self.assertContains(article_response, "Frontend story")

    def test_render_cannot_open_article_create_page(self):
        """Verify that render cannot open article create page."""
        self.client.force_login(self.reader)
        response = self.client.get(reverse("article-create"))
        self.assertEqual(response.status_code, 403)

    def test_journalist_can_create_article_from_form(self):
        """Verify that journalist can create article from form."""
        self.client.force_login(self.journalist)
        response = self.client.post(
            reverse("article-create"),
            {
                "title": "New browser draft",
                "content": "Drafted using the HTML form.",
                "publisher": self.publisher.pk,
            },
        )
        article = Article.objects.get(title="New browser draft")
        self.assertRedirects(
            response, reverse("article-detail", args=[article.pk])
        )
        self.assertFalse(article.approved)

    def test_editor_review_page_contains_draft(self):
        """Verify that editor review page contains draft."""
        Article.objects.create(
            title="Needs approval",
            content="Review this.",
            author=self.journalist,
            publisher=self.publisher,
        )
        self.client.force_login(self.editor)
        response = self.client.get(reverse("editor-review"))
        self.assertContains(response, "Needs approval")

    def test_reader_update_subscriptions(self):
        """Verify that reader update subscriptions."""
        second_publisher = Publisher.objects.create(name="Second Source")
        self.client.force_login(self.reader)
        response = self.client.post(
            reverse("subscriptions"),
            {
                "subscribed_publishers": [second_publisher.pk],
                "subscribed_journalists": [],
            },
        )
        self.assertRedirects(response, reverse("subscriptions"))
        self.assertQuerySetEqual(
            self.reader.subscribed_publishers.all(), [second_publisher]
        )

    def test_reader_only_sees_subscribed_newsletters(self):
        """Verify that reader only sees subscribed newsletters."""
        newsletter = Newsletter.objects.create(
            title="Reader edition",
            author=self.journalist,
            publisher=self.publisher,
        )
        newsletter.articles.add(self.article)
        self.client.force_login(self.reader)
        response = self.client.get(reverse("newsletter-list"))
        self.assertContains(response, "Reader edition")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class RequirementsRegressionTests(APITestCase):
    """Protect the published feed, editorial updates, and role access."""

    def setUp(self):
        self.writer = User.objects.create_user(
            "writer", password="test-pass", role="journalist"
        )
        self.other = User.objects.create_user(
            "other_writer", role="journalist"
        )
        self.editor = User.objects.create_user("editor", role="editor")
        self.reader = User.objects.create_user(
            "reader", role="reader", email="reader@example.com"
        )
        self.publisher = Publisher.objects.create(name="Regression News")
        self.publisher.journalists.add(self.writer)
        self.publisher.editors.add(self.editor)
        self.reader.subscribed_publishers.add(self.publisher)
        self.article = Article.objects.create(
            title="Published", content="Reviewed content", author=self.writer,
            publisher=self.publisher, approved=True,
        )
        self.draft = Article.objects.create(
            title="Draft", content="Private", author=self.writer
        )
        self.other_draft = Article.objects.create(
            title="Other draft", content="Private", author=self.other
        )

    def test_editor_put_preserves_valid_author_publisher_membership(self):
        self.client.force_authenticate(self.editor)
        response = self.client.put(
            f"/api/articles/{self.article.pk}/",
            {
                "title": "Corrected",
                "content": "Edited by editor",
                "publisher": self.publisher.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.article.refresh_from_db()
        self.assertTrue(self.article.approved)
        self.assertEqual(self.article.author, self.writer)
        unrelated = Publisher.objects.create(name="Unrelated")
        response = self.client.patch(
            f"/api/articles/{self.article.pk}/",
            {"publisher": unrelated.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_published_feed_never_contains_drafts_for_any_role(self):
        for user in (self.reader, self.writer, self.editor):
            self.client.force_authenticate(user)
            response = self.client.get("/api/articles/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                [item["id"] for item in response.data], [self.article.pk]
            )

    def test_draft_feed_and_details_are_scoped_by_role_and_author(self):
        for user, expected in (
            (self.writer, {self.draft.pk}),
            (self.editor, {self.draft.pk, self.other_draft.pk}),
        ):
            self.client.force_authenticate(user)
            response = self.client.get("/api/articles/drafts/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual({item["id"] for item in response.data}, expected)
        self.client.force_authenticate(self.writer)
        self.assertEqual(
            self.client.get(
                f"/api/articles/{self.other_draft.pk}/"
            ).status_code,
            404,
        )
        self.client.force_authenticate(self.reader)
        self.assertEqual(
            self.client.get("/api/articles/drafts/").status_code, 403
        )
        self.assertEqual(
            self.client.get(f"/api/articles/{self.draft.pk}/").status_code, 404
        )

    def test_journalist_changes_require_reapproval_but_noop_does_not(self):
        self.client.force_authenticate(self.writer)
        url = f"/api/articles/{self.article.pk}/"
        self.assertEqual(
            self.client.patch(
                url, {"content": self.article.content}
            ).status_code,
            200,
        )
        self.article.refresh_from_db()
        self.assertTrue(self.article.approved)
        response = self.client.patch(
            url, {"content": "Unreviewed revision", "approved": True}
        )
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertFalse(self.article.approved)
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get("/api/articles/").data, [])

    def test_browser_journalist_changes_require_reapproval(self):
        self.client.force_login(self.writer)
        response = self.client.post(
            reverse("article-edit", args=[self.article.pk]),
            {
                "title": self.article.title,
                "content": "Browser revision",
                "publisher": self.publisher.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        self.assertFalse(self.article.approved)

    def test_newsletters_hide_withdrawn_and_unsubscribed_articles(
        self,
    ):
        newsletter = Newsletter.objects.create(
            title="Digest", author=self.writer, publisher=self.publisher
        )
        unrelated = Article.objects.create(
            title="Unsubscribed",
            content="Hidden extract",
            author=self.other,
            approved=True,
        )
        newsletter.articles.add(self.article, self.draft, unrelated)
        self.client.force_authenticate(self.reader)
        response = self.client.get(f"/api/newsletters/{newsletter.pk}/")
        self.assertEqual(response.data["articles"], [self.article.pk])
        self.client.force_login(self.reader)
        response = self.client.get(
            reverse("newsletter-detail", args=[newsletter.pk])
        )
        self.assertContains(response, "Reviewed content")
        self.assertNotContains(response, "Private")
        self.assertNotContains(response, "Hidden extract")
        self.article.approved = False
        self.article.save(update_fields=["approved"])
        self.assertEqual(
            self.client.get(
                f"/api/newsletters/{newsletter.pk}/"
            ).data["articles"],
            [],
        )
        response = self.client.get(
            reverse("newsletter-detail", args=[newsletter.pk])
        )
        self.assertNotContains(response, "Reviewed content")

    def test_former_journalist_cannot_mutate_previously_authored_content(self):
        newsletter = Newsletter.objects.create(
            title="Previous work", author=self.writer
        )
        self.writer.role = User.Role.READER
        self.writer.save()
        self.writer.subscribed_publishers.add(self.publisher)
        self.client.force_authenticate(self.writer)
        self.client.force_login(self.writer)
        for resource, obj in (
            ("articles", self.article), ("newsletters", newsletter)
        ):
            url = f"/api/{resource}/{obj.pk}/"
            self.assertEqual(
                self.client.patch(url, {"title": "Forbidden"}).status_code,
                403,
            )
            self.assertEqual(self.client.delete(url).status_code, 403)
        for name, obj in (
            ("article", self.article), ("newsletter", newsletter)
        ):
            for action in ("edit", "delete"):
                url = reverse(f"{name}-{action}", args=[obj.pk])
                self.assertEqual(
                    self.client.post(url, {"title": "Forbidden"}).status_code,
                    403,
                )
        response = self.client.get(
            reverse("article-detail", args=[self.article.pk])
        )
        self.assertNotContains(
            response, reverse("article-edit", args=[self.article.pk])
        )

    def test_newsletter_crud_and_role_denials(self):
        self.client.force_authenticate(self.writer)
        response = self.client.post(
            "/api/newsletters/",
            {
                "title": "New digest",
                "articles": [self.article.pk],
                "publisher": self.publisher.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        url = f'/api/newsletters/{response.data["id"]}/'
        self.client.force_authenticate(self.reader)
        self.assertEqual(
            self.client.post(
                "/api/newsletters/", {"title": "Denied"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(url, {"title": "Denied"}).status_code,
            403,
        )
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.patch(url, {"title": "Denied"}).status_code, 403
        )
        self.client.force_authenticate(self.editor)
        self.assertEqual(
            self.client.patch(url, {"title": "Edited digest"}).status_code, 200
        )
        response = self.client.patch(url, {"articles": []}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["articles"], [])
        response = self.client.patch(
            url, {"articles": [self.article.pk]}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["articles"], [self.article.pk])
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_token_issuance_success_and_failure(self):
        response = self.client.post(
            "/api/token/", {"username": "writer", "password": "test-pass"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        response = self.client.post(
            "/api/token/", {"username": "writer", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 400)

    @patch("news.services.requests.post")
    def test_approval_receiver_and_failed_sharing(self, mock_post):
        import requests
        from news.models import ApprovedArticleDelivery
        mock_post.side_effect = requests.ConnectionError(
            "Test connection failure"
        )
        self.client.force_authenticate(self.editor)
        with self.assertLogs("news.services", level="ERROR"):
            response = self.client.post(
                f"/api/articles/{self.draft.pk}/approve/"
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["shared_with_api"])
        self.draft.refresh_from_db()
        self.assertTrue(self.draft.approved)
        self.client.force_authenticate(self.writer)
        for expected in (201, 200):
            response = self.client.post(
                "/api/approved/", {"article": self.draft.pk}
            )
            self.assertEqual(response.status_code, expected)
        self.assertEqual(
            ApprovedArticleDelivery.objects.filter(article=self.draft).count(),
            1,
        )
        response = self.client.post(
            "/api/approved/", {"article": self.other_draft.pk}
        )
        self.assertEqual(response.status_code, 404)

    def test_approval_receiver_rejects_readers_and_other_authors(self):
        for user in (self.reader, self.other):
            self.client.force_authenticate(user)
            response = self.client.post(
                "/api/approved/", {"article": self.article.pk}
            )
            self.assertEqual(response.status_code, 403)
