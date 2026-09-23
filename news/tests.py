from django.test import TestCase
from django.urls import reverse

from .models import Article, Newsletter, Publisher, User


class SignUpTests(TestCase):
    """Verify signup links, reader registration and duplicate-email errors."""

    def test_login_page_links_to_signup(self):
        """Verify that login page links to signup."""
        response = self.client.get(reverse("login"))

        self.assertContains(response, reverse("signup"))
        self.assertContains(response, "Create an account")

    def test_valid_signup_creates_reader_and_redirects_to_login(self):
        """Verify that valid signup creates reader and redirects to login."""
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new_reader",
                "role": User.Role.READER,
                "email": "reader@example.com",
                "password1": "A-secure-password-123",
                "password2": "A-secure-password-123",
            },
        )

        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="new_reader")
        self.assertEqual(user.role, User.Role.READER)
        self.assertEqual(user.email, "reader@example.com")
        self.assertTrue(user.check_password("A-secure-password-123"))

    def test_signup_rejects_duplicate_email(self):
        """Verify that signup rejects duplicate email."""
        User.objects.create_user(
            username="existing",
            email="reader@example.com",
            password="A-secure-password-123",
        )

        response = self.client.post(
            reverse("signup"),
            {
                "username": "another_reader",
                "role": User.Role.READER,
                "email": "READER@example.com",
                "password1": "A-secure-password-123",
                "password2": "A-secure-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "An account with this email address already exists."
        )
        self.assertFalse(
            User.objects.filter(username="another_reader").exists()
        )


class DashboardTests(TestCase):
    """Verify role-specific dashboards and their navigation targets."""

    def setUp(self):
        """Create accounts, memberships and content used by each test."""
        self.reader = User.objects.create_user(
            "reader", password="password", role=User.Role.READER
        )
        self.journalist = User.objects.create_user(
            "journalist", password="password", role=User.Role.JOURNALIST
        )
        self.editor = User.objects.create_user(
            "editor", password="password", role=User.Role.EDITOR
        )
        self.publisher = Publisher.objects.create(name="Daily Test")
        self.publisher.journalists.add(self.journalist)
        self.publisher.editors.add(self.editor)
        self.reader.subscribed_publishers.add(self.publisher)
        self.published = Article.objects.create(
            title="Published story",
            content="A published story for subscribed readers.",
            author=self.journalist,
            publisher=self.publisher,
            approved=True,
        )
        self.draft = Article.objects.create(
            title="Draft story",
            content="A draft awaiting review.",
            author=self.journalist,
            publisher=self.publisher,
        )
        self.newsletter = Newsletter.objects.create(
            title="Daily edition",
            author=self.journalist,
            publisher=self.publisher,
        )

    def test_anonymous_visitor_is_redirected_to_login(self):
        """Verify that anonymous visitor is redirected to login."""
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response, f'{reverse("login")}?next={reverse("dashboard")}'
        )

    def test_reader_sees_subscribed_content_and_reader_action(self):
        """Verify that reader sees subscribed content and reader action."""
        self.client.force_login(self.reader)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Reader workspace")
        self.assertContains(response, "Published story")
        self.assertNotContains(response, "Draft story")
        self.assertContains(response, "Manage subscriptions")
        self.assertEqual(response.context["article_count"], 1)
        self.assertEqual(response.context["publisher_count"], 1)

    def test_journalist_sees_draft_count_and_write_action(self):
        """Verify that journalist sees draft count and write action."""
        self.client.force_login(self.journalist)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Journalist workspace")
        self.assertContains(response, "Write article")
        self.assertEqual(response.context["draft_count"], 1)
        self.assertEqual(response.context["article_count"], 2)

    def test_editor_sees_pending_review_count_and_review_action(self):
        """Verify that editor sees pending review count and review action."""
        self.client.force_login(self.editor)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Editor workspace")
        self.assertContains(response, "Review articles")
        self.assertEqual(response.context["pending_count"], 1)
        self.assertEqual(response.context["article_count"], 2)

    def test_dashboard_navigation_destinations_render(self):
        """Verify that dashboard navigation destinations render."""
        self.client.force_login(self.reader)

        for url in (
            reverse("article-list"),
            reverse("article-detail", args=[self.published.pk]),
            reverse("newsletter-list"),
            reverse("newsletter-detail", args=[self.newsletter.pk]),
            reverse("subscriptions"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class RegistrationAndPublisherTests(TestCase):
    """Exercise public onboarding and ownership-scoped team management."""

    def signup(self, username, role, **extra):
        """Submit a complete public registration for the requested role."""
        return self.client.post(reverse("signup"), {
            "username": username, "email": f"{username}@example.com",
            "password1": "A-secure-password-123",
            "password2": "A-secure-password-123", "role": role, **extra,
        })

    def test_all_roles_register_without_admin_privileges(self):
        """Each public role receives its group without staff or superuser
        access.
        """
        for role, label in User.Role.choices:
            with self.subTest(role=role):
                response = self.signup(role, role, publisher_name="Daily News")
                self.assertRedirects(response, reverse("login"))
                user = User.objects.get(username=role)
                self.assertEqual(user.role, role)
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertTrue(user.groups.filter(name=label).exists())
                self.assertEqual(
                    user.owned_publishers.count(), int(role == "publisher")
                )

    def test_invalid_registration_does_not_create_partial_accounts(self):
        """Missing or duplicate publisher names and invalid roles create no
        user.
        """
        Publisher.objects.create(name="Taken")
        for index, payload in enumerate([
            {"role": "publisher"},
            {"role": "publisher", "publisher_name": "TAKEN"},
            {"role": "administrator"},
        ]):
            with self.subTest(payload=payload):
                response = self.signup(f"invalid{index}", **payload)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(
                    User.objects.filter(username=f"invalid{index}").exists()
                )

    def test_publisher_can_assign_and_remove_own_team(self):
        """A publicly registered owner can add staff and remove them again."""
        self.signup("owner", "publisher", publisher_name="Owner News")
        self.signup("writer", "journalist")
        self.signup("reviewer", "editor")
        owner = User.objects.get(username="owner")
        writer = User.objects.get(username="writer")
        editor = User.objects.get(username="reviewer")
        publisher = owner.owned_publishers.get()
        self.client.force_login(owner)
        url = reverse("publisher-team", args=[publisher.pk])
        self.assertContains(self.client.get(reverse("dashboard")), url)
        self.assertContains(self.client.get(url), "Owner News team")
        response = self.client.post(
            url, {"editors": [editor.pk], "journalists": [writer.pk]}
        )
        self.assertRedirects(response, url)
        self.assertQuerySetEqual(publisher.editors.all(), [editor])
        self.assertQuerySetEqual(publisher.journalists.all(), [writer])
        self.client.force_login(writer)
        response = self.client.post(reverse("article-create"), {
            "title": "Assigned story", "content": "Team news",
            "publisher": publisher.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Article.objects.filter(
                title="Assigned story", publisher=publisher
            ).exists()
        )
        self.client.force_login(owner)
        self.assertRedirects(self.client.post(url, {}), url)
        self.assertFalse(publisher.editors.exists())
        self.assertFalse(publisher.journalists.exists())

    def test_team_management_rejects_other_owners_and_roles(self):
        """Only the publisher owner can read or change their team."""
        owner = User.objects.create_user("owner", role=User.Role.PUBLISHER)
        publisher = Publisher.objects.create(name="Private Team", owner=owner)
        url = reverse("publisher-team", args=[publisher.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        for role, label in User.Role.choices:
            user = User.objects.create_user(f"other_{role}", role=role)
            self.client.force_login(user)
            for method in [self.client.get, self.client.post]:
                with self.subTest(role=role, method=method.__name__):
                    response = method(url)
                    self.assertEqual(
                        response.status_code,
                        404 if role == "publisher" else 403,
                    )

    def test_wrong_role_and_inactive_team_members_are_rejected(self):
        """Crafted form submissions cannot bypass the staff role filters."""
        owner = User.objects.create_user("owner", role=User.Role.PUBLISHER)
        publisher = Publisher.objects.create(name="Team", owner=owner)
        reader = User.objects.create_user("reader")
        inactive = User.objects.create_user(
            "inactive", role=User.Role.EDITOR, is_active=False
        )
        self.client.force_login(owner)
        url = reverse("publisher-team", args=[publisher.pk])
        for data in [
            {"editors": [reader.pk]},
            {"journalists": [reader.pk]},
            {"editors": [inactive.pk]},
        ]:
            with self.subTest(data=data):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertFalse(publisher.editors.exists())
                self.assertFalse(publisher.journalists.exists())

    def test_publisher_cannot_view_drafts_or_approve_content(self):
        """Publisher registration grants team management without editor
        powers."""
        owner = User.objects.create_user("owner", role=User.Role.PUBLISHER)
        writer = User.objects.create_user("writer", role=User.Role.JOURNALIST)
        draft = Article.objects.create(
            title="Hidden draft", content="Text", author=writer
        )
        self.client.force_login(owner)
        self.assertNotContains(
            self.client.get(reverse("article-list")), "Hidden draft"
        )
        self.assertEqual(
            self.client.get(
                reverse("article-detail", args=[draft.pk])
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/articles/").json(), [])
        self.assertEqual(
            self.client.post(f"/api/articles/{draft.pk}/approve/").status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("article-create")).status_code, 403
        )
