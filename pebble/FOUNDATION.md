# Foundation snapshot and local setup

Phase 1 was recorded on 2026-09-26 UTC (2026-09-27 in Dhaka).

## Private snapshot

The snapshot is in `../foundation_backups/20260926T185053Z/`. It contains a
PostgreSQL custom-format dump, the complete `media/` archive, table counts,
SHA-256 hashes, a Pebble reference image, and restore/check reports. Keep this
directory private: the dump can contain customer records. It is on the same
machine as the project, so copy it to another protected location for disaster
recovery before relying on it as the only backup.

The dump was restored into a separate temporary PostgreSQL 18 cluster and all
66 table counts matched. The restored cluster was removed after verification.
The media archive contains all 406 files with matching paths and sizes. After
the configuration change, all 66 live table counts still match the snapshot.

To inspect the dump without touching the live database:

```bash
pg_restore --list ../foundation_backups/20260926T185053Z/database.dump
```

For another restore check, create an empty **separate** database under an
account that can create databases, then run:

```bash
pg_restore --no-owner --no-acl --dbname=YOUR_SEPARATE_DATABASE \
  ../foundation_backups/20260926T185053Z/database.dump
```

Extract the media archive into an empty directory with
`tar -xzf ../foundation_backups/20260926T185053Z/media.tar.gz -C YOUR_EMPTY_DIRECTORY`.
Do not restore either archive over the live project during normal development.

## Local configuration

`pebble/settings.py` reads process environment first, then `.env.local`.
`.env.local` is private and excluded by `.gitignore`. For a fresh local setup,
copy `.env.example` to `.env.local` and supply a unique Django secret and your
PostgreSQL credentials. Use JSON double-quoted values for secrets containing
spaces or special characters. Leave `.env.local` out of commits and screenshots.

The existing local values were moved into `.env.local`; no catalog or media
records were edited. Before any public deployment, rotate the Django secret
and use environment-specific host, CSRF, CORS, and debug settings.

## Repeatable checks

From this directory:

```bash
../venv/bin/python manage.py check
../venv/bin/python manage.py test --settings=pebble.test_settings
```

The test settings use an in-memory SQLite database and a temporary media
directory. They work without PostgreSQL `CREATE DATABASE` privilege or a local
`.env.local` file. The live application continues to use PostgreSQL.

From each Flutter project directory, run `flutter test --no-pub`.

## Reference image

`pebble_reference_home.jpg` is a 2000 × 2496 Pebble theme-store screenshot.
Source: <https://cdn.shopify.com/theme-store/7wlo9a84wrq752oyssxm8txuazp4.jpg?width=2400>.
It is stored for visual comparison, not as a product media asset.
