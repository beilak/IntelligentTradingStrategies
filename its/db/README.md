# Database

Database schema code lives in `its/db`.

Use `DATABASE_URL` for local SQLAlchemy and Alembic commands:

```dotenv
DATABASE_URL=postgresql+psycopg://its:its_password@localhost:5432/its
```

Docker services receive an internal URL that points to the `postgres` service.

Common commands:

```bash
poetry run alembic revision --autogenerate -m "describe change"
poetry run alembic upgrade head
poetry run alembic downgrade -1
```

RSS items are stored in `rss_items` with `pub_date`, `title`, `text`, and
`source` columns.
