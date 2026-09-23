# Requirements fixes and validation

Verified on 22 September 2026 against the specified `news_application` folder.

## Changes

- Editor API updates validate publisher membership against the article's author,
  allowing editors to update an existing publisher article without becoming a
  journalist for that publisher.
- `/api/articles/` returns approved content only, with reader subscription
  restrictions retained. `/api/articles/drafts/` provides role-scoped drafts.
- Journalist article revisions require reapproval in browser and API workflows.
  No-op submissions and editor corrections preserve approval.
- Newsletter read queries hide withdrawn articles; reader queries also exclude
  articles from unsubscribed sources. Newsletter article updates return the
  current collection in the API response.
- Former journalists cannot mutate historical articles or newsletters after
  becoming readers. The browser hides their editing links.
- The approval receiver accepts editors or the current journalist author;
  readers cannot write delivery logs.
- Added 11 regression tests, including newsletter CRUD, successful/failed token
  issuance and sharing failures.
- Added `DESIGN.md` with requirements, UI wireframes, entity relationships,
  normalization rationale and explicit interpretations of ambiguous brief text.
- Added an opt-in MariaDB test mode using `NEWS_TEST_DATABASE=mariadb`.

## Verified results

Environment: Python 3.14, Django 6.0.8, Django REST Framework 3.18.1,
mysqlclient 2.3.0; MariaDB server 12.3.3.

| Verification | Result |
|---|---|
| `.venv/bin/python manage.py test` | 48 tests passed on temporary SQLite database |
| `NEWS_TEST_DATABASE=mariadb .venv/bin/python manage.py test --noinput` | 48 tests passed on separate MariaDB test database |
| `.venv/bin/python manage.py check` | No issues |
| `.venv/bin/python manage.py makemigrations --check --dry-run` | No model changes requiring migrations |
| `.venv/bin/python manage.py migrate --check` | No pending migrations |
| MariaDB runtime connection | Confirmed MySQL backend with `mysql_is_mariadb=True` |

## Local database and environment

MariaDB was already running and contained migrations 0001 and 0002. The existing
database was backed up before applying `0003_publisher_accounts`, which adds
nullable publisher ownership and the publisher role. All three news migrations
are now applied. The three existing MariaDB users were preserved.

A dedicated local database account was configured with privileges limited to
`news_application` and its Django test database. The application uses a private,
gitignored `.env` and a project `.venv` containing the declared dependencies.
Credentials are not included in this document or the submission ZIP.

The separate SQLite file was left intact. It contained one user and one
newsletter; those records were not merged into the existing MariaDB database.
The tests create synthetic data in temporary databases and do not change real
application content. Use the MariaDB accounts or register through the website
when running the now-configured application.

## Running locally

From the original project folder:

```bash
source .venv/bin/activate
python manage.py runserver
```

For another computer or an extracted submission ZIP, follow README setup:
create a virtual environment, install requirements, create `.env`, configure
MariaDB credentials, and run migrations. Local credentials and virtual
environments are deliberately not portable submission files.

## Remaining boundaries

Notification behavior is verified with the in-memory email backend and mocked
outgoing requests. The production configuration still uses console email; actual
SMTP delivery has not been configured. The local receiver is tested directly.
The design document records the current design and does not claim to establish
when planning occurred. No browser visual audit or production deployment was
performed as part of these fixes.
