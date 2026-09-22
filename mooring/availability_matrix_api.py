from rest_framework.response import Response
from rest_framework.views import APIView

from mooring.availability_matrix_serialisers import MooringAreaTreeSerialiser
from mooring.models import MooringArea
from mooring.perms import OfficerPermission


class AvailabilityMatrixTreeView(APIView):
    permission_classes = [OfficerPermission]

    def get(self, request, *args, **kwargs):
        park = request.query_params.get('park')
        mooring_group = request.query_params.get('mooring_group')

        if park is not None and not park.isdigit():
            return Response({'error': 'park must be an integer'}, status=400)
        if mooring_group is not None and not mooring_group.isdigit():
            return Response({'error': 'mooring_group must be an integer'}, status=400)

        queryset = MooringArea.objects.all().order_by('name').prefetch_related('campsites')

        if park is not None:
            queryset = queryset.filter(park_id=park)
        if mooring_group is not None:
            queryset = queryset.filter(mooringareagroup=mooring_group)

        serialiser = MooringAreaTreeSerialiser(queryset, many=True)
        return Response(serialiser.data)
