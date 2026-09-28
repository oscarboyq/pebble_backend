from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from home.media_rights import referenced_media
from home.models import MediaRightsRecord


class AdminMediaRightsView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [JSONParser]

    def get(self, request):
        inventory = referenced_media()
        records = MediaRightsRecord.objects.filter(path__in=inventory)
        records = {record.path: record for record in records}
        return Response([
            {
                'path': path,
                'references': len(refs),
                'used_by': sorted({ref['model'] for ref in refs}),
                'file_exists': all(ref['exists'] for ref in refs),
                'source_url': records[path].source_url if path in records else '',
                'rights_holder': records[path].rights_holder if path in records else '',
                'permission_note': records[path].permission_note if path in records else '',
                'approved_for_public': records[path].approved_for_public if path in records else False,
                'reviewed_at': records[path].reviewed_at if path in records else None,
            }
            for path, refs in sorted(inventory.items())
        ])

    def put(self, request):
        path = request.data.get('path')
        inventory = referenced_media()
        if not isinstance(path, str) or path not in inventory:
            return Response({'path': 'Select a currently referenced media file.'}, status=400)
        record = MediaRightsRecord.objects.filter(path=path).first() or MediaRightsRecord(path=path)
        for field in ('source_url', 'rights_holder', 'permission_note'):
            if field in request.data:
                value = request.data[field]
                if not isinstance(value, str):
                    return Response({field: 'Enter text.'}, status=400)
                setattr(record, field, value.strip())
        approved = request.data.get('approved_for_public', False)
        if not isinstance(approved, bool):
            return Response({'approved_for_public': 'Enter true or false.'}, status=400)
        if approved and not (record.rights_holder and record.permission_note):
            return Response({'approved_for_public': 'Rights holder and permission evidence are required.'}, status=400)
        if approved and not all(ref['exists'] for ref in inventory[path]):
            return Response({'approved_for_public': 'Restore the missing file before approval.'}, status=400)
        record.approved_for_public = approved
        record.reviewed_at = timezone.now()
        record.reviewed_by = request.user
        try:
            record.full_clean()
        except ValidationError as exc:
            return Response(exc.message_dict, status=400)
        record.save()
        return Response({'path': record.path, 'approved_for_public': record.approved_for_public})
