from datetime import datetime

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from mooring.availability_matrix_serialisers import (
    AvailabilityCellSerialiser,
    CellDetailSerialiser,
    MooringAreaTreeSerialiser,
)
from mooring.models import MooringArea, Mooringsite, MooringsiteBooking
from mooring.perms import OfficerPermission
from mooring.utils import generate_mooring_rate, get_campsite_availability

MAX_SITE_IDS = 200
MAX_DATE_SPAN_DAYS = 400


def _compute_cell_status(area_open, site_open, booking_period_status, bp_result):
    """Reduce a per-date booking-period status map to a single matrix cell status (most restrictive wins)."""
    if not area_open or not site_open:
        return 'closed'
    if not bp_result:
        return 'no-data'

    statuses = list(booking_period_status.values())
    closed_count = statuses.count('closed')
    if closed_count == len(statuses):
        return 'closed'
    if closed_count > 0:
        return 'partial'
    return 'open'


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

                status = _compute_cell_status(area_open, site_open, booking_period_status, bp_result)

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


class AvailabilityMatrixCellDetailView(APIView):
    permission_classes = [OfficerPermission]

    def get(self, request, *args, **kwargs):
        site_id_param = request.query_params.get('site_id')
        date_param = request.query_params.get('date')

        if not site_id_param or not site_id_param.isdigit():
            return Response({'error': 'site_id must be an integer'}, status=400)
        if not date_param:
            return Response({'error': 'date is required'}, status=400)

        try:
            target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'date must be in YYYY-MM-DD format'}, status=400)

        site = get_object_or_404(Mooringsite.objects.select_related('mooringarea'), pk=int(site_id_param))

        campsites_qs = Mooringsite.objects.filter(pk=site.pk).select_related('mooringarea')

        availability = get_campsite_availability(
            campsites_qs,
            target_date,
            target_date,
            ongoing_booking=None,
            request=request._request,
        )

        rate_hash = generate_mooring_rate(campsites_qs, target_date, target_date, duration=1)
        mooring_rate = rate_hash.get(target_date, {}).get(site.pk)

        cell_data = availability.get(site.pk, {}).get(target_date)
        booking_period_status = cell_data[1] if cell_data else {}
        bp_result = cell_data[3] if cell_data else []

        status = _compute_cell_status(site.mooringarea.active, site.active, booking_period_status, bp_result)

        booking_periods = []
        for bp in bp_result:
            raw_status = booking_period_status.get(bp.pk, 'open')
            booking_periods.append({
                'id': bp.pk,
                'name': bp.period_name,
                'start_time': bp.start_time,
                'finish_time': bp.finish_time,
                'small_price': format(bp.small_price, '.2f') if bp.small_price is not None else None,
                'medium_price': format(bp.medium_price, '.2f') if bp.medium_price is not None else None,
                'large_price': format(bp.large_price, '.2f') if bp.large_price is not None else None,
                'status': raw_status if raw_status == 'open' else 'closed',
            })

        rate = None
        if mooring_rate:
            rate = {
                'price_model': mooring_rate.get_price_model_display(),
                'rate_type': mooring_rate.get_rate_type_display(),
                'mooring': format(mooring_rate.rate.mooring, '.2f'),
                'adult': format(mooring_rate.rate.adult, '.2f') if mooring_rate.rate.adult is not None else None,
                'concession': format(mooring_rate.rate.concession, '.2f') if mooring_rate.rate.concession is not None else None,
                'child': format(mooring_rate.rate.child, '.2f') if mooring_rate.rate.child is not None else None,
                'infant': format(mooring_rate.rate.infant, '.2f') if mooring_rate.rate.infant is not None else None,
                'reason': mooring_rate.reason.text if mooring_rate.reason else None,
                'details': mooring_rate.details,
            }

        bookings = []
        booking_qs = MooringsiteBooking.objects.filter(
            campsite_id=site.pk, date=target_date
        ).exclude(booking_type=4).select_related('booking').order_by('from_dt')
        for booking in booking_qs:
            bookings.append({
                'id': booking.pk,
                'booking_type': booking.get_booking_type_display(),
                'from_dt': booking.from_dt,
                'to_dt': booking.to_dt,
            })

        detail = {
            'site_id': site.pk,
            'site_name': site.name,
            'mooringarea_name': site.mooringarea.name,
            'date': target_date,
            'status': status,
            'rate': rate,
            'booking_periods': booking_periods,
            'bookings': bookings,
        }

        serialiser = CellDetailSerialiser(detail)
        return Response(serialiser.data)

