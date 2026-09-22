from datetime import datetime

from rest_framework.response import Response
from rest_framework.views import APIView

from mooring.availability_matrix_serialisers import AvailabilityCellSerialiser, MooringAreaTreeSerialiser
from mooring.models import MooringArea, Mooringsite
from mooring.perms import OfficerPermission
from mooring.utils import generate_mooring_rate, get_campsite_availability

MAX_SITE_IDS = 200
MAX_DATE_SPAN_DAYS = 400


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


class AvailabilityMatrixCellsView(APIView):
    permission_classes = [OfficerPermission]

    def get(self, request, *args, **kwargs):
        site_ids_param = request.query_params.get('site_ids')
        start_date_param = request.query_params.get('start_date')
        end_date_param = request.query_params.get('end_date')

        if not site_ids_param:
            return Response({'error': 'site_ids is required'}, status=400)
        if not start_date_param or not end_date_param:
            return Response({'error': 'start_date and end_date are required'}, status=400)

        site_id_strings = [s for s in site_ids_param.split(',') if s]
        if not site_id_strings or not all(s.isdigit() for s in site_id_strings):
            return Response({'error': 'site_ids must be a comma-separated list of integers'}, status=400)
        if len(site_id_strings) > MAX_SITE_IDS:
            return Response({'error': 'site_ids exceeds the maximum of {}'.format(MAX_SITE_IDS)}, status=400)
        site_ids = [int(s) for s in site_id_strings]

        try:
            start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'start_date and end_date must be in YYYY-MM-DD format'}, status=400)

        if end_date < start_date:
            return Response({'error': 'end_date must not be before start_date'}, status=400)
        if (end_date - start_date).days > MAX_DATE_SPAN_DAYS:
            return Response({'error': 'date span exceeds the maximum of {} days'.format(MAX_DATE_SPAN_DAYS)}, status=400)

        campsites_qs = Mooringsite.objects.filter(id__in=site_ids).select_related('mooringarea')

        availability = get_campsite_availability(
            campsites_qs,
            start_date,
            end_date,
            ongoing_booking=None,
            request=request._request,
        )

        # date range used here must match the day-range get_campsite_availability iterates over internally
        duration = (end_date - start_date).days + 1
        rate_hash = generate_mooring_rate(campsites_qs, start_date, end_date, duration)

        cells = []
        for site in campsites_qs:
            area_open = site.mooringarea.active
            site_open = site.active
            site_results = availability.get(site.pk, {})

            for cell_date, cell_data in site_results.items():
                booking_period_status = cell_data[1]
                bp_result = cell_data[3]

                if not area_open or not site_open:
                    status = 'closed'
                elif not bp_result:
                    status = 'no-data'
                else:
                    statuses = list(booking_period_status.values())
                    closed_count = statuses.count('closed')
                    if closed_count == len(statuses):
                        status = 'closed'
                    elif closed_count > 0:
                        status = 'partial'
                    else:
                        status = 'open'

                mooring_rate = rate_hash.get(cell_date, {}).get(site.pk)
                rate_display = str(mooring_rate.rate.mooring) if mooring_rate else site.price

                cells.append({
                    'site_id': site.pk,
                    'date': cell_date,
                    'status': status,
                    'rate': rate_display,
                })

        serialiser = AvailabilityCellSerialiser(cells, many=True)
        return Response(serialiser.data)

