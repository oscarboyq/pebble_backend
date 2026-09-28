"""Run with: python manage.py shell -c 'exec(open("scripts/phase4_owner_walkthrough.py").read())'

Exercises each populated typed owner endpoint against the local database and
rolls back every write. The public home payload must stay identical.
"""
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.test import APIClient

from admin_api.catalog_content_views import EDITORIAL_MODELS

owner_client = APIClient(HTTP_HOST='localhost')
owner_client.force_authenticate(User(username='phase4-audit', is_active=True, is_staff=True))
buyer_client = APIClient(HTTP_HOST='localhost')
before_home = buyer_client.get('/api/home/')
assert before_home.status_code == 200, before_home.status_code
before_catalog_counts = {kind: model.objects.count() for kind, model in EDITORIAL_MODELS.items()}
edited_kinds = []
empty_kinds = []

with transaction.atomic():
    for kind in EDITORIAL_MODELS:
        path = f'/api/admin/home/content/{kind}/'
        listing = owner_client.get(path)
        schema = owner_client.get(f'{path}schema/')
        assert listing.status_code == 200, (kind, listing.status_code)
        assert schema.status_code == 200, (kind, schema.status_code)
        if not listing.data:
            empty_kinds.append(kind)
            continue
        item = listing.data[0]
        field = next((name for name in (
            'is_active', 'order', 'title', 'heading', 'label', 'name', 'text',
            'who_we_are_title', 'store_name', 'newsletter_heading',
        ) if name in item), None)
        assert field is not None, kind
        saved = owner_client.patch(f"{path}{item['id']}/", {field: item[field]}, format='json')
        assert saved.status_code == 200, (kind, saved.status_code, saved.data)
        edited_kinds.append(kind)
    transaction.set_rollback(True)

after_catalog_counts = {kind: model.objects.count() for kind, model in EDITORIAL_MODELS.items()}
assert before_catalog_counts == after_catalog_counts
after_home = buyer_client.get('/api/home/')
assert after_home.status_code == 200
assert before_home.data == after_home.data
print({'editor_kinds': len(EDITORIAL_MODELS), 'round_tripped': len(edited_kinds),
       'empty': empty_kinds, 'public_home_unchanged': True,
       'row_counts_unchanged': True})
