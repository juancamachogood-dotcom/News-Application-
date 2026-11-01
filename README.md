# News Application

A Django and Django REST Framework capstone for readers, journalists, editors
and publishers. Users register and perform their normal workflows through the
website; the Django admin is only needed for maintenance.

## Setup on macOS

Use Python 3.12 or newer for Django 6, Git, and a terminal. Keep the terminal
inside the project root (the folder containing `manage.py`) for every Python
command below.

### 1. Clone and enter the project

```bash
git clone https://github.com/juancamachogood-dotcom/News-Application-.git news_application
cd news_application
```

The final argument gives the local folder a lowercase name with underscores.
If you received a ZIP instead, extract it and open a terminal inside its
`news_application` folder, then continue at step 2.

### 2. Prepare the database dependencies

MariaDB is the application's default database. With Homebrew installed:

```bash
brew install mariadb pkg-config
brew services start mariadb
```

The Python `mysqlclient` dependency needs the MariaDB/MySQL development libraries
and a compiler. If its installation reports a missing compiler, install Apple's
command-line tools with `xcode-select --install`, then retry step 3. See the
[mysqlclient installation guide](https://github.com/PyMySQL/mysqlclient#macos-homebrew)
for platform-specific setup.

### 3. Create the virtual environment and install dependencies

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Check that `python3 --version` reports 3.12 or later before creating the virtual
environment. On a new terminal session, return to this folder and activate
`.venv` again.

### 4. Configure the environment file

```bash
cp .env.example .env
```

Open `.env` in your editor. Set `DJANGO_SECRET_KEY` to a unique random value.
You can generate one with:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(50))'
```

Keep `DB_ENGINE=mariadb`, and set `DB_PASSWORD` to a password you choose.
`news_project/settings.py` uses `python-dotenv` to load this project-root `.env`
automatically. Existing shell environment variables take precedence; remove any
old conflicting exports from earlier setup attempts. Do not commit `.env`.

### 5. Create the MariaDB database

Open `mariadb` using your local database administrator account. Execute:

```sql
CREATE DATABASE news_application CHARACTER SET utf8mb4;
CREATE USER 'news_user'@'127.0.0.1' IDENTIFIED BY 'replace-with-your-password';
GRANT ALL PRIVILEGES ON news_application.* TO 'news_user'@'127.0.0.1';
FLUSH PRIVILEGES;
EXIT;
```

Replace the password in the SQL with the same value as `DB_PASSWORD` in `.env`.
The host, database and username must also match `.env`. For an existing database,
keep its credentials and skip the creation commands.

For a lightweight local demonstration, you may instead set `DB_ENGINE=sqlite`
in `.env` and skip the MariaDB creation commands. The next step creates a fresh
`db.sqlite3` in the project root. SQLite is also used by the automated tests by default.
The standard requirements still include the MariaDB driver.

### 6. Create tables and run the application

```bash
python manage.py migrate
python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser. Register at
**http://127.0.0.1:8000/accounts/signup/**, then sign in. Stop the server with
`Control+C`.

An optional maintenance administrator can be created with
`python manage.py createsuperuser` and used at `/admin/`. This is not required
for normal registration, publishing, editing or team assignment.

## Try the role workflows

1. Register a **Publisher** and supply a unique publisher name. Sign in and open
   **Manage [publisher name] team** from the dashboard.
2. Sign out and register separate **Journalist** and **Editor** accounts.
3. Sign in as the publisher, select these registered users on the team page,
   and click **Save team**. Unchecking users and saving removes their membership.
   An owner can manage only their own publisher. New publisher accounts do not
   claim existing publisher records by name.
4. Sign in as the journalist, choose **Write article**, select the assigned
   publisher, and save a draft. Journalists may also write independently by
   leaving the publisher blank.
5. Sign in as the editor, open **Review queue**, and approve the draft.
6. Register a **Reader**, sign in, and use **Subscriptions** to follow the
   publisher or journalist. The approved article then appears in the feed.

Editors retain the project's existing editorial access across the newsroom;
team membership does not restrict editors to a publisher-specific review queue.
Publisher accounts manage teams but cannot create or approve articles. No public
registration grants Django staff or superuser privileges.

Changing an article's title, content or publisher as a journalist returns it to
the review queue. Unchanged submissions preserve approval, and editors can make
editorial corrections without withdrawing approval. Newsletters hide withdrawn
articles and restrict reader article previews to subscribed sources.

Approval notifications are printed in the server terminal using Django's console
email backend. The approval integration posts to the local `/api/approved/`
endpoint; it does not post to a social network.

## Project structure

```text
news_application/
├── manage.py
├── requirements.txt
├── .env.example
├── news_project/              # Settings, root URLs and WSGI
├── templates/
│   ├── base.html             # Shared site layout
│   ├── 403.html
│   └── registration/login.html
├── news/
│   ├── models.py, forms.py, views.py, ...
│   ├── migrations/           # Recreate the database schema
│   ├── templates/news/       # App-specific pages and partials
│   └── static/news/          # App stylesheet
└── tests.py                  # Additional API and browser tests
```

## Database and submission files

Database files, `.env`, virtual environments and generated Python caches are
excluded by `.gitignore`. Submit source code and migrations, not your local
SQLite database or a database dump. On a fresh installation, the database setup
above followed by `python manage.py migrate` recreates the schema. Users and
content are then created through the website.

