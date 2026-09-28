# Run the Pebble local showcase

This workspace has three projects:

- Backend: `/home/asif/dark life/django/pebble_backend/pebble`
- Storefront: `/home/asif/dark life/flutter/pebble_type`
- Owner admin: `/home/asif/dark life/flutter/pebble_admin`

The existing local PostgreSQL database and media directory are the catalog source. Keep the backend running at `localhost:8000`; both Flutter apps point there. Browsing is open to guests, but checkout requires a buyer account. Placing an order records it and adjusts stock; no payment is taken.

## Backend

Use the existing private `.env.local` in the backend project. On a new machine, provide `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DJANGO_ALLOWED_HOSTS`. For these two local Flutter web origins, set `DJANGO_DEBUG=true` and `DJANGO_CORS_ALLOW_ALL_ORIGINS=true` only in local development.

```bash
cd "/home/asif/dark life/django/pebble_backend/pebble"
"/home/asif/dark life/django/pebble_backend/venv/bin/python" manage.py migrate
"/home/asif/dark life/django/pebble_backend/venv/bin/python" manage.py runserver 127.0.0.1:8000
```

If an owner account is needed, run `manage.py createsuperuser` with the same Python executable. Restart the backend after applying the Phase 6 data migration so any in-memory home cache is refreshed.

For local password recovery, the backend writes the reset email to its terminal. Open the link printed there to choose a new password. `STOREFRONT_URL` defaults to `http://localhost:3000`; set it if the storefront runs elsewhere. A real mail service requires `DJANGO_EMAIL_BACKEND`, `DJANGO_DEFAULT_FROM_EMAIL`, and the `DJANGO_EMAIL_HOST`/port/user/password/TLS settings. Reset links expire after one hour. After the JWT password revocation setting changes, existing sessions must sign in again.

## Storefront

```bash
cd "/home/asif/dark life/flutter/pebble_type"
flutter pub get
flutter run -d chrome --web-port 3000
```

Open `http://localhost:3000`. Register or sign in as a buyer for checkout.

## Owner admin

```bash
cd "/home/asif/dark life/flutter/pebble_admin"
flutter pub get
flutter run -d chrome --web-port 3001
```

Open `http://localhost:3001` and sign in with a staff account. Edit home sections in **Home Content**, product relationships and images in **Products**, and covers in **Collections**. Refresh the storefront after saving to review the buyer view.

Use **Store Pages** to edit published information page titles and bodies. The product list flags active products that still need a variant; add a variant with the real size and stock through **Products**. The [Phase 9 readiness audit](PHASE9_AUDIT.json) lists outstanding content and material claims for owner review.

Use **Products → Review material** to record supplier or label evidence and explicitly verify a material claim. Unverified material remains stored for editing but is hidden from shoppers. Editing the material or evidence in the product form clears its verification until reviewed again. Use **Photo Rights** to inspect every referenced file, record its rights holder and permission evidence, and approve it for public use. New files start unapproved. The [Phase 10 audit](PHASE10_AUDIT.json) records the remaining review counts; do not mark claims or photos approved without evidence.

Bundle products are added through one atomic cart request. The storefront disables purchase when a product has no available variant. To repeat the Phase 11 PostgreSQL owner-to-buyer check without keeping its temporary changes, run `"/home/asif/dark life/django/pebble_backend/venv/bin/python" scripts/owner_buyer_walkthrough.py --output PHASE11_WALKTHROUGH.json` from this backend directory.

## Verification commands

```bash
cd "/home/asif/dark life/django/pebble_backend/pebble"
"/home/asif/dark life/django/pebble_backend/venv/bin/python" manage.py test --settings=pebble.test_settings
"/home/asif/dark life/django/pebble_backend/venv/bin/python" manage.py check
"/home/asif/dark life/django/pebble_backend/venv/bin/python" manage.py audit_storefront --strict --output PHASE6_AUDIT.json --inventory PHASE6_MEDIA_PROVENANCE.json
"/home/asif/dark life/django/pebble_backend/venv/bin/python" scripts/owner_buyer_walkthrough.py
```

The walkthrough creates temporary owner and buyer actions inside a transaction and rolls them back. In each Flutter project, run `flutter test`, `flutter analyze --no-pub`, and `flutter build web --release --no-wasm-dry-run`. Analysis currently reports informational lints but no errors or warnings.

The photo-rights editor tracks owner approval of referenced media. Confirm licenses and ownership before a public deployment. Shipping charges, tax calculation, and a payment gateway are outside this local showcase.
