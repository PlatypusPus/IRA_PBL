# Schema changes

The schema lives in `migrations/` as numbered plain SQL files, tracked in the
`schema_migrations` table.

To change it, add `migrations/000N_<what-it-does>.sql` and run:

```sh
uv run wadr migrate
```

Never edit a migration that has already been applied somewhere. That is a hard
rule in [CONTRIBUTING.md](../CONTRIBUTING.md): the next person's database has
already run the old version, and editing it silently diverges the two.

Full reset, which drops all data:

```sh
docker compose down -v && docker compose up -d && uv run wadr migrate
```