Migration `0003_publisher_accounts` adds publisher ownership and the publisher
role without deleting existing records. Existing publishers retain their staff
and have no owner until an administrator assigns the correct account during
maintenance. Existing databases should be backed up before upgrades. If upgrading
an older SQLite installation that stored `news_project/db.sqlite3`, move that
file to `db.sqlite3` in the root before running migrations.

## Browser routes

- `/accounts/signup/` — public registration for all four roles
- `/accounts/login/` — sign in
- `/dashboard/` — role-specific overview
- `/publishers/<id>/team/` — publisher-owner team management
- `/articles/` and `/articles/new/` — article feed and journalist submission
- `/newsletters/` and `/newsletters/new/` — newsletter feed and creation
- `/subscriptions/` — reader subscriptions
- `/editor/review/` — editor approval queue

## API

- `POST /api/token/` — obtain a token with username and password
- `GET /api/articles/` — approved articles, restricted to subscriptions for readers
- `GET /api/articles/drafts/` — editors’ drafts or the journalist’s own drafts
- `GET /api/articles/subscribed/` — reader's subscribed approved articles
- `POST /api/articles/` — journalist draft creation
- `GET|PUT|DELETE /api/articles/<id>/` — permitted article operations
- `POST /api/articles/<id>/approve/` — editor approval
- `/api/newsletters/` — newsletter CRUD with role controls
- `GET /api/publishers/` — publisher listing
- `POST /api/approved/` — local integration receiver

Authenticate API calls with `Authorization: Token <token>`.
Registration and team management are browser workflows.

## Tests and checks

Run these from the project root with `.venv` activated:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Tests default to a temporary SQLite test database and mock the outgoing
approval integration. They cover registration for all roles, duplicate email
and publisher names, publisher ownership, team role validation, team removal,
article creation, subscription filtering, editor approval and denied access.
Regression coverage also includes full editor article updates, draft feed
separation, reapproval after revisions, newsletter CRUD and visibility, former
author permissions, token issuance, and failed sharing requests.

To run the same suite on MariaDB, keep `DB_ENGINE=mariadb` in `.env`, then use:

```bash
NEWS_TEST_DATABASE=mariadb python manage.py test
```

Django creates and removes `test_news_application`, separate from your application
database. The configured database user needs privileges on that test database.
For the example user above, an administrator can grant them with:

```sql
GRANT ALL PRIVILEGES ON test_news_application.* TO 'news_user'@'127.0.0.1';
```

Adjust the name and host to match your own configuration. Never point the test
configuration at an existing database containing data you need.

## Requirements and validation

- [Requirements, UI wireframes and normalized database design](docs/DESIGN.md)
- [Verification results and local MariaDB migration notes](docs/VALIDATION.md)

The development settings and runserver workflow here are for local coursework.

## References

- [Django installation](https://docs.djangoproject.com/en/6.0/intro/install/)
- [python-dotenv configuration](https://bbc2.github.io/python-dotenv/)
- [PEP 257 docstring conventions](https://peps.python.org/pep-0257/)


## Run with Docker Desktop

Start Docker Desktop and open a terminal in the project root.

This setup runs the application locally using SQLite and Django's
development server.

### Build the image

```bash
docker --context desktop-linux build --builder desktop-linux --load -t news-application:local .
```

### Configure the application

If you do not already have a `.env` file, copy `.env.example` to `.env`.
Set `DJANGO_SECRET_KEY` to your own random secret, following the environment
configuration instructions above. Keep `.env` private.

The command below selects SQLite, overriding the MariaDB setting in `.env`.
No MariaDB server is needed for this Docker demonstration.

### Create and start the container

Run this once when creating a new container:

```bash
docker --context desktop-linux run \
  --name news-capstone \
  --pull=never \
  --env-file .env \
  --env DB_ENGINE=sqlite \
  -p 127.0.0.1:8000:8000 \
  news-application:local
```

Database migrations run automatically when the container starts.

Open http://127.0.0.1:8000/ in your browser, then register and sign in.
Use this browser address even though the server logs display `0.0.0.0`.

### Stop and restart

Press Control+C in the terminal running the application to stop it.

To restart the existing container:

```bash
docker --context desktop-linux start -a news-capstone
```


Accounts and content remain when this container is stopped and restarted.
They are stored inside the container; removing it deletes that database.
Rebuilding the image does not update an existing container.

### Run automated tests

While the container is running, open another terminal and run:

```bash
docker --context desktop-linux exec news-capstone python manage.py test --verbosity 2
```

The tests use a separate temporary test database.

## Build and view the documentation

The project uses Sphinx to document its models, permissions and notification
services. Generated HTML is included in the repository for this capstone.

From the project root, activate the virtual environment created during setup
and install the documentation dependencies:

```bash
source .venv/bin/activate
python -m pip install -r requirements-docs.txt
```

Build the HTML documentation:

```bash
python -m sphinx -b html -W --keep-going docs docs/_build/html
```

The `-W` option makes documentation warnings count as build failures.

On macOS, open the generated documentation with:

```bash
open docs/_build/html/index.html
```

Rebuild the documentation after changing documented Python code or the
documentation source files. Keep the updated HTML in the repository.