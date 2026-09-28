"""Referenced media inventory shared by owner review and audits."""

from collections import defaultdict
from django.apps import apps
from django.db.models import FileField


def referenced_media():
    inventory = defaultdict(list)
    for model in apps.get_models():
        fields = [field for field in model._meta.fields if isinstance(field, FileField)]
        if not fields:
            continue
        for row in model.objects.all().iterator():
            for field in fields:
                file = getattr(row, field.name)
                if file and file.name:
                    inventory[file.name].append({
                        'model': model.__name__, 'id': row.pk,
                        'field': field.name, 'exists': file.storage.exists(file.name),
                    })
    return dict(inventory)
