import hashlib
import logging
import calendar
from django_crispy_jcaptcha.widget import CaptchaImages
import json
import os
import mimetypes
import requests
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.serializers.json import DjangoJSONEncoder
from django.views.generic.base import View, TemplateView
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django import forms
from django.contrib import messages
from mooring import forms as app_forms
from mooring.forms import LoginForm, MakeBookingsForm, AnonymousMakeBookingsForm, VehicleInfoFormset
from mooring import models
from mooring.models import (MooringArea,
                                MooringsiteBooking,
                                Mooringsite,
                                MooringsiteRate,
                                Booking,
                                BookingInvoice,
                                PromoArea,
                                MarinePark,
                                Feature,
                                Region,
                                MooringsiteClass,
                                Booking,
                                BookingVehicleRego,
                                MooringsiteRate,
                                MarinaEntryRate,
                                AdmissionsBooking,
                                AdmissionsLine,
                                AdmissionsLocation,
                                AdmissionsBookingInvoice,
                                AdmissionsRate,
                                DiscountReason,
                                RegisteredVessels,
                                ChangePricePeriod,
                                AdmissionsOracleCode,
                                MooringAreaGroup,
                                GlobalSettings,
                                MooringsiteRateLog,
                                ChangeGroup,
                                CancelGroup,
                                ChangePricePeriod,
                                CancelPricePeriod,
                                BookingPeriod,
                                BookingPeriodOption,
                                RefundFailed,
                                AnnualBookingPeriodGroup,
                                AnnualBookingPeriodOption,
                                VesselSizeCategory,
                                AnnualBookingPeriodOptionVesselCategoryPrice,
                                BookingAnnualAdmission,
                                BookingAnnualInvoice,
                                VesselDetail
                                )

from mooring.serialisers import AdmissionsBookingSerializer, AdmissionsLineSerializer
from mooring import emails
# Ledger 
# from ledger.accounts.models import EmailUser, Address
# from ledger.payments.models import Invoice
# from ledger.basket.models import Basket
from ledger_api_client.ledger_models import EmailUserRO as EmailUser, Address, Invoice, Basket
# from ledger.payments.bpoint.models import BpointTransaction, BpointToken
class BpointTransaction():
    pass
# from ledger.payments.utils import systemid_check, update_payments
# from ledger.checkout.utils import place_order_submission 
from ledger_api_client.utils import update_payments, place_order_submission, get_or_create, Order
# from ledger.payments.cash.models import CashTransaction 
# Ledger
# from ledger.order.models import Order
from django_ical.views import ICalFeed
from datetime import datetime, timedelta, date
from decimal import *
from pytz import timezone as pytimezone
import hashlib
import logging

from mooring.helpers import is_officer, is_payment_officer
from mooring import utils
# from ledger.payments.mixins import InvoiceOwnerMixin
from ledger_api_client.mixins import InvoiceOwnerMixin
# from mooring.invoice_pdf import create_invoice_pdf_bytes
from mooring.context_processors import mooring_url, template_context
# from ledger.checkout.utils import create_basket_session, create_checkout_session, place_order_submission, get_cookie_basket
from ledger_api_client.utils import create_basket_session, create_checkout_session, place_order_submission, process_api_refund 
# from ledger.payments.invoice import utils as utils_ledger_payment_invoice


logger = logging.getLogger('booking_checkout')


class MooringsiteBookingSelector(TemplateView):
    template_name = 'mooring/campsite_booking_selector.html'

class MooringsiteAvailabilitySelector(TemplateView):
    template_name = 'mooring/campsite_booking_selector.html'

    def get(self, request, *args, **kwargs):
        # if page is called with ratis_id, inject the ground_id
        context = {}
        ratis_id = request.GET.get('mooring_site_id', None)
        if ratis_id:
            cg = MooringArea.objects.filter(ratis_id=ratis_id)
            if cg.exists():
                context['ground_id'] = cg.first().id
        return render(request, self.template_name, context)

class MooringAvailability2Selector(TemplateView):
    template_name = 'mooring/mooring_availability_booking_selector.html'

    def get(self, request, *args, **kwargs):
        # if page is called with ratis_id, inject the ground_id
        num_adults = request.POST.get('num_adult', 0)
        num_children = request.POST.get('num_children', 0)
        num_infants = request.POST.get('num_infant',0)
        vessel_size = request.GET.get('vessel_size', 0)
        vessel_draft = request.GET.get('vessel_draft', 0)
        vessel_beam = request.GET.get('vessel_beam', 0)
        vessel_weight = request.GET.get('vessel_weight', 0)
        vessel_rego = request.GET.get('vessel_rego', 0)
    
        booking_period_start = datetime.strptime(request.GET['arrival'], "%Y/%m/%d").date()
        booking_period_finish = datetime.strptime(request.GET['departure'], "%Y/%m/%d").date()

        context = {}
        ratis_id = request.GET.get('mooring_site_id', None)
        if ratis_id:
            cg = MooringArea.objects.filter(ratis_id=ratis_id)
            if cg.exists():
                context['ground_id'] = cg.first().id

        booking = None
        # Accept booking_uuid from URL parameter (e.g. change booking redirect)
        booking_uuid_param = request.GET.get('booking_uuid')
        if booking_uuid_param:
            existing = Booking.objects.filter(uuid=booking_uuid_param, booking_type=3).first()
            if existing:
                context['booking_uuid'] = str(existing.uuid)

        if 'booking_uuid' not in context:
            # Create a new temporary booking
            details = {
               'num_adults' : num_adults,
               'num_children' : num_children,
               'num_infants' : num_infants,
               'vessel_size' : vessel_size,
               'vessel_draft': vessel_draft,
               'vessel_beam' : vessel_beam,
               'vessel_weight' : vessel_weight,
               'vessel_rego' : vessel_rego,
            }
#            mooring_site = Mooringsite.objects.get(id=ratis_id)
            mooringarea = MooringArea.objects.get(id=request.GET.get('site_id', None))
            booking = Booking.objects.create(
                mooringarea=mooringarea,
                booking_type=3,
                expiry_time=timezone.now()+timedelta(seconds=settings.BOOKING_TIMEOUT),
                details=details,
                arrival=booking_period_start,
                departure=booking_period_finish
            )
            logger.info(f'New Booking: [{booking}] has been created.')
            context['booking_uuid'] = str(booking.uuid)

        return render(request, self.template_name, context)

class AvailabilityAdmin(TemplateView):
    template_name = 'mooring/availability_admin.html'

class MooringAreaFeed(ICalFeed):
    timezone = 'UTC+8'

    # permissions check
    def __call__(self, request, *args, **kwargs):
        if not is_officer(self.request.user):
            raise Http403('Insufficient permissions')

        return super(ICalFeed, self).__call__(request, *args, **kwargs)

    def get_object(self, request, ground_id):
        # FIXME: add authentication parameter check
        return MooringArea.objects.get(pk=ground_id)

    def title(self, obj):
        return 'Bookings for {}'.format(obj.name)

    def items(self, obj):
        now = datetime.utcnow()
        low_bound = now - timedelta(days=60)
        up_bound = now + timedelta(days=90)
        return Booking.objects.filter(campground=obj, arrival__gte=low_bound, departure__lt=up_bound).order_by('-arrival','campground__name')

    def item_link(self, item):
        return 'http://www.geocities.com/replacethiswithalinktotheadmin'

    def item_title(self, item):
        return item.legacy_name

    def item_start_datetime(self, item):
        return item.arrival

    def item_end_datetime(self, item):
        return item.departure

    def item_location(self, item):
        return '{} - {}'.format(item.campground.name, ', '.join([
            x[0] for x in item.campsites.values_list('campsite__name').distinct()
        ] ))

class DashboardAnnualAdmissionView(UserPassesTestMixin, ListView):
    template_name = 'mooring/dash/dash_tables_annual_admissions.html'
    model = BookingAnnualAdmission

    def get(self, request, *args, **kwargs):
        if is_officer(request.user) == True:
            return super(DashboardAnnualAdmissionView, self).get(request, *args, **kwargs)
        else:
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(DashboardAnnualAdmissionView, self).get_context_data(**kwargs)
        request = self.request
        nowdt = datetime.strptime(str(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
        context['status'] = 0
        context['keyword'] = ''
        baainvoices_temp = {}
        anpg = []
        pg = AnnualBookingPeriodGroup.objects.all()
        mooring_groups = MooringAreaGroup.objects.filter(members__in=[self.request.user,])

        for f in pg:
             if f.mooring_group in mooring_groups: 
                  anpg.append(f)

        context['annual_booking_period_group'] = anpg
        #baainvoices = BookingAnnualInvoice.objects.select_related('booking_annual_admission').values('booking_annual_admission__id','invoice_reference').filter(Q(booking_annual_admission__booking_type=1) | Q(booking_annual_admission__booking_type=4))
        #for b in baainvoices:
        #    baainvoices_temp[b['booking_annual_admission__id']] = []
        #    baainvoices_temp[b['booking_annual_admission__id']].append(b['invoice_reference'])
        #baa = []
        #baarows = BookingAnnualAdmission.objects.filter(Q(booking_type=1) | Q(booking_type=4))
        #for c in baarows:
        #    start_dt = datetime.strptime(str(c.start_dt.strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
        #    expiry_dt = datetime.strptime(str(c.expiry_dt.strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')

        #    row = {}
        #    row['id'] = c.id
        #    row['customer_name'] = c.customer.first_name+' '+c.customer.last_name
        #    row['customer'] = c.customer
        #    row['start_dt'] = c.start_dt
        #    row['expiry_dt'] = c.expiry_dt
        #    row['details'] = c.details
        #    row['booking_type'] = c.booking_type
        #    row['annual_booking_period_group'] = c.annual_booking_period_group.id
        #    row['cost_total'] = c.cost_total
        #    row['override_price'] = c.override_price
        #    row['override_reason'] = c.override_reason
        #    row['override_reason_info'] = c.override_reason_info
        #    row['overridden_by'] = c.overridden_by
        #    row['is_canceled'] = c.is_canceled
        #    row['send_invoice'] = c.send_invoice
        #    row['cancellation_reason'] = c.cancellation_reason
        #    row['cancelation_time'] = c.cancelation_time
        #    row['confirmation_sent'] = c.confirmation_sent
        #    row['created'] = c.created
        #    row['created_by'] = c.created_by
        #    row['canceled_by'] = c.canceled_by
        #    row['override_lines'] = c.override_lines
        #    row['sticker_no'] = c.sticker_no

        #    if c.id in baainvoices_temp:
        #        row['invoices'] = baainvoices_temp[c.id]
        #    if c.booking_type == 1:
        #        row['status'] = 'current'
        #        if expiry_dt < nowdt:
        #            row['status'] = 'expired'
        #        if start_dt > nowdt:
        #            row['status'] = 'future'

        #    baa.append(row)

        #context['baa'] = baa


        #if 'status' in self.request.GET:
        #    context['status'] = self.request.GET['status']
        #if 'keyword' in self.request.GET:
        #    context['keyword'] = self.request.GET['keyword']

        #if is_payment_officer(request.user) == True:
        #    if 'status' in self.request.GET:
        #        context['status'] = self.request.GET['status']
        #    if 'keyword' in self.request.GET:
        #        context['keyword'] = self.request.GET['keyword']
        #    if context['status'] == 'ALL':
        #        query = Q()
        #    else:
        #        query = Q(status=context['status'])
        #    if context['keyword'].isdigit():
        #        query &= Q(Q(invoice_reference__icontains=context['keyword']) | Q(booking_id=int(context['keyword'])))
        #    else:
        #        query &= Q(Q(invoice_reference__icontains=context['keyword']))
        #    failrefunds_list =[]
        #    failrefunds = RefundFailed.objects.filter(query)
        #    mg = MooringAreaGroup.objects.all()
        return context

    def get_initial(self):
        initial = super(DashboardAnnualAdmissionView, self).get_initial()
        initial['action'] = 'list'
        return initial

    def test_func(self):
        return is_officer(self.request.user)


class DashboardView(UserPassesTestMixin, TemplateView):
    template_name = 'mooring/dash/dash_tables_campgrounds.html'

    def test_func(self):
        return is_officer(self.request.user)

def abort_booking_view(request, *args, **kwargs):
    try:
        change = bool(request.GET.get('change',False))
        change_ratis = request.GET.get('change_ratis',None)
        change_id = request.GET.get('change_id',None)
        change_to = None
        booking_uuid = request.GET.get('booking_uuid')
        booking = utils.get_booking_from_uuid_or_session(booking_uuid)
        if not booking:
            raise Exception('No booking found for abort')
        if change_ratis:
            try:
                c_id = MooringArea.objects.get(ratis_id=change_ratis).id
            except:
                c_id = booking.mooringarea.id
        elif change_id:
            try:
                c_id = MooringArea.objects.get(id=change_id).id
            except:
                c_id = booking.mooringarea.id
        else:
            c_id = booking.mooringarea.id
        
        if change:
            num_adults = booking.details['num_adult']
            num_children = booking.details['num_children']
            num_infants = booking.details['num_infant']
            vessel_size = booking.details['vessel_size']
            vessel_draft = booking.details['vessel_draft']
            vessel_beam = booking.details['vessel_beam']
            vessel_weight = booking.details['vessel_weight']
            vessel_rego = booking.details['vessel_rego']
            # Redirect to the availability screen
            #return redirect(reverse('campsite_availaiblity_selector') + '?site_id={}'.format(c_id)) 
            #mooring_availaiblity2_selector
            # +str(booking.mooringarea_id)+'&arrival='+str(booking.arrival.strftime('%Y/%m/%d'))+'&departure='+str(booking.departure.strftime('%Y/%m/%d'))
            return redirect(reverse('mooring_availaiblity2_selector') + '?site_id={}&num_adult={}&num_children={}&num_infant={}&vessel_size={}&vessel_draft={}&vessel_beam={}&vessel_weight={}&vessel_rego={}&arrival={}&departure={}'.format(c_id, num_adults, num_children, num_infants, vessel_size, vessel_draft, vessel_beam, vessel_weight, vessel_rego, booking.arrival.strftime('%Y/%m/%d'), booking.departure.strftime('%Y/%m/%d')))
        else:
            # only ever delete a booking object if it's marked as temporary
            if booking.booking_type == 3:
                booking.delete()
            # Redirect to explore parks
            return redirect('map')
    except Exception as e:
        pass
    return redirect('public_make_booking')

class CancelBookingView(TemplateView):
    template_name = 'mooring/booking/cancel_booking.html'

    def get_booking_info(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = Booking.objects.get(pk=booking_id)
        bpoint_id = None
        booking_invoice = BookingInvoice.objects.filter(booking=booking)
        for bi in booking_invoice:
            inv = Invoice.objects.filter(reference=bi.invoice_reference)
            for i in inv:
                for b in i.bpoint_transactions:
                   if b.action == 'payment':
                      bpoint_id = b.id

        return bpoint_id

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None
        occ = request.GET.get('occ', 'false')
        booking_total = Decimal('0.00')
        overide_cancel_fees = False

        payments_officer_group = False
        if request.user.is_authenticated:
            payments_officer_group = request.user.groups().filter(name='Payments Officers').exists()

        if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(customer=request.user,pk=booking_id).count() == 1:
             booking = Booking.objects.get(pk=booking_id)
             if booking.booking_type == 4:
                  print ("BOOKING HAS BEEN CANCELLED")
                  return HttpResponseRedirect(reverse('home'))
        if occ == 'true':
            if payments_officer_group:
                overide_cancel_fees = True

#        booking_cancellation_fees = []
        booking_cancellation_fees = utils.calculate_price_booking_cancellation(booking, overide_cancel_fees)
        booking_cancellation_fees = utils.calculate_price_admissions_cancel(booking.admission_payment, booking_cancellation_fees, overide_cancel_fees)
        booking_total = Decimal('{0:.2f}'.format(booking_total + Decimal(sum(Decimal(i['amount']) for i in booking_cancellation_fees))))
        basket = {}

        response = render(request, self.template_name, {'booking': booking,'basket': basket, 'booking_fees': booking_cancellation_fees, 'booking_total': booking_total, 'booking_total_positive': booking_total - booking_total - booking_total, 'occ': occ, 'payments_officer_group': payments_officer_group, 'is_staff': request.user.is_staff})
        response.delete_cookie(settings.OSCAR_BASKET_COOKIE_OPEN)
        return response

    def post(self, request, *args, **kwargs):
        overide_cancel_fees = False
        occ = request.POST.get('occ', 'false')
        cancellation_reason = request.POST.get('cancellation_reason','')
        payments_officer_group = False
        if request.user.is_authenticated:
            payments_officer_group = request.user.groups().filter(name='Payments Officers').exists()
        failed_refund = False

        if occ == 'true':
            if payments_officer_group:
                overide_cancel_fees = True

        context_processor = template_context(request)
        booking_id = kwargs['pk']
        booking_total = Decimal('0.00')
        basket_total = Decimal('0.00')
        booking = None
        invoice = None
        booking_admission = None
        if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(customer=request.user,pk=booking_id).count() == 1:
             booking = Booking.objects.get(pk=booking_id)
             if booking.booking_type == 4:
                  logger.info(f'Booking: [{booking.id}] has already been cancelled.')
                  return HttpResponseRedirect(reverse('home'))
        
        # bpoint_id = self.get_booking_info(self, request, *args, **kwargs)
        booking_cancellation_fees = utils.calculate_price_booking_cancellation(booking, overide_cancel_fees)
        if booking.admission_payment:
            booking_admission = AdmissionsBooking.objects.get(pk=booking.admission_payment_id)
            booking_cancellation_fees = utils.calculate_price_admissions_cancel(booking.admission_payment, booking_cancellation_fees, overide_cancel_fees)
        booking_total = Decimal('{0:.2f}'.format(booking_total + Decimal(sum(Decimal(i['amount']) for i in booking_cancellation_fees))))

#        booking_total = booking_total + sum(Decimal(i['amount']) for i in booking_cancellation_fees)
#        booking_total =  Decimal('{:.2f}'.format(float(booking_total - booking_total - booking_total)))

        ## PLACE IN UTILS
        lines = []
        for cf in booking_cancellation_fees:
            lines.append({
                'ledger_description': cf['description'],
                "quantity": 1,
                "price_incl_tax": cf['amount'],
                "oracle_code": cf['oracle_code'],
                'line_status': 3
            })

        basket_params = {
            'products': lines,
            'vouchers': [],
            'system': settings.PS_PAYMENT_SYSTEM_ID,
            'custom_basket': True,
            'booking_reference': settings.MOORING_BOOKING_REF_PREFIX + str(booking.id),
            'booking_reference_link': settings.MOORING_BOOKING_REF_PREFIX + str(booking.id)
        }

        basket_params = utils.convert_decimal_to_float(basket_params)
        basket_hash = create_basket_session(request, request.user.id, basket_params)
        basket = utils.get_basket_by_basket_hash(basket_hash)
        # ci = utils_ledger_payment_invoice.CreateInvoiceBasket()
        # order_ci  = ci.create_invoice_and_order(basket, total=None, shipping_method='No shipping required',shipping_charge=False, status='Submitted', invoice_text='Refund Allocation Pool', user=booking.customer)
        #basket.status = 'Submitted'
        #basket.save() 
#        print (basket)
#        print (basket_hash)
#
#        checkout_params = {
#            'system': settings.PS_PAYMENT_SYSTEM_ID,
#            'fallback_url': request.build_absolute_uri('/'),
#            'return_url': request.build_absolute_uri(reverse('public_admissions_success')),
#            'return_preload_url': request.build_absolute_uri(reverse('public_admissions_success')),
#            'force_redirect': True,
#            'proxy': False,
#            'invoice_text': "Cancellation of Booking",
#            'basket_owner': booking.customer.id
#        }
#        create_checkout_session(request, checkout_params)
#        # END PLACE IN UTILS
#        order_response = place_order_submission(request)

        # new_order = Order.objects.get(basket=basket)
        # new_invoice = Invoice.objects.get(order_number=new_order.number)
        # update_payments(new_invoice.reference)
        # book_inv, created = BookingInvoice.objects.get_or_create(booking=booking, invoice_reference=new_invoice.reference)

        #basket.status = 'Submitted'
        #basket.save()

        #print new_order.basket
        #print basket.status
        b_total = Decimal('{:.2f}'.format(float(booking_total - booking_total - booking_total)))
        info = {'amount': Decimal('{:.2f}'.format(float(booking_total - booking_total - booking_total))), 'details' : 'Refund via system'}
#         info = {'amount': float('10.00'), 'details' : 'Refund via system'}
        refund = None

        checkouthash =  hashlib.sha256(str(booking.pk).encode('utf-8')).hexdigest()
        logger.info(f"checkouthash: [{checkouthash}] has been generated from the booking.pk: [{booking.pk}].")
        # utils.set_session_checkouthash(request.session, checkouthash)

        return_url = request.build_absolute_uri()+"/booking/cancellation-success/?checkouthash="+checkouthash
        return_preload_url = request.build_absolute_uri()+"/booking/return-cancelled/"
        jsondata = process_api_refund(request, basket_params, booking.customer.id, return_url, return_preload_url)
        if jsondata['message'] == 'success':
            for ir in jsondata['data']['invoice_reference']:
                # Link the refund invoice to the booking  (Ref: https://github.com/dbca-wa/parkstay_bs_v2/blob/63895cd92193cebe003f53bb2866ce7346006d40/parkstay/views.py#L816)
                BookingInvoice.objects.get_or_create(booking=booking, invoice_reference=ir)
            emails.send_refund_completed_email_customer(booking, context_processor)
        else:
            emails.send_refund_failure_email(booking, context_processor)
            emails.send_refund_failure_email_customer(booking, context_processor)


        try: 
            # bpoint = BpointTransaction.objects.get(id=bpoint_id)
            # refund = bpoint.refund(info,request.user)
            # invoice = Invoice.objects.get(reference=bpoint.crn1)
            # update_payments(invoice.reference)
            emails.send_refund_completed_email_customer(booking, context_processor)
 
        except:
            failed_refund = True
#            # Refund Failed Assign Refund amount to allocation pool.
#            lines = [{'ledger_description':'Refund assigned to unallocated pool',"quantity":1,"price_incl_tax":info['amount'],"oracle_code":settings.UNALLOCATED_ORACLE_CODE, 'line_status': 1}]
#            utils.allocate_failedrefund_to_unallocated(request, booking, lines, invoice_text=None, internal=False)
#            #######################################################
 
            emails.send_refund_failure_email(booking, context_processor)
            emails.send_refund_failure_email_customer(booking, context_processor)
         
            # booking_invoice = BookingInvoice.objects.filter(booking=booking).order_by('id')
            # for bi in booking_invoice:
            #     invoice = Invoice.objects.get(reference=bi.invoice_reference)
            # RefundFailed.objects.create(booking=booking, invoice_reference=invoice.reference, refund_amount=b_total,status=0, basket_json=None)



        # new_invoice.settlement_date = None
        # new_invoice.save()

        # if refund:
        #     print ("DID REFUND HAPPEN")
        #     bpoint_refund = BpointTransaction.objects.get(txn_number=refund.txn_number)
        #     bpoint_refund.crn1 = new_invoice.reference
        #     bpoint_refund.save()


        # update_payments(invoice.reference)
        # update_payments(new_invoice.reference)
 
        # invoice.voided = True
        # invoice.save()
        booking.booking_type = 4  # This means is_canceled=True
        booking.cancelation_time = datetime.now() 
        booking.canceled_by = request.user
        booking.cancellation_reason = cancellation_reason
        booking.save()
        emails.send_booking_cancellation_email_customer(booking, context_processor)

        if booking.admission_payment:
            booking_admission.booking_type = 4
            booking_admission.cancelation_time = datetime.now()
            booking_admission.canceled_by = request.user
            booking_admission.cancellation_reason = cancellation_reason
            booking_admission.save()

        # update_payments(invoice.reference)
        # update_payments(new_invoice.reference)

        # if failed_refund is True:
        #     # Refund Failed Assign Refund amount to allocation pool.
        #     lines = [{'ledger_description':'Refund assigned to unallocated pool',"quantity":1,"price_incl_tax":abs(info['amount']),"oracle_code":settings.UNALLOCATED_ORACLE_CODE, 'line_status': 1}]
        #     utils.allocate_failedrefund_to_unallocated(request, booking, lines, invoice_text=None, internal=False,order_total=abs(info['amount']),user=booking.customer)

        return HttpResponseRedirect(reverse('public_booking_cancelled', args=(booking.id,)))


class CancelAdmissionsBookingView(TemplateView):
    template_name = 'mooring/admissions/cancel_booking.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None
        booking_total = Decimal('0.00')
        overide_cancel_fees=False
        if request.user.is_staff or request.user.is_superuser or AdmissionsBooking.objects.filter(customer_id=request.user.id,pk=booking_id).count() == 1:
            booking = AdmissionsBooking.objects.get(pk=booking_id)
            if booking.booking_type == 4:
                print ("ADMISSIONS BOOKING HAS BEEN CANCELLED")
                return HttpResponseRedirect(reverse('home'))


        if request.user.is_authenticated:
            if request.user.groups().filter(name='Mooring Admin').exists():
                overide_cancel_fees=True
          
        booking_cancellation_fees = utils.calculate_price_admissions_cancel(booking, [], overide_cancel_fees)
        booking_total = booking_total + sum(Decimal(i['amount']) for i in booking_cancellation_fees)
        basket = {}
        response = render(request, self.template_name, {'booking': booking,'basket': basket, 'booking_fees': booking_cancellation_fees, 'booking_total': booking_total, 'booking_total_positive': booking_total - booking_total - booking_total ,'is_staff': request.user.is_staff})
        response.delete_cookie(settings.OSCAR_BASKET_COOKIE_OPEN)
        return response

    def post(self, request, *args, **kwargs):
        context_processor = template_context(request)
        cancellation_reason = request.POST.get('cancellation_reason','')

        booking_id = kwargs['pk']
        booking_total = Decimal('0.00')
        booking = None
        overide_cancel_fees = False

        if request.user.is_staff or request.user.is_superuser or AdmissionsBooking.objects.filter(customer_id=request.user.id,pk=booking_id).count() == 1:
             booking = AdmissionsBooking.objects.get(pk=booking_id)
             if booking.booking_type == 4:
                  logger.info(f'Admissions Booking: [{booking.id}] has already been cancelled.')
                  return HttpResponseRedirect(reverse('home'))

        if request.user.is_authenticated:
            if request.user.groups().filter(name='Mooring Admin').exists():
                overide_cancel_fees = True
        
        booking_cancellation_fees = utils.calculate_price_admissions_cancel(booking, [], overide_cancel_fees)
        booking_total = booking_total + sum(Decimal(i['amount']) for i in booking_cancellation_fees)

        lines = []
        for cf in booking_cancellation_fees:
            lines.append({
                'ledger_description': cf['description'],
                "quantity": 1,
                "price_incl_tax": cf['amount'],
                "oracle_code": cf['oracle_code'],
                'line_status': 3
            })

        basket_params = {
            'products': lines,
            'vouchers': [],
            'system': settings.PS_PAYMENT_SYSTEM_ID,
            'custom_basket': True,
            'booking_reference': settings.DAILY_ADMISSION_REF_PREFIX + str(booking.id),
            'booking_reference_link': settings.DAILY_ADMISSION_REF_PREFIX + str(booking.id)
        }

        basket_params = utils.convert_decimal_to_float(basket_params)

        checkouthash = hashlib.sha256(str(booking.pk).encode('utf-8')).hexdigest()
        logger.info(f"checkouthash: [{checkouthash}] has been generated from the admissions booking.pk: [{booking.pk}].")

        return_url = request.build_absolute_uri()+"/admissions/cancellation-success/?checkouthash="+checkouthash
        return_preload_url = request.build_absolute_uri()+"/admissions/return-cancelled/"
        jsondata = process_api_refund(request, basket_params, booking.customer.id, return_url, return_preload_url)
        
        if jsondata['message'] == 'success':
            for ir in jsondata['data']['invoice_reference']:
                AdmissionsBookingInvoice.objects.get_or_create(admissions_booking=booking, invoice_reference=ir)
            
            booking.booking_type = 4
            booking.cancelation_time = datetime.now()
            booking.canceled_by = request.user
            booking.cancellation_reason = cancellation_reason
            booking.save()
            
            emails.send_refund_completed_email_customer_admissions(booking, context_processor)
            return HttpResponseRedirect(reverse('public_admission_booking_cancelled', args=(booking.id,)))
        else:
            emails.send_refund_failure_email_admissions(booking, context_processor)
            emails.send_refund_failure_email_customer_admissions(booking, context_processor)
            return HttpResponseRedirect(reverse('home'))

# class RefundPaymentView(TemplateView):
#     template_name = 'mooring/booking/refund_booking.html'

#     def get_booking_info(self, request, *args, **kwargs):
      
#         booking = Booking.objects.get(pk=request.session['ps_booking']) if 'ps_booking' in request.session else None
#         bpoint_id = None
#         form_context = {
#         }
#         form = MakeBookingsForm(form_context)

#         booking_invoice = BookingInvoice.objects.filter(booking=booking.old_booking)
#         for bi in booking_invoice:
#             inv = Invoice.objects.filter(reference=bi.invoice_reference)
#             for i in inv:
#                 for b in i.bpoint_transactions:
#                    if b.action == 'payment':
#                       bpoint_id = b.id

#         return booking,bpoint_id

#     def get(self, request, *args, **kwargs):

#         booking = Booking.objects.get(pk=request.session['ps_booking']) if 'ps_booking' in request.session else None
#         if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(customer=request.user,pk=booking.id).count() == 1:    
#             basket = utils.get_basket(request)
#             #basket_total = [sum(Decimal(b.line_price_incl_tax)) for b in basket.all_lines()] 
#             basket_total = Decimal('0.00')
#             for b in basket.all_lines():
#                basket_total = basket_total + b.line_price_incl_tax
#             booking,bpoint_id = self.get_booking_info(request, *args, **kwargs)

#             #    return self.render_page(request, booking, form)
#             return render(request, self.template_name, {'basket': basket})
#         else:
#             return HttpResponseRedirect(reverse('home'))

#     def post(self, request, *args, **kwargs):
#          context_processor = template_context(request)
#          booking = Booking.objects.get(pk=request.session['ps_booking']) if 'ps_booking' in request.session else None
#          if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(customer=request.user,pk=booking.id).count() == 1:

#              bpoint = None
#              invoice = None
#              refund  = None
#              failed_refund = False
#              basket = utils.get_basket(request)
#              booking,bpoint_id = self.get_booking_info(request, *args, **kwargs)
#              basket_total = Decimal('0.00')
#              for b in basket.all_lines():
#                  basket_total = basket_total + b.line_price_incl_tax

#              b_total =  Decimal('{:.2f}'.format(float(basket_total - basket_total - basket_total)))
#              info = {'amount': Decimal('{:.2f}'.format(float(basket_total - basket_total - basket_total))), 'details' : 'Refund via system'}
             
#              try:  
#                 bpoint = BpointTransaction.objects.get(id=bpoint_id)      
#                 refund = bpoint.refund(info,request.user)
#                 invoice = Invoice.objects.get(reference=bpoint.crn1)
#                 update_payments(invoice.reference)
#                 emails.send_refund_completed_email_customer(booking, context_processor)
#              except:
#                 failed_refund = True
#                 emails.send_refund_failure_email(booking, context_processor)
#                 emails.send_refund_failure_email_customer(booking, context_processor)
#                 booking_invoice = BookingInvoice.objects.filter(booking=booking.old_booking).order_by('id')
#                 for bi in booking_invoice:
#                     invoice = Invoice.objects.get(reference=bi.invoice_reference)
#                 RefundFailed.objects.create(booking=booking, invoice_reference=invoice.reference, refund_amount=b_total,status=0)
#              order_response = place_order_submission(request)
#              new_order = Order.objects.get(basket=basket)
#              new_invoice = Invoice.objects.get(order_number=new_order.number)
#              new_invoice.settlement_date = None
#              new_invoice.save()
              
# #             book_inv, created = BookingInvoice.objects.create(booking=booking, invoice_reference=invoice.reference)

#              BookingInvoice.objects.get_or_create(booking=booking, invoice_reference=new_invoice.reference)
#              if refund:
#                  invoice.voided = True
#                  invoice.save()
#                  bpoint_refund = BpointTransaction.objects.get(txn_number=refund.txn_number)
#                  bpoint_refund.crn1 = new_invoice.reference
#                  bpoint_refund.save()
#                  update_payments(invoice.reference)
#              update_payments(new_invoice.reference)


#              ## Send booking confirmation and invoice
#              #emails.send_booking_invoice(booking,request,context_processor)
#              #emails.send_booking_confirmation(booking,request, context_processor)


#              if failed_refund is True:
#                  # Refund Failed Assign Refund amount to allocation pool.
#                  lines = [{'ledger_description':'Refund assigned to unallocated pool',"quantity":1,"price_incl_tax":abs(info['amount']),"oracle_code":settings.UNALLOCATED_ORACLE_CODE, 'line_status': 1}]
#                  utils.allocate_failedrefund_to_unallocated(request, booking, lines, invoice_text=None, internal=False,order_total=abs(info['amount']),user=booking.customer)

#              return HttpResponseRedirect('/success/')
#          else:
#              return HttpResponseRedirect(reverse('home'))


# class ZeroBookingView(TemplateView):
#     template_name = 'mooring/booking/no_booking_payment.html'

#     def get_booking_info(self, request, *args, **kwargs):

#         booking = Booking.objects.get(pk=request.session['ps_booking']) if 'ps_booking' in request.session else None
#         form_context = {
#         }
#         form = MakeBookingsForm(form_context)

#         #booking_invoice = BookingInvoice.objects.filter(booking=booking.old_booking)
#         return booking

#     def get(self, request, *args, **kwargs):
#         booking = Booking.objects.get(pk=request.session['ps_booking']) if 'ps_booking' in request.session else None
#         if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(pk=booking.id).count() == 1:
#             basket = utils.get_basket(request)
#             #basket_total = [sum(Decimal(b.line_price_incl_tax)) for b in basket.all_lines()]
#             basket_total = Decimal('0.00')
#             for b in basket.all_lines():
#                basket_total = basket_total + b.line_price_incl_tax
#             booking = self.get_booking_info(request, *args, **kwargs)
#             #    return self.render_page(request, booking, form)
#             return render(request, self.template_name, {'basket': basket})
#         else:
#             return HttpResponseRedirect(reverse('home'))

#     def post(self, request, *args, **kwargs):
#          context_processor = template_context(request)
#          booking = Booking.objects.get(pk=request.session['ps_booking']) if 'ps_booking' in request.session else None
#          if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(pk=booking.id).count() == 1:

#              bpoint = None
#              invoice = None
#              basket = utils.get_basket(request)
#              booking = self.get_booking_info(request, *args, **kwargs)
#              basket_total = Decimal('0.00')
#              for b in basket.all_lines():
#                  basket_total = basket_total + b.line_price_incl_tax

#              b_total =  Decimal('{:.2f}'.format(float(basket_total - basket_total - basket_total)))
#              info = {'amount': Decimal('{:.2f}'.format(float(basket_total - basket_total - basket_total))), 'details' : 'Refund via system'}
#              booking_invoice = BookingInvoice.objects.filter(booking=booking.old_booking).order_by('id')
#              for bi in booking_invoice:
#                  invoice = Invoice.objects.get(reference=bi.invoice_reference)

#              order_response = place_order_submission(request)
#              new_order = Order.objects.get(basket=basket)
#              new_invoice = Invoice.objects.get(order_number=new_order.number)

#              # Send booking confirmation and invoice
#              #emails.send_booking_invoice(booking,request,context_processor)
#              #emails.send_booking_confirmation(booking,request, context_processor)

#              return HttpResponseRedirect('/success/')
#          else:
#              return HttpResponseRedirect(reverse('home'))


class MakeBookingsView(TemplateView):
    template_name = 'mooring/booking/make_booking.html'

    def render_page(self, request, booking, form, vehicles, show_errors=False):
        booking_mooring = None
        booking_total = '0.00'
        nowtime =  datetime.today()
        nowtimec = datetime.strptime(nowtime.strftime('%Y-%m-%d'),'%Y-%m-%d')
        occ = request.GET.get('occ', 'false')
        overide_change_fees = False

        #datetime.strptime(str(date_rotate_forward)+' '+str(bp.start_time), '%Y-%m-%d %H:%M:%S')
        today = date.today()
        # for now, we can assume that there's only one campsite per booking.
        # later on we might need to amend that
        expiry = booking.expiry_time.isoformat() if booking else ''
        timer = (booking.expiry_time-timezone.now()).seconds if booking else -1
        campsite = booking.campsites.all()[0].campsite if booking else None
        entry_fees = MarinaEntryRate.objects.filter(Q(period_start__lte = booking.arrival), Q(period_end__gt=booking.arrival)|Q(period_end__isnull=True)).order_by('-period_start').first() if (booking and campsite.mooringarea.park.entry_fee_required) else None

        payments_officer_group = False
        if request.user.is_authenticated:
            payments_officer_group = request.user.groups().filter(name='Payments Officers').exists()

        if occ == 'true':
            if payments_officer_group:
                overide_change_fees = True

        
        pricing = {
            'mooring': Decimal('0.00'),
            'adult': Decimal('0.00'),
            'concession': Decimal('0.00'),
            'child': Decimal('0.00'),
            'infant': Decimal('0.00'),
            'family': Decimal('0.00'),
            'adult_on': Decimal('0.00'),
            'child_on': Decimal('0.00'),
            'infant_on': Decimal('0.00'),
            'family_on': Decimal('0.00'),
            'vessel': entry_fees.vessel if entry_fees else Decimal('0.00'),
            'vehicle': entry_fees.vehicle if entry_fees else Decimal('0.00'),
            'vehicle_conc': entry_fees.concession if entry_fees else Decimal('0.00'),
            'motorcycle': entry_fees.motorbike if entry_fees else Decimal('0.00')
        }

        details = {
            'num_adults':0,
            'num_children':0,
            'num_infants':0,
            'vessel_size':0,
            'vessel_draft':0,
            'vessel_beam':0,
            'vessel_weight':0,
            'vessel_rego':"",
            'admission_fees': False,
        }

        lines = []

        if booking:
            booking_mooring = MooringsiteBooking.objects.filter(booking=booking)
            booking_total = sum(Decimal(i.amount) for i in booking_mooring)
            
            details = booking.details
            booking.details['admission_fees'] = False
            # for bm in booking_mooring:
            #     # Convert the from and to dates of this booking to just plain dates in local time.
            #     # Append them to a list.
            #     if bm.campsite.mooringarea.park.entry_fee_required:
            #         from_dt = bm.from_dt
            #         timestamp = calendar.timegm(from_dt.timetuple())
            #         local_dt = datetime.fromtimestamp(timestamp)
            #         from_dt = local_dt.replace(microsecond=from_dt.microsecond)
            #         to_dt = bm.to_dt
            #         timestamp = calendar.timegm(to_dt.timetuple())
            #         local_dt = datetime.fromtimestamp(timestamp)
            #         to_dt = local_dt.replace(microsecond=to_dt.microsecond)
            #         lines.append({'from': from_dt, 'to': to_dt})


        booking_change_fees = {}
        if booking:
            if booking.old_booking:
                booking_change_fees = utils.calculate_price_booking_change(booking.old_booking, booking, overide_change_fees)
                if booking.old_booking.admission_payment:
                    booking_change_fees = utils.calculate_price_admissions_change(booking.old_booking.admission_payment, booking_change_fees)
                booking_total = booking_total + sum(Decimal(i['amount']) for i in booking_change_fees)
            # Sort the list by date from.
            # new_lines = sorted(lines, key=lambda line: line['from'])
            # i = 0
            # lines = []
            # latest_from = None
            # latest_to = None
            # Loop through the list, if first instance, then this line's from date is the first admission fee.
            # Then compare this TO value to the next FROM value. If they are not the same or overlapping dates
            # add this date to the list, using the latest from and this TO value.
            # while i < len(new_lines):
            #     if i == 0:
            #         latest_from = new_lines[i]['from'].date()
            #     if i < len(new_lines)-1:
            #         if new_lines[i]['to'].date() < new_lines[i+1]['from'].date():
            #             latest_to = new_lines[i]['to'].date()
            #     else:
            #         # if new_lines[i]['from'].date() > new_lines[i-1]['to'].date():
            #         latest_to = new_lines[i]['to'].date()
                
            #     if latest_to:
            #         lines.append({'from':datetime.strftime(latest_from, '%d %b %Y'), 'to': datetime.strftime(latest_to, '%d %b %Y'), 'admissionFee': 0})
            #         if i < len(new_lines)-1:
            #             latest_from = new_lines[i+1]['from'].date()
            #             latest_to = None
            #     i+= 1
            no_admissions = False
            if details['vessel_rego']:
                vessel = RegisteredVessels.objects.filter(rego_no=details['vessel_rego'].upper())
                if settings.ML_ADMISSION_PAID_CHECK == True:
                   ml_vl = models.VesselLicence.objects.filter(status=1, start_date__lte=booking.arrival,expiry_date__gte=booking.arrival,vessel_rego__icontains=details['vessel_rego'])
                   if ml_vl.count() > 0:
                         no_admissions = True

                else:
                   if vessel.count() > 0:
                       vessel = vessel[0]
                       if vessel:
                           no_admissions = vessel.admissionsPaid
                   if no_admissions is False:
                       baa = BookingAnnualAdmission.objects.filter(booking_type=1,start_dt__lte=booking.arrival,expiry_dt__gte=booking.arrival,rego_no=details['vessel_rego'])
                       if baa.count() > 0:
                           no_admissions = True
 

            details['admission_fees'] = no_admissions
            if not no_admissions:
                lines_pre_check = utils.admissions_lines(booking_mooring)                
                # rate = AdmissionsRate.objects.filter(Q(period_start__lte=booking.arrival), (Q(period_end=None) | Q(period_end__gte=booking.arrival)))[0]
                for line in lines_pre_check:
                    if AdmissionsOracleCode.objects.filter(mooring_group__in=[line['group'],]).count() > 0:                        
                        if AdmissionsLocation.objects.filter(mooring_group__in=[line['group'],]).count() > 0:                            
                            rates = AdmissionsRate.objects.filter(Q(period_start__lte=booking.arrival), (Q(period_end=None) | Q(period_end__gte=booking.arrival)), Q(mooring_group=line['group']))
                            rate = None
                            if rates:
                                rate = rates[0]
                            if rate:
                                line['adult'] = str(rate.adult_cost)
                                line['child'] = str(rate.children_cost)
                                line['infant'] = str(rate.infant_cost)
                                line['family'] = str(rate.family_cost)
                                line['adult_on'] = str(rate.adult_overnight_cost)
                                line['child_on'] = str(rate.children_overnight_cost)
                                line['infant_on'] = str(rate.infant_overnight_cost)
                                line['family_on'] = str(rate.family_overnight_cost)
                                lines.append(line)
        
        staff = request.user.is_staff
        if(staff):
            staff = "true"
        else:
            staff = "false"

        #lines.append(booking_change_fees)
        return render(request, self.template_name, {
            'form': form, 
            'vehicles': vehicles,
            'booking': booking,
            'booking_mooring': booking_mooring,
            'booking_total' : booking_total,
            'campsite': campsite,
            'expiry': expiry,
            'timer': timer,
            'details': details,
            'pricing': pricing,
            'show_errors': show_errors,
            'lines': lines,
            'staff': staff,
            'booking_change_fees': booking_change_fees,
            'overide_change_fees' : overide_change_fees,
            'occ': occ,
            'payments_officer_group': payments_officer_group 
        })


    def get(self, request, *args, **kwargs):
        # TODO: find campsites related to campgroundi

        #occ = request.GET.get('occ', 'false')
        #overide_change_fees = False

        booking_uuid = kwargs.get('booking_uuid')
        booking = utils.get_booking_from_uuid_or_session(booking_uuid, request.session)

        # TEMP DEBUG (multi-tab concurrency control): trace cookie state on every GET/refresh.
        logger.info(
            'MakeBookingsView.get: booking_uuid=%s, active_booking_token=%s, cookie_valid=%s',
            booking_uuid, request.COOKIES.get(utils.ACTIVE_BOOKING_COOKIE_NAME),
            utils.validate_booking_cookie(request, booking) if booking else None
        )

        if booking is None or booking.expiry_time is None:
           messages.error(self.request, 'Sorry your booking has expired')
           return HttpResponseRedirect(reverse('map'))


        nowtime = datetime.strptime(str(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
        expiry_time = datetime.strptime(str(booking.expiry_time.strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
           
        if nowtime > expiry_time: 
           messages.error(self.request, 'Sorry your booking has expired')   
           return HttpResponseRedirect(reverse('map'))

        #payments_officer_group = request.user.groups().filter(name__in=['Payments Officers']).exists()
        #if occ == 'true':
        #    if payments_officer_group:
        #        overide_change_fees = True


         
 
        form_context = {
            'num_adult': booking.details.get('num_adult', 0) if booking else 0,
            'num_concession': booking.details.get('num_concession', 0) if booking else 0,
            'num_child': booking.details.get('num_child', 0) if booking else 0,
            'num_infant': booking.details.get('num_infant', 0) if booking else 0
        }

        if booking.old_booking is not None:
            form_context['first_name'] = booking.old_booking.details['first_name']
            form_context['last_name'] = booking.old_booking.details['last_name']
            form_context['phone'] = booking.old_booking.details['phone']
            form_context['postcode'] = booking.old_booking.details['postcode']
            form_context['country'] = booking.old_booking.details['country']
            form_context['email'] = booking.old_booking.customer.email
            form_context['confirm_email'] = booking.old_booking.customer.email
            #form_context['payments_officer_group'] = payments_officer_group
            #form_context['occ'] = occ
            #form_context['overide_change_fees'] = overide_change_fees
            form = MakeBookingsForm(form_context)
            #form.fields['email'].disabled = True
            form.fields['email'].widget.attrs['disabled'] = True
            form.fields['confirm_email'].widget.attrs['disabled'] = True
            form.fields['first_name'].widget.attrs['disabled'] = True
            form.fields['last_name'].widget.attrs['disabled'] = True
            form.fields['phone'].widget.attrs['disabled'] = True
            form.fields['postcode'].widget.attrs['disabled'] = True
            form.fields['country'].widget.attrs['disabled'] = True



#            form.fields['email'].widget.attrs['required'] = False
#            form.fields['confirm_email'].widget.attrs['required'] = False
#            form.fields['first_name'].widget.attrs['required'] = False
#            form.fields['last_name'].widget.attrs['disabled'] = False 
#            form.fields['phone'].widget.attrs['disabled'] = False
#            form.fields['postcode'].widget.attrs['disabled'] = False
#            form.fields['country'].widget.attrs['disabled'] = False

#            form.fields['email'].required = False
#            form.fields['confirm_email'].required = False
#            form.fields['first_name'].required = False
#            form.fields['last_name'].required = False
#            form.fields['phone'].required = False
#            form.fields['postcode'].required = False
#            form.fields['country'].required = False
        else:  
            if request.user.is_anonymous or request.user.is_staff:
                form = AnonymousMakeBookingsForm(form_context)
            else:
                form_context['first_name'] = request.user.first_name
                form_context['last_name'] = request.user.last_name
                if request.user.mobile_number:
                    if len(request.user.mobile_number) > 1:
                       form_context['phone'] = request.user.mobile_number
                    else:
                       form_context['phone'] = request.user.phone_number
                else:
                    form_context['phone'] = request.user.phone_number
                if  Address.objects.filter(user=request.user).count() > 0:
                    address = Address.objects.filter(user=request.user)[0]
                        
                    form_context['postcode'] = address.postcode
                    form_context['country'] = address.country
                form = MakeBookingsForm(form_context)

        vehicles = VehicleInfoFormset()
        response = self.render_page(request, booking, form, vehicles)
        # Re-activate this tab's booking as the valid one for checkout (multi-tab concurrency control)
        response = utils.set_active_booking_cookie(response, booking)
        # TEMP DEBUG (multi-tab concurrency control): confirm the cookie was overwritten for this tab.
        logger.info('MakeBookingsView.get: active_booking_token reset to booking_uuid=%s', booking_uuid)
        return response


    def post(self, request, *args, **kwargs):
        booking_uuid = kwargs.get('booking_uuid')
        booking = utils.get_booking_from_uuid_or_session(booking_uuid, request.session)
        if booking is None or booking.expiry_time is None:
           messages.error(self.request, 'Sorry your booking has expired')
           return HttpResponseRedirect(reverse('map'))

        nowtime = datetime.strptime(str(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
        expiry_time = datetime.strptime(str(booking.expiry_time.strftime('%Y-%m-%d %H:%M:%S')), '%Y-%m-%d %H:%M:%S')
        if nowtime > expiry_time:
           messages.error(self.request, 'Sorry your booking has expired')
           return HttpResponseRedirect(reverse('map'))

        mooring_booking = ""
        if booking:
            mooring_booking = MooringsiteBooking.objects.filter(booking=booking)
        if request.user.is_anonymous or request.user.is_staff:
            form = AnonymousMakeBookingsForm(request.POST)
        else:
            form = MakeBookingsForm(request.POST)

        if request.user.is_authenticated:
            form.fields['email'].required = False
            form.fields['confirm_email'].required = False
            form.fields['email'].widget.attrs['required'] = False
            form.fields['confirm_email'].widget.attrs['required'] = False
 

        if booking.old_booking is not None:
            form.fields['email'].required = False
            form.fields['confirm_email'].required = False
            form.fields['first_name'].required = False
            form.fields['last_name'].required = False
            form.fields['phone'].required = False
            form.fields['postcode'].required = False
            form.fields['country'].required = False

            form.fields['email'].widget.attrs['required'] = False
            form.fields['confirm_email'].widget.attrs['required'] = False
            form.fields['first_name'].widget.attrs['required'] = False
            form.fields['last_name'].widget.attrs['disabled'] = False
            form.fields['phone'].widget.attrs['disabled'] = False
            form.fields['postcode'].widget.attrs['disabled'] = False
            form.fields['country'].widget.attrs['disabled'] = False

        vehicles = VehicleInfoFormset(request.POST)   
        
        # re-render the page if there's no booking in the session
        if not booking:
            return self.render_page(request, booking, form, vehicles)
    
        # re-render the page if the form doesn't validate
        if (not form.is_valid()) or (not vehicles.is_valid()):
            return self.render_page(request, booking, form, vehicles, show_errors=True)

        # Abort checkout if another tab has since activated a different booking (multi-tab concurrency control)
        cookie_valid = utils.validate_booking_cookie(request, booking)
        # TEMP DEBUG (multi-tab concurrency control): trace cookie state on every POST/submit.
        logger.info(
            'MakeBookingsView.post: booking_uuid=%s, active_booking_token=%s, cookie_valid=%s',
            booking_uuid, request.COOKIES.get(utils.ACTIVE_BOOKING_COOKIE_NAME), cookie_valid
        )
        if not cookie_valid:
            messages.warning(self.request, 'A newer booking session was opened in another tab. Please continue in the active tab or refresh this page.')
            # Redirect (instead of re-rendering) so a browser refresh issues a fresh GET - which
            # re-activates this tab's cookie - rather than resubmitting this stale POST again.
            return HttpResponseRedirect(reverse('public_make_booking_uuid', args=(booking.uuid,)))

        # update the booking object with information from the form
        if not booking.details:
            booking.details = {}

        booking.details['num_adult'] = int(request.POST.get('num_adults')) if request.POST.get('num_adults') else 0
        booking.details['num_child'] = int(request.POST.get('num_children')) if request.POST.get('num_children') else 0
        booking.details['num_infant'] = int(request.POST.get('num_infants')) if request.POST.get('num_infants') else 0

        if booking.old_booking is None:
            booking.details['first_name'] = form.cleaned_data.get('first_name')
            booking.details['last_name'] = form.cleaned_data.get('last_name')
            booking.details['phone'] = form.cleaned_data.get('phone')
            booking.details['country'] = form.cleaned_data.get('country').iso_3166_1_a2
            booking.details['postcode'] = form.cleaned_data.get('postcode')
            # booking.details['num_adult'] = form.cleaned_data.get('num_adult')
            booking.details['num_concession'] = form.cleaned_data.get('num_concession')
            # booking.details['num_child'] = form.cleaned_data.get('num_child')
            # booking.details['num_infant'] = form.cleaned_data.get('num_infant')
            booking.details['num_adult'] = int(request.POST.get('num_adults')) if request.POST.get('num_adults') else 0
            booking.details['num_child'] = int(request.POST.get('num_children')) if request.POST.get('num_children') else 0
            booking.details['num_infant'] = int(request.POST.get('num_infants')) if request.POST.get('num_infants') else 0
            booking.details['non_online_booking'] = True if request.POST.get('nononline') else False

        overide_change_fees = False
        occ = request.POST.get('occ', 'false')
        overidden = True if request.POST.get('override') else False
        payments_officer_group = False
        if request.user.is_authenticated:
            payments_officer_group = request.user.groups().filter(name='Payments Officers').exists()
        if occ == 'true':
            if payments_officer_group:
                overide_change_fees = True

        admissionLineOverRideJson = {}
        if overidden:
            override_price = Decimal(request.POST.get('overridePrice')) if request.POST.get('overridePrice') else 0
            #if override_price > 0:
            booking.override_price = override_price
            booking.overridden_by = request.user
            override_reason = request.POST.get('overrideReason') if request.POST.get('overrideReason') else None
            if override_reason is not None:
                booking.override_reason = DiscountReason.objects.get(id=override_reason)
            booking.override_reason_info = request.POST.get('overrideDetail') if request.POST.get('overrideDetail') else ""
            #print request.POST.get('admissionsLines',{})
            bookingLinesOverRideJson = json.loads(request.POST.get('bookingLines',{}))
            #admissionLineOverRideJson = json.loads(request.POST.get('admissionsLines',{}))
            booking.override_lines = bookingLinesOverRideJson
            booking.save()
            #booking.
            #for bl in bookingLinesOverRideJson:
            #      print (bookingLinesOverRideJson[bl])
            #      mooring_booking_line = MooringsiteBooking.objects.get(id=bl)
            #      mooring_booking_line.amount = Decimal(bookingLinesOverRideJson[bl])
            #      mooring_booking_line.save() 
            #for post_list in request.POST:
            #      print (post_list)

        oracle_code = ''
        if booking.mooringarea.oracle_code:
            oracle_code = booking.mooringarea.oracle_code
        rego = request.POST.get('form-0-vehicle_rego') if request.POST.get('form-0-vehicle_rego') else None

        admissionsJson = json.loads(request.POST.get('admissionsLines')) if request.POST.get('admissionsLines') else []
        admissions = []

        admissionsTotal = 0

        for line in admissionsJson:
            group = line['group']
            codes = AdmissionsOracleCode.objects.filter(mooring_group__in=[group,])
            if codes.count() > 0:
                oracle_code_admissions = codes[0].oracle_code
                admissionFee = Decimal(line['admissionFee'])
                if overidden is True:
                      admissionFee = Decimal(line['override_price'])

                admissions.append({
                    'from': line['from'],
                    'to': line['to'],
                    'admissionFee': admissionFee,
                    'guests': booking.num_guests,
                    'oracle_code': oracle_code_admissions
                    })
                admissionsTotal += Decimal(line['admissionFee'])

        admissionsPaid = True
        admissionLines = utils.admission_lineitems(admissions)
        if RegisteredVessels.objects.filter(rego_no=rego).count() > 0:
            vessel = RegisteredVessels.objects.get(rego_no=rego)
            admissionsPaid = vessel.admissionsPaid
            if vessel.admissionsPaid:
                admissionLines = []
        if admissionsPaid is False:
            baa = BookingAnnualAdmission.objects.filter(booking_type=1,start_dt__lte=booking.arrival,expiry_dt__gte=booking.arrival,rego_no=booking.details['vessel_rego'])
            if baa.count() > 0:
                 admissionsPaid = True

        booking.details['admission_fees'] = admissionsPaid 
 

        # update vehicle registrations from form
        VEHICLE_CHOICES = {'0': 'vessel', '1': 'concession', '2': 'motorbike'}
        BookingVehicleRego.objects.filter(booking=booking).delete()
        for vehicle in vehicles:
            BookingVehicleRego.objects.create(
                    booking=booking, 
                    rego=vehicle.cleaned_data.get('vehicle_rego'), 
                    type=VEHICLE_CHOICES[vehicle.cleaned_data.get('vehicle_type')],
                    entry_fee=vehicle.cleaned_data.get('entry_fee')
            )

        # Check if number of people is exceeded in any of the campsites
        for c in booking.campsites.all():
            if booking.num_guests > c.campsite.max_people:
                form.add_error(None, 'Number of people exceeded for the current camp site.')
                return self.render_page(request, booking, form, vehicles, show_errors=True)
            # Prevent booking if less than min people 
#            if booking.num_guests < c.campsite.min_people:
#                form.add_error('Number of people is less than the minimum allowed for the current campsite.')
#                return self.render_page(request, booking, form, vehicles, show_errors=True)
        # generate final pricing
        
        #booking_change_fees = utils.calculate_price_booking_change(booking.old_booking, booking)

        lines = utils.price_or_lineitems(request, booking, booking.campsite_id_list)
        if booking.old_booking is not None:
           booking_change_fees = utils.calculate_price_booking_change(booking.old_booking, booking, overide_change_fees)
           if booking.old_booking.admission_payment:
               booking_change_fees = utils.calculate_price_admissions_change(booking.old_booking.admission_payment, booking_change_fees)
           lines = utils.price_or_lineitems_extras(request,booking,booking_change_fees,lines) 
        if 'non_online_booking' in booking.details:
            if booking.details['non_online_booking'] is True:
                groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
                if groups.count() == 1:
                    if GlobalSettings.objects.filter(key=17, mooring_group=groups[0]).count() == 0:
                        form.add_error(None, 'Non-Online Booking fee oracle code missing for {}.'.format(str(groups[0])))
                        return self.render_page(request, booking, form, vehicles, show_errors=True)
                   
                    oracle_code_non_online = GlobalSettings.objects.filter(key=17, mooring_group=groups[0])[0].value
                    if oracle_code_non_online:
                        booking_line = utils.nononline_booking_lineitems(oracle_code_non_online, request)
                        for line in booking_line:
                            lines.append(line)
                else:
                      form.add_error(None, 'ERROR: Not assigned a mooring group or you are part of more than one mooring group.  We can not determine which non online booking fee to calculate from when are you are linked to more than one group or zero mooring groups.')
                      return self.render_page(request, booking, form, vehicles, show_errors=True)

        from_earliest = None
        to_latest = None
        if mooring_booking:
            lines_required = False
            for bm in mooring_booking:
                if bm.campsite.mooringarea.park.entry_fee_required:
                    lines_required = True
                if from_earliest:
                    if bm.from_dt < from_earliest:
                        from_earliest = bm.from_dt
                else:
                    from_earliest = bm.from_dt
                if to_latest:
                    if bm.to_dt > to_latest:
                        to_latest = bm.to_dt
                else:
                    to_latest = bm.to_dt
            if lines_required:
                for line in admissionLines:
                    lines.append(line)
        booking.arrival = from_earliest
        booking.departure = to_latest
        try:
            pass
#           lines = utils.price_or_lineitems(request, booking, booking.campsite_id_list)
        except Exception as e:
            form.add_error(None, '{} Please contact mooring rentals with this error message and the time of the request.'.format(str(e)))
            return self.render_page(request, booking, form, vehicles, show_errors=True)
            
        #print(lines)
        total = sum([Decimal(p['price_incl_tax'])*p['quantity'] for p in lines])

        # if was discounted, include discount line and set total cost of booking.
        if overidden:
            if booking.override_price is None:
                    booking.override_price = Decimal('0.00')
            discount_line = utils.override_lineitems(booking.override_price, booking.override_reason, total, oracle_code, booking.override_reason_info)
            for line in discount_line:
                lines.append(line)
            #total = booking.override_price
        total = sum([Decimal(p['price_incl_tax'])*p['quantity'] for p in lines])

        # get the customer object
        if request.user.is_anonymous or request.user.is_staff:
            if booking.old_booking is None:     
                try:
                   customer = EmailUser.objects.get(email=form.cleaned_data.get('email').lower())
                except EmailUser.DoesNotExist:
                   customer = EmailUser.objects.create(
                        email=form.cleaned_data.get('email').lower(), 
                        first_name=form.cleaned_data.get('first_name'),
                        last_name=form.cleaned_data.get('last_name'),
                        phone_number=form.cleaned_data.get('phone'),
                        mobile_number=form.cleaned_data.get('phone')
                   )
                   Address.objects.create(line1='address', user=customer, postcode=form.cleaned_data.get('postcode'), country=form.cleaned_data.get('country').iso_3166_1_a2)
        else:
            customer = request.user
        
        if booking.old_booking is not None:
            customer = booking.old_booking.customer 

 
        # FIXME: get feedback on whether to overwrite personal info if the EmailUser
        # already exists
        al_json = {}
        if booking.details['num_adult'] > 0:
            adBooking = AdmissionsBooking.objects.create(customer_id=customer.id, booking_type=3, vesselRegNo=rego, noOfAdults=booking.details['num_adult'],
                noOfConcessions=0, noOfChildren=booking.details['num_child'], noOfInfants=booking.details['num_infants'], totalCost=admissionsTotal, created=datetime.now())
            
            for line in admissionsJson:
                loc = AdmissionsLocation.objects.filter(mooring_group=line['group'])[0]
                if line['from'] == line['to']:
                    overnight = False
                else:
                    overnight = True
                from_date = datetime.strptime(line['from'], '%d %b %Y').strftime('%Y-%m-%d')
                al = AdmissionsLine.objects.create(arrivalDate=from_date, admissionsBooking=adBooking, overnightStay=overnight, cost=line['admissionFee'], location=loc)
                if 'override_price' in line:
                    al_json[al.id] = line['override_price']
            booking.admission_payment = adBooking
            adBooking.override_lines = al_json 
            adBooking.save()
        # finalise the booking object
        if booking.customer is None:
            # Check if the provided 'customer' object is already saved in the database.
            # An object is considered unsaved if its primary key (pk) is None.
            if customer.pk is None:
                # The customer object is not yet saved.
                logger.info(f"Unsaved customer detected (Email: {customer.email}). Running ledger_api_client.utils.get_or_create to prevent ValueError.")
                resp_json = get_or_create(email=customer.email)
                logger.info(f"New customer has been created. resp_json: { resp_json }")
                customer = EmailUser.objects.get(email=customer.email)
                booking.customer = customer
            else:
                # The customer object is already a saved instance, so we can assign it directly.
                booking.customer = customer

        booking.cost_total = total
        if request.user.__class__.__name__ == 'EmailUser':
           booking.created_by =  request.user
        else:
           booking.created_by = None

        booking.save()


        timestamp = calendar.timegm(booking.arrival.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        from_dt = local_dt.replace(microsecond=booking.arrival.microsecond)
        from_date_converted = from_dt.date()
        timestamp = calendar.timegm(booking.departure.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        to_dt = local_dt.replace(microsecond=booking.departure.microsecond)
        to_date_converted = to_dt.date()
        # generate invoice
        reservation = u"Reservation for {} from {} to {} ".format(
               u'{} {}'.format(booking.customer.first_name, booking.customer.last_name),
                from_date_converted,
                to_date_converted,
                #booking.mooringarea.name
        )
        
        logger.info('{} built booking {} and handing over to payment gateway'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user',booking.id))

        # if request.user.is_staff:
        #     result = utils.checkout(request, booking, lines, invoice_text=reservation, internal=True)    
        # else:
        result = utils.checkout(request, booking, lines, invoice_text=reservation)
        
        # result =  HttpResponse(
        #     content=response.content,
        #     status=response.status_code,
        #     content_type=response.headers['Content-Type'],
        # )

        # if we're anonymous add the basket cookie to the current session
        # if request.user.is_anonymous() and settings.OSCAR_BASKET_COOKIE_OPEN in response.history[0].cookies:
        #    basket_cookie = response.history[0].cookies[settings.OSCAR_BASKET_COOKIE_OPEN]
        #    result.set_cookie(settings.OSCAR_BASKET_COOKIE_OPEN, basket_cookie)
        return result

class BookingPolicyView(TemplateView):
    template_name = 'mooring/dash/booking_policy.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        return super(BookingPolicyView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BookingPolicyView, self).get_context_data(**kwargs)
        request = self.request
        mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user,])
        if request.user.is_superuser:
            context['change_groups'] = ChangeGroup.objects.all()
            context['cancel_groups'] = CancelGroup.objects.all()
        else:
            context['change_groups'] = ChangeGroup.objects.filter(mooring_group__in=mooring_groups)
            context['cancel_groups'] = CancelGroup.objects.filter(mooring_group__in=mooring_groups)
        return context

class BookingPolicyChangeView(UpdateView):
    template_name = 'mooring/dash/view_change_policy.html'
    model = ChangeGroup

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_change(pk,request) == True:
            context_processor = template_context(self.request)
            app = self.get_object()
            return super(BookingPolicyChangeView, self).get(request, *args, **kwargs)
        else:
             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")


    def get_context_data(self, **kwargs):
        context = super(BookingPolicyChangeView, self).get_context_data(**kwargs)
        change_period_options = self.object.change_period.all()
        cpo = False
        for i in change_period_options:
            if i.days == 0:
               cpo = True
        context['cpo_check'] = cpo
        context['query_string'] = ''
        return context

    def get_form_class(self):
        return app_forms.ChangeGroupForm

class BookingPolicyCancelView(UpdateView):
    template_name = 'mooring/dash/view_cancel_policy.html'
    model = CancelGroup

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_cancel(pk,request) == True:
           context_processor = template_context(self.request)
           app = self.get_object()
           return super(BookingPolicyCancelView, self).get(request, *args, **kwargs)
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/forbidden")


    def get_context_data(self, **kwargs):
        context = super(BookingPolicyCancelView, self).get_context_data(**kwargs)
        cancel_period_options = self.object.cancel_period.all()
        cpo = False
        for i in cancel_period_options:
            if i.days == 0:
               cpo = True
        context['cpo_check'] = cpo

        context['query_string'] = ''
        return context

    def get_form_class(self):
        return app_forms.CancelGroupForm

class BookingPolicyAddCancelGroup(CreateView):
    template_name = 'mooring/dash/add_cancel_policy_group.html'
    model = CancelGroup

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        return super(BookingPolicyAddCancelGroup, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BookingPolicyAddCancelGroup, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_initial(self):
        initial = super(BookingPolicyAddCancelGroup, self).get_initial()
        request = self.request
        initial['action'] = 'new'
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.pk,i.name))
            #initial['mooring_group_choices'].append(i)
        return initial

    def get_form_class(self):
        return app_forms.UpdateCancelGroupForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPolicyAddCancelGroup, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        forms_data = form.cleaned_data
        return HttpResponseRedirect(reverse('dash-booking-policy-cancel-view', args=(self.object.pk,)))


class BookingPolicyEditCancelGroup(UpdateView):
    template_name = 'mooring/dash/add_cancel_policy_group.html'
    model = CancelGroup

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_cancel(pk,request) == True:
            context_processor = template_context(self.request)
            return super(BookingPolicyEditCancelGroup, self).get(request, *args, **kwargs)


        else:
             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPolicyEditCancelGroup, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_initial(self):
        initial = super(BookingPolicyEditCancelGroup, self).get_initial()
        request = self.request
        initial['action'] = 'edit'
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser is not True:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.id,i.name))

        return initial

    def get_form_class(self):
        return app_forms.UpdateCancelGroupForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPolicyEditCancelGroup, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        forms_data = form.cleaned_data
        return HttpResponseRedirect(reverse('dash-bookingpolicy'))


class BookingPolicyAddChangeGroup(CreateView):
    template_name = 'mooring/dash/add_change_policy_group.html'
    model = ChangeGroup

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        return super(BookingPolicyAddChangeGroup, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BookingPolicyAddChangeGroup, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_initial(self):
        initial = super(BookingPolicyAddChangeGroup, self).get_initial()
        request = self.request
        initial['action'] = 'new'
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
           mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.id,i.name))
        return initial

    def get_form_class(self):
        return app_forms.UpdateChangeGroupForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPolicyAddChangeGroup, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        forms_data = form.cleaned_data
        return HttpResponseRedirect(reverse('dash-booking-policy-change-view', args=(self.object.pk,)))

class BookingPolicyEditChangeGroup(UpdateView):
    template_name = 'mooring/dash/add_change_policy_group.html'
    model = ChangeGroup

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_change(pk,request) == True:
            context_processor = template_context(self.request)
            return super(BookingPolicyEditChangeGroup, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")


    def get_context_data(self, **kwargs):
        context = super(BookingPolicyEditChangeGroup, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_initial(self):
        initial = super(BookingPolicyEditChangeGroup, self).get_initial()
        initial['action'] = 'edit'
        request = self.request
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.id,i.name))
        return initial

    def get_form_class(self):
        return app_forms.UpdateChangeGroupForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPolicyEditChangeGroup, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        forms_data = form.cleaned_data
        return HttpResponseRedirect(reverse('dash-bookingpolicy'))

class BookingPolicyAddChangeOption(CreateView):
    template_name = 'mooring/dash/add_change_policy_option.html'
    model = ChangeGroup

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_change(pk,request) == True:
            context_processor = template_context(self.request)
            return super(BookingPolicyAddChangeOption, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPolicyAddChangeOption, self).get_context_data(**kwargs)
        context['query_string'] = ''
        context['change_group_id'] = self.kwargs['pk']
        return context

    def get_initial(self):
        initial = super(BookingPolicyAddChangeOption, self).get_initial()
        initial['action'] = 'new'
        request = self.request
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
           mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.id,i.name))

        return initial

    def get_form_class(self):
        return app_forms.UpdateChangeOptionForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPolicyAddChangeOption, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        pk = self.kwargs['pk']
        cg = ChangeGroup.objects.get(pk=pk)
#        cpp = ChangePricePeriod.objects.create(days=forms_data['days'],calulation_type=forms_data['calulation_type'], amount=forms_data['amount'], percentage=forms_data['percentage'])
        self.object.save()
        cg.change_period.add(self.object)
        cg.save()
        return HttpResponseRedirect(reverse('dash-booking-policy-change-view', args=(pk,)))

class BookingPolicyAddCancelOption(CreateView):
    template_name = 'mooring/dash/add_cancel_policy_option.html'
    model = CancelGroup

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_cancel(pk,request) == True:
            context_processor = template_context(self.request)
            return super(BookingPolicyAddCancelOption, self).get(request, *args, **kwargs)

        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPolicyAddCancelOption, self).get_context_data(**kwargs)
        context['query_string'] = ''
        context['cancel_group_id'] = self.kwargs['pk']
        return context

    def get_initial(self):
        initial = super(BookingPolicyAddCancelOption, self).get_initial()
        request = self.request
        initial['action'] = 'new' 
        return initial

    def get_form_class(self):
        return app_forms.UpdateCancelOptionForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPolicyAddCancelOption, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        pk = self.kwargs['pk']
        cg = CancelGroup.objects.get(pk=pk)
#        cpp = ChangePricePeriod.objects.create(days=forms_data['days'],calulation_type=forms_data['calulation_type'], amount=forms_data['amount'], percentage=forms_data['percentage'])
        self.object.save()
        cg.cancel_period.add(self.object)
        cg.save()
        return HttpResponseRedirect(reverse('dash-booking-policy-cancel-view', args=(pk,)))

class BookingPolicyEditChangeOption(UpdateView):
    template_name = 'mooring/dash/add_change_policy_option.html'
    model = ChangePricePeriod 

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        cg = self.kwargs['cg']

        if utils.mooring_group_access_level_change_options(cg,pk,request) == True:
            context_processor = template_context(self.request)
            return super(BookingPolicyEditChangeOption, self).get(request, *args, **kwargs)
        else:
             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPolicyEditChangeOption, self).get_context_data(**kwargs)
        context['query_string'] = ''
        context['change_group_id'] = self.kwargs['cg']
        return context

    def get_initial(self):
        initial = super(BookingPolicyEditChangeOption, self).get_initial()
        initial['action'] = 'edit'
        return initial

    def get_form_class(self):
        return app_forms.UpdateChangeOptionForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPolicyEditChangeOption, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        pk = self.kwargs['pk']
        cg = self.kwargs['cg']
        self.object.save()
        return HttpResponseRedirect(reverse('dash-booking-policy-change-view', args=(cg,)))

class BookingPolicyEditCancelOption(UpdateView):
    template_name = 'mooring/dash/add_cancel_policy_option.html'
    model = CancelPricePeriod

    def get(self, request, *args, **kwargs):

        pk = self.kwargs['pk']
        cg = self.kwargs['cg']

        if utils.mooring_group_access_level_cancel_options(cg,pk,request) == True:
             context_processor = template_context(self.request)
             return super(BookingPolicyEditCancelOption, self).get(request, *args, **kwargs)
        else:
             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPolicyEditCancelOption, self).get_context_data(**kwargs)
        context['query_string'] = ''
        context['cancel_group_id'] = self.kwargs['cg']
        return context

    def get_initial(self):
        initial = super(BookingPolicyEditCancelOption, self).get_initial()
        initial['action'] = 'edit'
        return initial

    def get_form_class(self):
        return app_forms.UpdateCancelOptionForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPolicyEditCancelOption, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        pk = self.kwargs['pk']
        cg = self.kwargs['cg']
        self.object.save()
        return HttpResponseRedirect(reverse('dash-booking-policy-cancel-view', args=(cg,)))


class ForbiddenView(TemplateView):

    template_name = 'mooring/forbidden.html'

    def get(self, request, *args, **kwargs):
        return super(ForbiddenView, self).get(request, *args, **kwargs)

class AnnualAdmissionsView(CreateView):
    template_name = 'mooring/dash/view_annual_admissions.html'
    model = BookingAnnualAdmission
   
    def get(self, request, *args, **kwargs):
        return super(AnnualAdmissionsView, self).get(request, *args, **kwargs)

    def get_form_class(self):
        return app_forms.AnnualAdmissionForm
    
    def get_context_data(self, **kwargs):
        context = super(AnnualAdmissionsView, self).get_context_data(**kwargs)
        request = self.request
        context['state'] = "WA"
        if self.request.POST.get('state'):
            context['state'] = self.request.POST.get('state')
        return context  

    def get_initial(self):
        initial = super(AnnualAdmissionsView, self).get_initial()
        initial['loc'] = self.kwargs['loc']
        
        al = AdmissionsLocation.objects.filter(key=self.kwargs['loc'])
        initial['termscondsurl'] = al[0].annual_admissions_terms
        initial['annual_admissions_more_price_info_url'] = al[0].annual_admissions_more_price_info_url
        initial['mooring_group'] = al[0].mooring_group
        initial['country'] = "AU"
        if self.request.POST.get('country'):
            initial['country'] = self.request.POST.get('country')
        
        initial['allow_override_fees'] = False
        initial['discount_reason'] = DiscountReason.objects.filter(mooring_group=al[0].mooring_group)
        payments_officer_group = False
        if self.request.user.is_authenticated:
            payments_officer_group = self.request.user.groups().filter(name='Payments Officers').exists()
        if payments_officer_group:
             initial['allow_override_fees'] = True
        initial['vessel_length'] = '0.00'
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('annual_admissions_view'))
        return super(AnnualAdmissionsView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        print ("SUBMITTED BOOKING")
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        payments_officer_group = False
        if self.request.user.is_authenticated:
            payments_officer_group = self.request.user.groups().filter(name='Payments Officers').exists()
        allow_override_fees=False
        if payments_officer_group:
             allow_override_fees = True


        customer = None
        if self.request.user.is_anonymous or self.request.user.is_staff:
            try:
               customer = EmailUser.objects.get(email=form.cleaned_data.get('email').lower())
            except EmailUser.DoesNotExist:
               customer = EmailUser.objects.create(
                    email=form.cleaned_data.get('email').lower(),
                    first_name=form.cleaned_data.get('first_name'),
                    last_name=form.cleaned_data.get('last_name'),
                    phone_number=form.cleaned_data.get('phone'),
                    mobile_number=form.cleaned_data.get('mobile')
               )
               Address.objects.create(line1='address', user=customer, postcode=form.cleaned_data.get('postcode'), country=form.cleaned_data.get('country').iso_3166_1_a2)
        else:
            customer = self.request.user


       
        lines = []
        booking_period = self.request.POST.get('booking_period')
        abg = AnnualBookingPeriodGroup.objects.get(id=int(booking_period))
        annual_admission = utils.get_annual_admissions_pricing_info(self.request.POST.get('booking_period'),self.request.POST.get('vessel_length'))
        details={}
        details['first_name'] = self.request.POST.get('first_name')
        details['last_name'] = self.request.POST.get('last_name')
        details['postal_address_line_1'] = self.request.POST.get('postal_address_line_1')
        details['postal_address_line_2'] = self.request.POST.get('postal_address_line_2')
        details['country'] = self.request.POST.get('country')       
        details['state'] = self.request.POST.get('state')
        details['post_code'] = self.request.POST.get('postcode')
        details['suburb'] = self.request.POST.get('suburb')
        details['phone'] = self.request.POST.get('phone')
        details['mobile'] = self.request.POST.get('mobile').replace(" ", "")
        details['email'] = self.request.POST.get('email')
        details['confirm_email'] = self.request.POST.get('confirm_email')
        details['vessel_rego'] = self.request.POST.get('vessel_rego').replace(" ","")
        details['vessel_name'] = self.request.POST.get('vessel_name')
        details['vessel_length'] = self.request.POST.get('vessel_length')
        details['terms'] = self.request.POST.get('terms')
        #print (annual_admission)
        total_cost = annual_admission['abpovc'].price
        oracle_code = annual_admission['abpovc'].oracle_code

        self.object.customer = customer
        self.object.start_dt = abg.start_time
        self.object.expiry_dt = abg.finish_time 
        self.object.booking_type = 3
        self.object.annual_booking_period_group = abg
        self.object.cost_total = total_cost
        self.object.rego_no = self.request.POST.get('vessel_rego').replace(" ","")
        self.object.details = details
        override_lines = None

        if allow_override_fees is True:
            if self.request.POST.get('override_price_selection', 'off') == 'on':
               pass
               dr = DiscountReason.objects.get(id=self.request.POST.get('override_reason'))
               self.object.override_price = self.request.POST.get('override_price')
               self.object.override_reason = dr
               self.object.override_reason_info = self.request.POST.get('override_details')
               self.object.overridden_by = self.request.user
               override_lines = {'ledger_description': '{} - {}'.format(dr.text, str(self.object.override_reason_info)), "quantity": 1, 'price_incl_tax': Decimal('0.00'), "oracle_code": oracle_code, 'line_status': 1}
               total_cost = self.object.override_price
        start_time = abg.start_time + timedelta(hours=8)
        finish_time = abg.finish_time + timedelta(hours=8)

        lines.append({'ledger_description': 'Annual Admission Fee for Vessel {}, {}m  ({} - {})'.format(details['vessel_rego'], details['vessel_length'],str(start_time.strftime('%d/%m/%Y')), str(finish_time.strftime('%d/%m/%Y'))), "quantity": 1, 'price_incl_tax': total_cost, "oracle_code": oracle_code, 'line_status': 1})
        if override_lines:
            lines.append(override_lines)
        if self.request.user.is_authenticated:
           self.object.created_by = self.request.user
        else:
           self.object.created_by = customer
        #self.object.completed_date = datetime.now()
        #self.object.completed_by = self.request.user
        #self.object.status = 1
        self.object.save()
        #lines = []
        #lines.append({'ledger_description': 'Annual Admissions {} - {}'.format(str(abg.start_time), str(abg.finish_time)), "quantity": 1, 'price_incl_tax': '20.00', "oracle_code": 'ORCALE CODE', 'line_status': 1})

        
        self.request.session['annual_admission_booking'] = self.object.id
        booking = self.object
        reservation = u"Annual Admission for {} from {} to {} ".format(
               u'{} {}'.format(booking.customer.first_name, booking.customer.last_name),
                str(start_time.strftime('%d/%m/%Y')),
                str(finish_time.strftime('%d/%m/%Y')),
        )

        logger.info('{} built annual admission booking {} and handing over to payment gateway'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user',booking.id))

        # if request.user.is_staff:
        #     result = utils.checkout(request, booking, lines, invoice_text=reservation, internal=True)
        # else:
        result = utils.annual_admission_checkout(self.request, booking, lines, invoice_text=reservation)
        return result
        #return HttpResponseRedirect("/map/")

class RefundFailedView(ListView):
    template_name = 'mooring/dash/view_failed_refunds.html'
    model = RefundFailed

    def get(self, request, *args, **kwargs):
#        pk = self.kwargs['pk']
        if is_payment_officer(request.user) == True:
            #context_processor = template_context(self.request)
#           app = self.get_object()
            return super(RefundFailedView, self).get(request, *args, **kwargs)
        else:
#             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(RefundFailedView, self).get_context_data(**kwargs)
        request = self.request
        context['status'] = 0
        context['keyword'] = ''

        if 'status' in self.request.GET:
            context['status'] = self.request.GET['status']
        if 'keyword' in self.request.GET:
            context['keyword'] = self.request.GET['keyword']

        if is_payment_officer(request.user) == True:
            if 'status' in self.request.GET:
                context['status'] = self.request.GET['status']
            if 'keyword' in self.request.GET:
                context['keyword'] = self.request.GET['keyword']
            if context['status'] == 'ALL':
                query = Q()
            else:
                query = Q(status=context['status'])
            if context['keyword'].isdigit():
                query &= Q(Q(invoice_reference__icontains=context['keyword']) | Q(booking_id=int(context['keyword'])))
            else:
                query &= Q(Q(invoice_reference__icontains=context['keyword']))
            failrefunds_list =[]
            failrefunds = RefundFailed.objects.filter(query)
            mg = MooringAreaGroup.objects.all() 
            

            for fr in failrefunds:
                mg_split = {}
                for i in mg:
                   mg_split[i.id] = {'amount': Decimal('0.00'), 'name': i.name, 'id': i.id}
                
                mooring_booking = MooringsiteBooking.objects.filter(booking=fr.booking)
                for mb in mooring_booking:
                    for i in mg:
                       if i.moorings.count() > 0:
                           if mb.campsite.mooringarea in i.moorings.all():
                               mg_split[i.id]['amount'] = mg_split[i.id]['amount'] + mb.amount
                #print (mooring_booking)
                mg_split_array = []
                for b in mg_split:
                    mg_split_array.append(mg_split[b])
                row = {'fr': fr, 'mgsplit': mg_split_array}
                failrefunds_list.append(row)
            context['failedrefunds'] = failrefunds_list
            #context['failedrefunds'] = RefundFailed.objects.filter(query)
        return context

    def get_initial(self):
        initial = super(RefundFailedView, self).get_initial()
        initial['action'] = 'list'
#        initial['status'] = 0
#        if 'status' in self.request.GET:
#            initial['status'] = self.request.GET['status']

        return initial

class RefundFailedCompletedView(ListView):
    template_name = 'mooring/dash/view_failed_refunds_completed.html'
    model = RefundFailed

    def get(self, request, *args, **kwargs):
#        pk = self.kwargs['pk']
        if is_payment_officer(request.user) == True:
            #context_processor = template_context(self.request)
#           app = self.get_object()
            return super(RefundFailedCompletedView, self).get(request, *args, **kwargs)
        else:
#             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(RefundFailedCompletedView, self).get_context_data(**kwargs)
        request = self.request
        if is_payment_officer(request.user) == True:
           context['status'] = 0
           if 'status' in self.request.GET:
              context['status'] = self.request.GET['status']

           context['failedrefunds'] = RefundFailed.objects.filter(status=1)
        return context

    def get_initial(self):
        initial = super(RefundFailedCompletedView, self).get_initial()
        initial['action'] = 'list'
        initial['status'] = 0 
        if 'status' in self.request.GET: 
            initial['status'] = self.request.GET['status']

        return initial

class RefundFailedCompleted(UpdateView):
    template_name = 'mooring/dash/complete_failed_refund.html'
    model = RefundFailed 

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        pk = self.kwargs['pk']
        if is_payment_officer(request.user) == True and self.object.status == 0:
            return super(RefundFailedCompleted, self).get(request, *args, **kwargs)
        else:
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(RefundFailedCompleted, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_form_class(self):
        return app_forms.FailedRefundCompletedForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('dash-failedrefunds'))
        return super(RefundFailedCompleted, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        self.object.completed_date = datetime.now() 
        self.object.completed_by = self.request.user
        self.object.status = 1
        self.object.save() 
        return HttpResponseRedirect(reverse('dash-failedrefunds'))


### Booking Period Views ###

class BookingPeriodGroupView(ListView):
    template_name = 'mooring/dash/view_booking_period_groups.html'
    model = BookingPeriod

    def get(self, request, *args, **kwargs):
#        pk = self.kwargs['pk']
        if utils.check_mooring_admin_access(request) == True:
            context_processor = template_context(self.request)
#            app = self.get_object()
            return super(BookingPeriodGroupView, self).get(request, *args, **kwargs)
        else:
             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPeriodGroupView, self).get_context_data(**kwargs)
        request = self.request
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        context['bp_groups'] = BookingPeriod.objects.filter(mooring_group__in=mg)
        return context

    def get_form_class(self):
        return app_forms.BookingPeriodForm

    def get_initial(self):
        initial = super(BookingPeriodGroupView, self).get_initial()
        initial['action'] = 'list'

        return initial


class AnnualBookingPeriodGroupView(ListView):
    template_name = 'mooring/dash/view_booking_annual_period_groups.html'
    model = AnnualBookingPeriodGroup 

    def get(self, request, *args, **kwargs):
#        pk = self.kwargs['pk']
        if utils.check_mooring_admin_access(request) == True:
            context_processor = template_context(self.request)
#            app = self.get_object()
            return super(AnnualBookingPeriodGroupView, self).get(request, *args, **kwargs)
        else:
             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(AnnualBookingPeriodGroupView, self).get_context_data(**kwargs)
        request = self.request
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        context['bp_groups'] = AnnualBookingPeriodGroup.objects.filter(mooring_group__in=mg)
        return context

    def get_form_class(self):
        return app_forms.BookingPeriodForm

    def get_initial(self):
        initial = super(AnnualBookingPeriodGroupView, self).get_initial()
        initial['action'] = 'list'
        return initial




class BookingPeriodAddChangeGroup(CreateView):
    template_name = 'mooring/dash/add_change_period_group.html'
    model = BookingPeriod

    def get(self, request, *args, **kwargs):
        #pk = self.kwargs['pk']
        #if utils.mooring_group_access_level_booking_period(pk,request) == True:
        #    context_processor = template_context(self.request)
        return super(BookingPeriodAddChangeGroup, self).get(request, *args, **kwargs)
        #else:
        #    messages.error(self.request, 'Forbidden from viewing this page.')
        #    return HttpResponseRedirect("/forbidden")


    def get_context_data(self, **kwargs):
        context = super(BookingPeriodAddChangeGroup, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_initial(self):
        initial = super(BookingPeriodAddChangeGroup, self).get_initial()
        initial['action'] = 'new'
        request = self.request
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.id,i.name))
        return initial

    def get_form_class(self):
        return app_forms.BookingPeriodForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPeriodAddChangeGroup, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        forms_data = form.cleaned_data
        return HttpResponseRedirect(reverse('dash-bookingperiod'))

class AnnualBookingPeriodAddChangeGroup(CreateView):
    template_name = 'mooring/dash/add_change_annual_period_group.html'
    model = AnnualBookingPeriodGroup 

    def get(self, request, *args, **kwargs):
        return super(AnnualBookingPeriodAddChangeGroup, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AnnualBookingPeriodAddChangeGroup, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_initial(self):
        initial = super(AnnualBookingPeriodAddChangeGroup, self).get_initial()
        initial['action'] = 'new'
        request = self.request
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.id,i.name))
        return initial

    def get_form_class(self):
        return app_forms.AnnualBookingPeriodForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(AnnualBookingPeriodAddChangeGroup, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        self.object.start_time = datetime.strptime(self.request.POST.get('start_time'), '%d/%m/%Y %H:%M')
        self.object.finish_time = datetime.strptime(self.request.POST.get('finish_time'), '%d/%m/%Y %H:%M')
        self.object.save()
        return HttpResponseRedirect(reverse('dash-annualbookingperiod'))

class BookingPeriodEditChangeGroup(UpdateView):
    template_name = 'mooring/dash/add_change_period_group.html'
    model = BookingPeriod 

    def get(self, request, *args, **kwargs):
        #print "--- BookingPeriodEditChangeGroup --- "
        #pk = self.kwargs['pk']
        #if utils.mooring_group_access_level_change(pk,request) == True:
        #    context_processor = template_context(self.request)
        return super(BookingPeriodEditChangeGroup, self).get(request, *args, **kwargs)
        #else:
        #    messages.error(self.request, 'Forbidden from viewing this page.')
        #    return HttpResponseRedirect("/forbidden")


    def get_context_data(self, **kwargs):
        context = super(BookingPeriodEditChangeGroup, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_initial(self):
        initial = super(BookingPeriodEditChangeGroup, self).get_initial()
        initial['action'] = 'edit'
        request = self.request
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.id,i.name))

        return initial

    def get_form_class(self):
        return app_forms.BookingPeriodForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPeriodEditChangeGroup, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        forms_data = form.cleaned_data
        return HttpResponseRedirect(reverse('dash-annualbookingperiod'))

class AnnualBookingPeriodEditChangeGroup(UpdateView):
    template_name = 'mooring/dash/add_change_annual_period_group.html'
    model = AnnualBookingPeriodGroup

    def get(self, request, *args, **kwargs):

        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_annual_booking_period(pk,request) == True:
            return super(AnnualBookingPeriodEditChangeGroup, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")


    def get_context_data(self, **kwargs):
        context = super(AnnualBookingPeriodEditChangeGroup, self).get_context_data(**kwargs)
        context['query_string'] = ''
        return context

    def get_initial(self):
        initial = super(AnnualBookingPeriodEditChangeGroup, self).get_initial()
        initial['action'] = 'edit'
        request = self.request
        initial['mooring_group_choices'] = []
        mg = []
        if request.user.is_superuser:
            mg = MooringAreaGroup.objects.all()
        else:
            mg = MooringAreaGroup.objects.filter(members__in=[request.user,])

        for i in mg:
            initial['mooring_group_choices'].append((i.id,i.name))

        pk = self.kwargs['pk']
        abp = AnnualBookingPeriodGroup.objects.get(id=pk)
        if abp.start_time is not None:
            initial['start_time'] = datetime.strftime(abp.start_time + timedelta(hours=8), '%d/%m/%Y %H:%M')
        if abp.finish_time is not None:
            initial['finish_time'] = datetime.strftime(abp.finish_time + timedelta(hours=8), '%d/%m/%Y %H:%M')
        return initial

    def get_form_class(self):
        return app_forms.AnnualBookingPeriodForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(AnnualBookingPeriodEditChangeGroup, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        self.object.start_time = datetime.strptime(self.request.POST.get('start_time'), '%d/%m/%Y %H:%M')
        self.object.finish_time = datetime.strptime(self.request.POST.get('finish_time'), '%d/%m/%Y %H:%M')
        self.object.save()
        return HttpResponseRedirect(reverse('dash-annualbookingperiod'))

class BookingPeriodView(UpdateView):
    template_name = 'mooring/dash/view_booking_periods.html'
    model = BookingPeriod 

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_booking_period(pk,request) == True:
            context_processor = template_context(self.request)
            app = self.get_object()
            return super(BookingPeriodView, self).get(request, *args, **kwargs)
        else:
             messages.error(self.request, 'Forbidden from viewing this page.')
             return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPeriodView, self).get_context_data(**kwargs)
        context['bp_group_id'] = self.kwargs['pk']
        return context

    def get_form_class(self):
        return app_forms.BookingPeriodForm

    def get_initial(self):
        initial = super(BookingPeriodView, self).get_initial()
        initial['action'] = 'list'
        return initial

class AnnualBookingPeriodView(UpdateView):
    template_name = 'mooring/dash/view_annual_booking_periods.html'
    model = AnnualBookingPeriodGroup 

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_booking_period(pk,request) == True:
            context_processor = template_context(self.request)
            app = self.get_object()
            return super(AnnualBookingPeriodView, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(AnnualBookingPeriodView, self).get_context_data(**kwargs)
        context['bp_group_id'] = self.kwargs['pk']
        context['annual_booking_periods'] = AnnualBookingPeriodOption.objects.filter(annual_booking_period_group=context['bp_group_id'])
        return context

    def get_form_class(self):
        return app_forms.BookingPeriodForm

    def get_initial(self):
        initial = super(AnnualBookingPeriodView, self).get_initial()
        initial['action'] = 'list'
        return initial

class BookingPeriodAddOption(CreateView):
    template_name = 'mooring/dash/add_change_period_option.html'
    model = BookingPeriodOption 

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['bp_group_id']
        if utils.mooring_group_access_level_booking_period(pk,request) == True:
            return super(BookingPeriodAddOption, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPeriodAddOption, self).get_context_data(**kwargs)
        #context['query_string'] = ''
        context['bp_group_id'] = self.kwargs['bp_group_id']
        return context

    def get_initial(self):
        initial = super(BookingPeriodAddOption, self).get_initial()
        initial['action'] = 'new'
        request = self.request
        initial['change_group_choices'] = []
        initial['cancel_group_choices'] = []
        change_group = []
        cancel_group = []
        mg = MooringAreaGroup.objects.filter(members__in=[request.user,])
        change_group = ChangeGroup.objects.filter(mooring_group__in=mg)
        cancel_group = CancelGroup.objects.filter(mooring_group__in=mg)

        for i in change_group:
            initial['change_group_choices'].append((i.id,i.name))
        for i in cancel_group:
            initial['cancel_group_choices'].append((i.id,i.name))
        return initial

    def get_form_class(self):
        return app_forms.BookingPeriodOptionForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPeriodAddOption, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data

        bp_group_id = self.kwargs['bp_group_id']
        bp = BookingPeriod.objects.get(pk=bp_group_id)
        self.object.save()
        bp.booking_period.add(self.object)
        bp.save()
        return HttpResponseRedirect(reverse('dash-bookingperiod-group-view', args=(self.kwargs['bp_group_id'],)))


class AnnualBookingPeriodAddOption(CreateView):
    template_name = 'mooring/dash/add_annual_change_period_option.html'
    model = AnnualBookingPeriodOption 

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['bp_group_id']
        if utils.mooring_group_access_level_annual_booking_period(pk,request) == True:
            return super(AnnualBookingPeriodAddOption, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(AnnualBookingPeriodAddOption, self).get_context_data(**kwargs)
        #context['query_string'] = ''
        context['bp_group_id'] = self.kwargs['bp_group_id']

        vsc_array = []
        vsc =VesselSizeCategory.objects.filter(status=1)
        for v in vsc:
            price = '0.00'
            oracle_code = ''
            vsc_array.append({'id': v.id, 'name' : v.name, 'start_size': v.start_size, 'end_size': v.end_size, 'price': price,'oracle_code': oracle_code})
        context['vessel_size_category'] = vsc_array


        return context

    def get_initial(self):
        initial = super(AnnualBookingPeriodAddOption, self).get_initial()
        initial['action'] = 'new'
        request = self.request
        return initial

    def get_form_class(self):
        return app_forms.AnnualBookingPeriodOptionForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(AnnualBookingPeriodAddOption, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        
        bp_group_id = self.kwargs['bp_group_id']
        bp = AnnualBookingPeriodGroup.objects.get(pk=bp_group_id)
        self.object.start_time = datetime.strptime(self.request.POST.get('start_time'), '%d/%m/%Y %H:%M')
        self.object.finish_time = datetime.strptime(self.request.POST.get('finish_time'), '%d/%m/%Y %H:%M')
        self.object.annual_booking_period_group = bp
        self.object.save()


        for pkeys in self.request.POST:
            if 'vessel_size_category' == pkeys[:20]:
                vcs_id = pkeys.replace("vessel_size_category_", "")
                vsc = VesselSizeCategory.objects.get(id=int(vcs_id))
                price = self.request.POST.get(pkeys)
                oracle_code = self.request.POST.get("vs_category_oracle_code_"+vcs_id)
                if AnnualBookingPeriodOptionVesselCategoryPrice.objects.filter(annual_booking_period_option=self.object,vessel_category=vsc).count() > 0:
                     abpocp = AnnualBookingPeriodOptionVesselCategoryPrice.objects.filter(annual_booking_period_option=self.object,vessel_category=vsc)[0]
                     abpocp.price = price
                     abpocp.oracle_code = oracle_code
                     abpocp.save()
                else:
                     AnnualBookingPeriodOptionVesselCategoryPrice.objects.create(annual_booking_period_option=self.object,vessel_category=vsc,price=price,oracle_code=oracle_code)

        return HttpResponseRedirect(reverse('dash-annual-bookingperiod-group-view', args=(self.kwargs['bp_group_id'],)))


class AnnualBookingPeriodDeleteOption(DeleteView):
    template_name = 'mooring/dash/delete_annual_period_option.html'
    model = AnnualBookingPeriodOption

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        bp_group_id = self.kwargs['bp_group_id']
        abpo = models.AnnualBookingPeriodOption.objects.get(id=int(pk))
        if utils.mooring_group_access_level_annual_booking_period(abpo.annual_booking_period_group.id,request) == True:
            return super(AnnualBookingPeriodDeleteOption, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(AnnualBookingPeriodDeleteOption, self).get_context_data(**kwargs)
        context['bp_group_id'] = self.kwargs['bp_group_id']
        return context
    def get_absolute_url(self):
        return reverse('dash-annual-bookingperiod-group-view', args=(self.kwargs['bp_group_id'],))

    def get_success_url(self):
        return reverse('dash-annual-bookingperiod-group-view', args=(self.kwargs['bp_group_id'],))


    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        pk = self.kwargs['pk']
        bp_group_id = self.kwargs['bp_group_id']

        try:
           self.delete(request, *args, **kwargs)
           messages.success(self.request, 'Annual Booking Period Option Successfully Removed')
        except Exception as e:
           messages.error(self.request, 'There was an error trying to deleting annual booking option.')
        return HttpResponseRedirect(self.get_absolute_url())


class AnnualBookingPeriodEditOption(UpdateView):
    template_name = 'mooring/dash/add_annual_change_period_option.html'
    model = AnnualBookingPeriodOption 

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        bp_group_id = self.kwargs['bp_group_id']
        abpo = models.AnnualBookingPeriodOption.objects.get(id=int(pk))
        if utils.mooring_group_access_level_annual_booking_period(abpo.annual_booking_period_group.id,request) == True:
            return super(AnnualBookingPeriodEditOption, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(AnnualBookingPeriodEditOption, self).get_context_data(**kwargs)
        #context['query_string'] = ''
        context['bp_group_id'] = self.kwargs['bp_group_id']

        vsc_array = []
        vsc =VesselSizeCategory.objects.filter(status=1)
        for v in vsc:
            price = '0.00'
            oracle_code = ''
            if AnnualBookingPeriodOptionVesselCategoryPrice.objects.filter(annual_booking_period_option=self.object,vessel_category=v).count() > 0:
                 a = AnnualBookingPeriodOptionVesselCategoryPrice.objects.filter(annual_booking_period_option=self.object,vessel_category=v)[0]
                 price = a.price
                 oracle_code = a.oracle_code
            vsc_array.append({'id': v.id, 'name' : v.name, 'start_size': v.start_size, 'end_size': v.end_size, 'price': price,'oracle_code': oracle_code})
        context['vessel_size_category'] = vsc_array


        return context

    def get_initial(self):
        initial = super(AnnualBookingPeriodEditOption, self).get_initial()
        initial['action'] = 'edit'
        pk = self.kwargs['pk']
        abp = AnnualBookingPeriodOption.objects.get(id=pk)
        request = self.request
        initial['start_time'] = datetime.strftime(abp.start_time + timedelta(hours=8), '%d/%m/%Y %H:%M')
        initial['finish_time'] = datetime.strftime(abp.finish_time + timedelta(hours=8), '%d/%m/%Y %H:%M')
        return initial

    def get_form_class(self):
        return app_forms.AnnualBookingPeriodOptionForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(AnnualBookingPeriodEditOption, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        bp_group_id = self.kwargs['bp_group_id']
        self.object.start_time = datetime.strptime(self.request.POST.get('start_time'), '%d/%m/%Y %H:%M')
        self.object.finish_time = datetime.strptime(self.request.POST.get('finish_time'), '%d/%m/%Y %H:%M')

        self.object.save()
        
        for pkeys in self.request.POST:
            if 'vessel_size_category' == pkeys[:20]:
                vcs_id = pkeys.replace("vessel_size_category_", "")
                vsc = VesselSizeCategory.objects.get(id=int(vcs_id))
                price = self.request.POST.get(pkeys)
                oracle_code = self.request.POST.get("vs_category_oracle_code_"+vcs_id)
                if AnnualBookingPeriodOptionVesselCategoryPrice.objects.filter(annual_booking_period_option=self.object,vessel_category=vsc).count() > 0:
                     abpocp = AnnualBookingPeriodOptionVesselCategoryPrice.objects.filter(annual_booking_period_option=self.object,vessel_category=vsc)[0]
                     abpocp.price = price
                     abpocp.oracle_code = oracle_code
                     abpocp.save()
                else:
                     AnnualBookingPeriodOptionVesselCategoryPrice.objects.create(annual_booking_period_option=self.object,vessel_category=vsc,price=price,oracle_code=oracle_code)
        

        return HttpResponseRedirect(reverse('dash-annual-bookingperiod-group-view', args=(bp_group_id,)))


class BookingPeriodEditOption(UpdateView):
    template_name = 'mooring/dash/add_change_period_option.html'
    model = BookingPeriodOption

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        bp_group_id = self.kwargs['bp_group_id']
        if utils.mooring_group_access_level_booking_period_option(pk,bp_group_id,request) == True:
            if MooringsiteBooking.objects.filter(booking_period_option_id=pk).count() > 0:
                messages.error(self.request, 'This booking period cannot be changed as it already associated with an existing booking.')
                return HttpResponseRedirect(reverse('dash-bookingperiod-group-view', args=(bp_group_id,)))

            return super(BookingPeriodEditOption, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPeriodEditOption, self).get_context_data(**kwargs)
        #context['query_string'] = ''
        context['bp_group_id'] = self.kwargs['bp_group_id']
        return context

    def get_initial(self):
        initial = super(BookingPeriodEditOption, self).get_initial()
        initial['action'] = 'edit'
        request = self.request

        initial['change_group_choices'] = []
        initial['cancel_group_choices'] = []
        change_group = []
        cancel_group = []
        mg = MooringAreaGroup.objects.filter(members__in=[request.user,])
        change_group = ChangeGroup.objects.filter(mooring_group__in=mg)
        cancel_group = CancelGroup.objects.filter(mooring_group__in=mg)

        for i in change_group:
            initial['change_group_choices'].append((i.id,i.name))
        for i in cancel_group:
            initial['cancel_group_choices'].append((i.id,i.name))
        return initial

    def get_form_class(self):
        return app_forms.BookingPeriodOptionForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        return super(BookingPeriodEditOption, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        bp_group_id = self.kwargs['bp_group_id']
        self.object.save()

        return HttpResponseRedirect(reverse('dash-bookingperiod-group-view', args=(bp_group_id,)))



class BookingPeriodDeleteGroup(DeleteView):
    template_name = 'mooring/dash/delete_period_group.html'
    model = BookingPeriod

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_booking_period(pk,request) == True:
            return super(BookingPeriodDeleteGroup, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPeriodDeleteGroup, self).get_context_data(**kwargs)
        return context

    def get_absolute_url(self):
        return reverse('dash-bookingperiod')

    def get_success_url(self):
        return reverse('dash-bookingperiod')

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        pk = self.kwargs['pk']
        try:
           self.delete(request, *args, **kwargs)
           messages.success(self.request, 'Booking Group Successfully Removed')
        except Exception as e:
           messages.error(self.request, 'There was an error trying to delete booking group ')
           return HttpResponseRedirect(reverse('dash-bookingperiod-group-delete', args=(pk,)))
        return HttpResponseRedirect(self.get_success_url())

class AnnualBookingPeriodDeleteGroup(DeleteView):
    template_name = 'mooring/dash/delete_annual_period_group.html'
    model = AnnualBookingPeriodGroup 

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if utils.mooring_group_access_level_annual_booking_period(pk,request) == True:
            print (models.BookingAnnualAdmission.objects.filter(annual_booking_period_group__id=int(pk)))
            if models.BookingAnnualAdmission.objects.filter(annual_booking_period_group__id=int(pk)).count() > 0:
                 messages.error(self.request,'Unable to delete groups that have annual admissions bookings linked.')
                 return HttpResponseRedirect(reverse('dash-annualbookingperiod'))

            
            return super(AnnualBookingPeriodDeleteGroup, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")


    def get_context_data(self, **kwargs):
        context = super(AnnualBookingPeriodDeleteGroup, self).get_context_data(**kwargs)
        return context

    def get_absolute_url(self):
        return reverse('dash-annualbookingperiod')

    def get_success_url(self):
        return reverse('dash-annualbookingperiod')

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        pk = self.kwargs['pk']
        try:
           self.delete(request, *args, **kwargs)
           messages.success(self.request, 'Annual Booking Group Successfully Removed')
        except Exception as e:
           messages.error(self.request, 'There was an error trying to delete annual booking group ')
           return HttpResponseRedirect(reverse('dash-annual-bookingperiod-group-delete', args=(pk,)))
        return HttpResponseRedirect(self.get_success_url())

class BookingPeriodDeleteOption(DeleteView):
    template_name = 'mooring/dash/delete_period_option.html'
    model = BookingPeriodOption

    def get(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        bp_group_id = self.kwargs['bp_group_id']
        if utils.mooring_group_access_level_booking_period_option(pk,bp_group_id,request) == True:
            return super(BookingPeriodDeleteOption, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Forbidden from viewing this page.')
            return HttpResponseRedirect("/forbidden")

    def get_context_data(self, **kwargs):
        context = super(BookingPeriodDeleteOption, self).get_context_data(**kwargs)
        context['bp_group_id'] = self.kwargs['bp_group_id']
        return context
    def get_absolute_url(self): 
        return reverse('dash-bookingperiod-group-view', args=(self.kwargs['bp_group_id'],))

    def get_success_url(self):
        return reverse('dash-bookingperiod-group-view', args=(self.kwargs['bp_group_id'],))


    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_absolute_url())
        pk = self.kwargs['pk']
        bp_group_id = self.kwargs['bp_group_id']

        if MooringsiteBooking.objects.filter(booking_period_option_id=pk).count() > 0:
           messages.error(self.request, 'This booking period cannot be deleted as it already associated with an existing booking.')
           return HttpResponseRedirect(reverse('dash-booking-period-option-delete', args=(bp_group_id,pk,)))

        try:
           self.delete(request, *args, **kwargs)
           messages.success(self.request, 'Booking Period Option Successfully Removed')
        except Exception as e:
           messages.error(self.request, 'There was an error trying to delete booking option.')
        return HttpResponseRedirect(self.get_absolute_url())
        #return HttpResponseRedirect(reverse('dash-booking-period-option-delete', args=(bp_group_id,pk,)))
        #return super(BookingPeriodDeleteOption, self).post(request, *args, **kwargs)

#    def form_valid(self, form):
#        self.object = form.save()
#        forms_data = form.cleaned_data
#        bp_group_id = self.kwargs['bp_group_id']
#        return HttpResponseRedirect(reverse('dash-bookingperiod-group-view', args=(bp_group_id,)))



### Booking Period Views ###

class AdmissionsBasketCreated(TemplateView):
    template_name = 'mooring/admissions/admissions_success.html'

    def get(request, *args, **kwargs):
        return HttpResponseRedirect(reverse('checkout:index'))

class AdmissionsBookingSuccessView(TemplateView):
    template_name = 'mooring/admissions/admission_success.html'

    def get(self, request, *args, **kwargs):
        try:
            booking = get_object_or_404(AdmissionsBooking, uuid=kwargs['booking_token'])

            invoice_ref = request.GET.get('invoice')

            # Ledger's return_url does not include ?invoice=, so fall back to the
            # AdmissionsBookingInvoice record already created by the notification endpoint.
            if not invoice_ref:
                bi = AdmissionsBookingInvoice.objects.filter(
                    admissions_booking=booking, system_invoice=False
                ).order_by('-id').first()
                if bi:
                    invoice_ref = bi.invoice_reference

            was_already_processed = (booking.booking_type == 1)
            context = booking.process_payment_notification(invoice_ref)

            # Inject keys required by admissions email/success templates
            context.update({
                'PUBLIC_URL': getattr(settings, 'PUBLIC_URL', request.build_absolute_uri('/')[:-1]),
                'SITE_URL': getattr(settings, 'SITE_URL', request.build_absolute_uri('/')[:-1]),
                'TEMPLATE_GROUP': 'ria',
                # Grant confirmation/invoice access to any user arriving via the correct UUID URL.
                # booking_view.html checks this alongside the usual user/session conditions.
                'arrived_via_payment': True,
            })

            # Only send emails if Path A (notification endpoint) has not already sent them.
            # process_payment_notification() is idempotent but send_payment_emails() is not.
            if not was_already_processed:
                try:
                    booking.send_payment_emails(context)
                except Exception as e:
                    logger.warning(f'Email sending failed in AdmissionsBookingSuccessView: {e}')

            response = render(request, self.template_name, context)
            # Admissions booking is confirmed, so both checkout cookies can be cleared (multi-tab concurrency control)
            utils.clear_admissions_cookie(response)
            response.delete_cookie(settings.OSCAR_BASKET_COOKIE_OPEN, path='/')
            return response

        except Exception as e:
            logger.error(f'Error in AdmissionsBookingSuccessView: {str(e)}', exc_info=True)
            return redirect('home')


class BookingCancelCompletedView(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/booking/cancel_completed.html'

    def get(self, request, *args, **kwargs):
        context = {}
        booking_id = kwargs['booking_id']
        booking = None
        refund_failed = None
        if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(customer=request.user,pk=booking_id).count() == 1:
             booking = Booking.objects.get(pk=booking_id)
             if RefundFailed.objects.filter(booking=booking).count() > 0:
                refund_failed = RefundFailed.objects.filter(booking=booking)

        context = {
           'booking_id': booking_id,
           'booking': booking,
           'refund_failed' : refund_failed
        }
        return render(request, self.template_name, context)

class AdmissionBookingCancelCompletedView(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/booking/admission_cancel_completed.html'

    def get(self, request, *args, **kwargs):
        context = {}
        booking_id = kwargs['booking_id']
        booking = None
        refund_failed = None
        if request.user.is_staff or request.user.is_superuser or AdmissionsBooking.objects.filter(customer_id=request.user.id,pk=booking_id).count() == 1:
             booking = AdmissionsBooking.objects.get(pk=booking_id)
             if RefundFailed.objects.filter(admission_booking=booking).count() > 0:
                refund_failed = RefundFailed.objects.filter(admission_booking=booking)

        context = {
           'booking_id': booking_id,
           'booking': booking,
           'refund_failed' : refund_failed
        }
        return render(request, self.template_name, context)

class AnnualAdmissionSuccessView(TemplateView):
    template_name = 'mooring/booking/annual-admission-success.html'

    def get(self, request, *args, **kwargs):
        print ("ANNUAL BOOKING SUCCESS ")
        try:
            print ("TRY SUSSE")
            context_processor = template_context(self.request)
            basket = None
            booking = utils.get_annual_admission_session_booking(request.session)
            if self.request.user.is_authenticated:
                basket = Basket.objects.filter(status='Submitted', owner=request.user).order_by('-id')[:1]
            else:
                basket = Basket.objects.filter(status='Submitted', owner=booking.customer).order_by('-id')[:1]

            context = utils.booking_annual_admission_success(basket, booking, context_processor)
            utils.delete_annual_admission_session_booking(request.session)
            request.session['annual_admission_last_booking'] = booking.id
            return render(request, self.template_name, context)
            #order = Order.objects.get(basket=basket[0])
            #invoice = Invoice.objects.get(order_number=order.number)
            #invoice_ref = invoice.reference
            #book_inv, created = BookingAnnualInvoice.objects.get_or_create(booking_annual_admission=booking, invoice_reference=invoice_ref)

            #

            ##invoice_ref = request.GET.get('invoice')
            #if booking.booking_type == 3:
            #    try:
            #        inv = Invoice.objects.get(reference=invoice_ref)
            #        order = Order.objects.get(number=inv.order_number)
            #        order.user = booking.customer
            #        order.save()
            #    except Invoice.DoesNotExist:
            #        print ("INVOICE ERROR")
            #        logger.error('{} tried making a booking with an incorrect invoice'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user'))
            #        return redirect('public_make_booking')
            #    if inv.system not in ['0516']:
            #        print ("SYSTEM ERROR")
            #        logger.error('{} tried making a booking with an invoice from another system with reference number {}'.format('User {} with id {}'.format(booking.customer.get_full_name(),booking.customer.id) if booking.customer else 'An anonymous user',inv.reference))
            #        return redirect('public_make_booking')

            #    if book_inv:
            #        # set booking to be permanent fixture
            #        booking.booking_type = 1  # internet booking
            #        booking.expiry_time = None
            #        update_payments(invoice_ref)
            #        #Calculate Admissions and create object
            #        booking.save()
            #        #if not request.user.is_staff:
            #        #    print "USER IS NOT STAFF."
            #        utils.delete_annual_admission_session_booking(request.session)
            #        # send out the invoice before the confirmation is sent if total is greater than zero
            #        #if booking.cost_total > 0:
            #        print ("SEND EMAIL")
            #        emails.send_annual_admission_booking_invoice(booking,request,context_processor)
            #        emails.send_new_annual_admission_booking_internal(booking,request,context_processor)
            #        # for fully paid bookings, fire off confirmation emaili
            #        #if booking.invoice_status == 'paid':
            #        request.session['annual_admission_last_booking'] = booking.id
            #        context = {
            #          'booking': booking,
            #          'book_inv': [book_inv],
            #        }

            #        try:

            #            if VesselDetail.objects.filter(rego_no=booking.details['vessel_rego']).count() > 0:
            #                    vd = VesselDetail.objects.filter(rego_no=booking.details['vessel_rego'])
            #                    p = vd[0]
            #                    p.vessel_name=booking.details['vessel_name']
            #                    p.save()
            #        except:
            #            print ("ERROR: create vesseldetails on booking success")


            #        print ("COMPLETED SUCCESS")
            #        return render(request, self.template_name, context)

        except Exception as e:
            print ("START EXCEPTION")
            print (str(e))
            print ("END EXCEPTION")
#            if 'ps_booking_internal' in request.COOKIES:
#                print "INTERNAL REDIRECT"
#                return redirect('dash-bookings')

            if ('annual_admission_last_booking' in request.session) and BookingAnnualAdmission.objects.filter(id=request.session['annual_admission_last_booking']).exists():
                booking = BookingAnnualAdmission.objects.get(id=request.session['annual_admission_last_booking'])
                if BookingAnnualInvoice.objects.filter(booking_annual_admission=booking).count() > 0:
                    bi = BookingAnnualInvoice.objects.filter(booking_annual_admission=booking)
                    book_inv = bi[0].invoice_reference
#                    book_inv = BookingInvoice.objects.get(booking=booking).invoice_reference
            else:
                print ("SUCCESS RETURN HOME")
                return redirect('home')

        #if request.user.is_staff:
        #    return redirect('dash-bookings')
        context = {
            'booking': booking,
            'book_inv': [book_inv],
            'context_processor' : context_processor
        }
        return render(request, self.template_name, context)


    
class BookingSuccessView(TemplateView):
    template_name = 'mooring/booking/success.html'

    def get(self, request, *args, **kwargs):
        try:
            booking = get_object_or_404(Booking, uuid=kwargs['booking_token'])

            invoice_ref = request.GET.get('invoice')

            # Ledger's return_url does not include ?invoice=, so fall back to the
            # BookingInvoice record that the notification endpoint already created.
            if not invoice_ref:
                bi = BookingInvoice.objects.filter(
                    booking=booking, system_invoice=False
                ).order_by('-id').first()
                if bi:
                    invoice_ref = bi.invoice_reference

            was_already_processed = (booking.booking_type == 1)
            context = booking.process_payment_notification(invoice_ref)

            # Grant confirmation/invoice access to any user arriving via the correct UUID URL.
            context['arrived_via_payment'] = True

            # Only send emails if Path A (notification endpoint) has not already sent them.
            # process_payment_notification() is idempotent but send_payment_emails() is not.
            if not was_already_processed:
                booking.send_payment_emails(context)

            response = render(request, self.template_name, context)
            # Booking is confirmed, so the active-booking cookie no longer needs to be tracked (multi-tab concurrency control)
            return utils.clear_booking_cookie(response)
        except Exception as e:
            logger.error('Error in BookingSuccessView: {}'.format(e))
            return redirect('home')


class MyBookingsView(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/booking/my_bookings.html'

    def get(self, request, *args, **kwargs):
        bookings = Booking.objects.filter(customer=request.user, booking_type__in=(0, 1), is_canceled=False)
        admissions = AdmissionsBooking.objects.filter(customer_id=request.user.id, booking_type__in=(0, 1))
        today = timezone.now().date()

        ad_currents = admissions.distinct().filter(admissionsline__arrivalDate__gte=today)
        ad_current = []
        for ad in ad_currents:
            adl = AdmissionsLine.objects.filter(admissionsBooking=ad)
            if adl.count() > 1:
                if Booking.objects.filter(admission_payment=ad).count() > 0:
                    conf = Booking.objects.filter(admission_payment=ad)[0].id
                    arrival = "See Booking PS" + str(conf)
                    overnight = "See Booking PS" + str(conf)
                else:
                    arrival = adl[0].arrivalDate
                    overnight = adl[0].overnightStay

            else :
                arrival = adl[0].arrivalDate
                overnight = adl[0].overnightStay
            invoice_reference = ''
            bk_invoices = []
            if AdmissionsBookingInvoice.objects.filter(admissions_booking=ad,system_invoice=False).count() > 0:
                 for i in AdmissionsBookingInvoice.objects.filter(admissions_booking=ad,system_invoice=False):
                      bk_invoices.append(i.invoice_reference)
 
            to_add = [ad, arrival, overnight, bk_invoices]
            ad_current.append(to_add)
        ad_pasts = admissions.distinct().filter(admissionsline__arrivalDate__lt=today)
        ad_past = []
        for ad in ad_pasts:
            bk_invoices = []
            for i in AdmissionsBookingInvoice.objects.filter(admissions_booking=ad, system_invoice=False):
                 bk_invoices.append(i.invoice_reference)
            to_add = [ad, bk_invoices]
            ad_past.append(to_add)

        bk_currents = bookings.filter(departure__gte=today).order_by('arrival')
        bk_current = []
        
        for bk in bk_currents:
            bk_invoices = []
            for i in BookingInvoice.objects.filter(booking=bk, system_invoice=False):
                bk_invoices.append(i.invoice_reference)    
            to_add = [bk, bk_invoices]
            bk_current.append(to_add)
        bk_pasts = bookings.filter(departure__lt=today).order_by('-arrival')
        bk_past = []
        for bk in bk_pasts:
            bk_invoices = []
            for i in BookingInvoice.objects.filter(booking=bk, system_invoice=False):
                bk_invoices.append(i.invoice_reference)
            to_add = [bk, bk_invoices]  
            bk_past.append(to_add)
        context = {
            'current_bookings': bk_current,
            'past_bookings': bk_past,
            'current_admissions': ad_current,
            'past_admissions': ad_past,
            # 'admissions_invoice': AdmissionsBookingInvoice.objects.filter(admissions_booking__in=admissions)
        }
        return render(request, self.template_name, context)

class ViewBookingView(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/booking/change_booking.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None
        booking_lines_collated = []
        if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(customer=request.user,pk=booking_id).count() == 1:
             booking = Booking.objects.get(pk=booking_id)
             if booking.in_future is True or request.user.is_staff or request.user.is_superuser:
                 booking_lines = MooringsiteBooking.objects.filter(booking=booking)

                 for ob in booking_lines:
                      from_dt = datetime.strptime(ob.from_dt.strftime('%Y-%m-%d'),'%Y-%m-%d')
                      cancel_fee_amount = '0.00'
                      description = 'Mooring {} ({} - {})'.format(ob.campsite.mooringarea.name,ob.from_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'),ob.to_dt.astimezone(pytimezone('Australia/Perth')).strftime('%d/%m/%Y %H:%M %p'))
                               #change_fees['amount'] = str(refund_amount)
                      booking_lines_collated.append({'description': description,'amount': ob.amount})
         
                 context = {
                    'booking_id': booking_id,
                    'booking': booking,
                    'booking_lines' : booking_lines_collated 
                 }
                 return render(request, self.template_name, context)
             else:
                 context = {}
                 self.template_name = 'mooring/booking-past.html'
                 return render(request, self.template_name, context)
        else:
             context = {}
             self.template_name = 'mooring/forbidden.html'
             return render(request, self.template_name, context)


class ViewBookingHistory(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/booking/booking_history.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None

        if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(customer=request.user,pk=booking_id).count() == 1:
#            booking = Booking.objects.get(customer=request.user, booking_type__in=(0, 1), is_canceled=False, pk=booking_id)
             booking = Booking.objects.get(pk=booking_id)
             newest_booking = self.get_newest_booking(booking_id)
             booking_history = self.get_history(newest_booking, booking_array=[])
             #print vars(booking_history['bookings'])

        context = {
           'booking_id': booking_id,
           'booking': booking,
           'booking_history' : booking_history,
           'GIT_COMMIT_DATE' : settings.GIT_COMMIT_DATE,
           'GIT_COMMIT_HASH' : settings.GIT_COMMIT_HASH,
        }

        return render(request, self.template_name,context)

    def get_newest_booking(self, booking_id):
        latest_id = booking_id
        if Booking.objects.filter(old_booking=booking_id).exclude(booking_type=3).count() > 0:
            booking = Booking.objects.filter(old_booking=booking_id)[0]   
            latest_id = self.get_newest_booking(booking.id)
        return latest_id

    def get_history(self, booking_id, booking_array=[]):
        booking = Booking.objects.get(pk=booking_id)
        # booking.invoices =()
        booking.invoices.set([])  # Direct assignment to the reverse side of a related set is prohibited. Use invoices.set() instead.
        #booking.invoices = BookingInvoice.objects.filter(booking=booking)
        booking_invoices= BookingInvoice.objects.filter(booking=booking) 
#        for bi in booking_invoices:
#            print bi
#            booking.invoices.add(bi)

        booking_array.append({'booking': booking, 'invoices': booking_invoices})
        if booking.old_booking:
             self.get_history(booking.old_booking.id, booking_array)
        return booking_array
          
class RefundBookingHistory(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/booking/booking_refund_history.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None
        print ("LOADED")
        if request.user.is_superuser or (request.user.is_authenticated and request.user.groups().filter(name='Payments Officers').exists()):
#            booking = Booking.objects.get(customer=request.user, booking_type__in=(0, 1), is_canceled=False, pk=booking_id)
             booking = Booking.objects.get(pk=booking_id)
             newest_booking = self.get_newest_booking(booking_id)
             booking_history = self.get_history(newest_booking, booking_array=[])
             invoice_line_items = self.get_history_line_items(booking_history)
             context = {
                'booking_id': booking_id,
                'booking': booking,
                'newest_booking': newest_booking,
                'booking_history' : booking_history,
                'invoice_line_items' : invoice_line_items,
                'oracle_code_refund_allocation_pool': settings.UNALLOCATED_ORACLE_CODE,
                'GIT_COMMIT_DATE' : settings.GIT_COMMIT_DATE,
                'GIT_COMMIT_HASH' : settings.GIT_COMMIT_HASH,
                'API_URL' : '/api/refund_oracle',
                'booking_class_type' : booking.__class__.__name__

             }
             return render(request, self.template_name,context)
        else:
             messages.error(self.request, 'Permission denied.')
             return HttpResponseRedirect(reverse('home')) 

    def get_newest_booking(self, booking_id):
        latest_id = booking_id
        if Booking.objects.filter(old_booking=booking_id).exclude(booking_type=3).count() > 0:
            booking = Booking.objects.filter(old_booking=booking_id)[0]
            latest_id = self.get_newest_booking(booking.id)
        return latest_id

    def get_history_line_items(self, booking_history):

        invoice_line_items = []
        invoice_line_items_array = []
        invoice_bpoint = []
        rolling_total = Decimal('0.00')
        bpoint_trans_totals = {}
        unique_oracle_code_on_booking = {}
        total_booking_allocation_pool = Decimal('0.00')
        total_bpoint_amount_available = Decimal('0.00')
        entry_count = 0
        for bi in booking_history:
            booking = Booking.objects.get(pk=bi['booking'].id)
            booking.invoices =()
            #booking.invoices = BookingInvoice.objects.filter(booking=booking)

            booking_invoices= BookingInvoice.objects.filter(booking=booking)
            for i in booking_invoices:
                 bp = BpointTransaction.objects.filter(crn1=i.invoice_reference)
                 for trans in bp:
                     if trans.action == 'payment':
                            if trans.txn_number not in bpoint_trans_totals:
                                   bpoint_trans_totals[trans.txn_number] = {'crn1': '', 'amount': Decimal('0.00')}
                             
                            total_bpoint_amount_available = total_bpoint_amount_available + trans.amount
                            bpoint_trans_totals[trans.txn_number]['amount'] = bpoint_trans_totals[trans.txn_number]['amount'] + trans.amount 
                            bpoint_trans_totals[trans.txn_number]['crn1'] = trans.crn1
                     if trans.action == 'refund':
                            if trans.original_txn not in bpoint_trans_totals:
                                   bpoint_trans_totals[trans.original_txn] = {'crn': '', 'amount': Decimal('0.00')}
                            bpoint_trans_totals[trans.original_txn]['amount'] = bpoint_trans_totals[trans.original_txn]['amount'] - trans.amount
                            total_bpoint_amount_available = total_bpoint_amount_available - trans.amount
                     invoice_bpoint.append(trans)

                 iv = Invoice.objects.filter(reference=i.invoice_reference)
                 for b in iv:
                    o = Order.objects.get(number=b.order_number)
                    for ol in o.lines.all():
                        if ol.oracle_code == settings.UNALLOCATED_ORACLE_CODE:
                             total_booking_allocation_pool = total_booking_allocation_pool + ol.line_price_incl_tax
                        #rolling_total = rolling_total + ol.line_price_incl_tax
                        entry_count = entry_count + 1
                        invoice_line_items_array.append({'line_id': ol.id, 'order_number': ol.order.number, 'title': ol.title, 'oracle_code': ol.oracle_code, 'line_price_incl_tax': ol.line_price_incl_tax, 'order_date_placed': ol.order.date_placed, 'rolling_total': '0.00' ,'entry_count': entry_count })
                        invoice_line_items.append(ol)

                        if ol.oracle_code == settings.UNALLOCATED_ORACLE_CODE:
                             pass
                        else:
                             if ol.oracle_code not in unique_oracle_code_on_booking:
                                 unique_oracle_code_on_booking[ol.oracle_code] = Decimal('0.00') 

                             unique_oracle_code_on_booking[ol.oracle_code] = unique_oracle_code_on_booking[ol.oracle_code] + Decimal(ol.line_price_incl_tax)
#                             unique_oracle_code_on_booking[ol.oracle_code] = float("%.2f".format(str(unique_oracle_code_on_booking[ol.oracle_code])))
#                            unique_oracle_code_on_booking.append(ol.oracle_code)
        for ocb in unique_oracle_code_on_booking:
                unique_oracle_code_on_booking[ocb] = str(unique_oracle_code_on_booking[ocb])

        for btt in bpoint_trans_totals:
             bpoint_trans_totals[btt]['amount'] = str(bpoint_trans_totals[btt]['amount'])
        #UNALLOCATED_ORACLE_CODE

        invoice_line_items_array.sort(key=lambda item:item['order_date_placed'], reverse=False)
       
        for il in invoice_line_items_array:
            rolling_total = Decimal(rolling_total) + Decimal(il['line_price_incl_tax'])
            il['rolling_total'] = rolling_total
        
        booking_balance_issue = False
        if rolling_total < 0:
            booking_balance_issue = True

        return {'invoice_line_items': invoice_line_items, 'invoice_line_items_array':  invoice_line_items_array, 'booking_balance_issue': booking_balance_issue,'total_booking_allocation_pool': total_booking_allocation_pool, 'invoice_bpoint': invoice_bpoint,'total_bpoint_amount_available': total_bpoint_amount_available, 'unique_oracle_code_on_booking': json.dumps(unique_oracle_code_on_booking),'bpoint_trans_totals': json.dumps(bpoint_trans_totals)}

    def get_history(self, booking_id, booking_array=[]):
        booking = Booking.objects.get(pk=booking_id)
        booking.invoices =()
        #booking.invoices = BookingInvoice.objects.filter(booking=booking)
        booking_invoices= BookingInvoice.objects.filter(booking=booking)
#        for bi in booking_invoices:
#            print bi
#            booking.invoices.add(bi)
#        invoice_line_items = []  
#        for i in booking_invoices:
#             print ("INVOICES")
#             print (i.invoice_reference)
#             iv = Invoice.objects.filter(reference=i.invoice_reference)
#             for b in iv:
#                o = Order.objects.get(number=b.order_number)
#                for ol in o.lines.all():
#                    print (ol.id)
#                    print (ol.title)
#                    print (ol.oracle_code)
#                    invoice_line_items.append(ol)
#        
#        
        booking_array.append({'booking': booking, 'invoices': booking_invoices})
 
        if booking.old_booking:
             self.get_history(booking.old_booking.id, booking_array)
        return booking_array





class RefundAnnualBookingHistory(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/booking/booking_refund_history.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None

        if request.user.is_superuser or (request.user.is_authenticated and request.user.groups().filter(name='Payments Officers').exists()):
#            booking = Booking.objects.get(customer=request.user, booking_type__in=(0, 1), is_canceled=False, pk=booking_id)
             newest_booking = models.BookingAnnualAdmission.objects.get(pk=booking_id)
             #newest_booking = self.get_newest_booking(booking_id)
             booking_history = self.get_history(newest_booking.id, booking_array=[])
             invoice_line_items = self.get_history_line_items(booking_history)

             context = {
                'booking_id': booking_id,
                'booking': booking,
                'newest_booking': newest_booking,
                'booking_history' : booking_history,
                'invoice_line_items' : invoice_line_items,
                'oracle_code_refund_allocation_pool': settings.UNALLOCATED_ORACLE_CODE,
                'GIT_COMMIT_DATE' : settings.GIT_COMMIT_DATE,
                'GIT_COMMIT_HASH' : settings.GIT_COMMIT_HASH,
                'API_URL' : '/api/annual_admissions_refund_oracle',
                'booking_class_type' : booking.__class__.__name__
             }

             return render(request, self.template_name,context)
        else:
             messages.error(self.request, 'Permission denied.')
             return HttpResponseRedirect(reverse('home'))

    #def get_newest_booking(self, booking_id):
    #    latest_id = booking_id
    #    #if BookingAnnualAdmission.objects.filter(old_booking=booking_id).exclude(booking_type=3).count() > 0:
    #    #    booking = BookingAnnualAdmission.objects.filter(old_booking=booking_id)[0]
    #    latest_id = self.get_newest_booking(booking.id)
    #    return latest_id

    def get_history_line_items(self, booking_history):

        invoice_line_items = []
        invoice_line_items_array = []
        invoice_bpoint = []
        rolling_total = Decimal('0.00')
        bpoint_trans_totals = {}
        unique_oracle_code_on_booking = {}
        total_booking_allocation_pool = Decimal('0.00')
        total_bpoint_amount_available = Decimal('0.00')
        entry_count = 0

        for bi in booking_history:
            booking = models.BookingAnnualAdmission.objects.get(pk=bi['booking'].id)
            booking.invoices =()
            #booking.invoices = BookingInvoice.objects.filter(booking=booking)

            booking_invoices= models.BookingAnnualInvoice.objects.filter(booking_annual_admission=booking)
            for i in booking_invoices:
                 bp = BpointTransaction.objects.filter(crn1=i.invoice_reference)
                 for trans in bp:
                     if trans.action == 'payment':
                            if trans.txn_number not in bpoint_trans_totals:
                                   bpoint_trans_totals[trans.txn_number] = {'crn1': '', 'amount': Decimal('0.00')}

                            total_bpoint_amount_available = total_bpoint_amount_available + trans.amount
                            bpoint_trans_totals[trans.txn_number]['amount'] = bpoint_trans_totals[trans.txn_number]['amount'] + trans.amount
                            bpoint_trans_totals[trans.txn_number]['crn1'] = trans.crn1
                     if trans.action == 'refund':
                            if trans.original_txn not in bpoint_trans_totals:
                                   bpoint_trans_totals[trans.original_txn] = {'crn': '', 'amount': Decimal('0.00')}
                            bpoint_trans_totals[trans.original_txn]['amount'] = bpoint_trans_totals[trans.original_txn]['amount'] - trans.amount
                            total_bpoint_amount_available = total_bpoint_amount_available - trans.amount
                     invoice_bpoint.append(trans)

                 iv = Invoice.objects.filter(reference=i.invoice_reference)
                 for b in iv:
                    o = Order.objects.get(number=b.order_number)
                    for ol in o.lines.all():
                        if ol.oracle_code == settings.UNALLOCATED_ORACLE_CODE:
                             total_booking_allocation_pool = total_booking_allocation_pool + ol.line_price_incl_tax
                        entry_count = entry_count + 1
                        invoice_line_items_array.append({'line_id': ol.id, 'order_number': ol.order.number, 'title': ol.title, 'oracle_code': ol.oracle_code, 'line_price_incl_tax': ol.line_price_incl_tax, 'order_date_placed': ol.order.date_placed, 'rolling_total': '0.00' ,'entry_count': entry_count })
                        invoice_line_items.append(ol)

                        if ol.oracle_code == settings.UNALLOCATED_ORACLE_CODE:
                             pass
                        else:
                             if ol.oracle_code not in unique_oracle_code_on_booking:
                                 unique_oracle_code_on_booking[ol.oracle_code] = Decimal('0.00')

                             unique_oracle_code_on_booking[ol.oracle_code] = unique_oracle_code_on_booking[ol.oracle_code] + Decimal(ol.line_price_incl_tax)

        for ocb in unique_oracle_code_on_booking:
                unique_oracle_code_on_booking[ocb] = str(unique_oracle_code_on_booking[ocb])

        for btt in bpoint_trans_totals:
             bpoint_trans_totals[btt]['amount'] = str(bpoint_trans_totals[btt]['amount'])

        for il in invoice_line_items_array:
            rolling_total = Decimal(rolling_total) + Decimal(il['line_price_incl_tax'])
            il['rolling_total'] = rolling_total

        booking_balance_issue = False
        if rolling_total < 0:
            booking_balance_issue = True

        #UNALLOCATED_ORACLE_CODE
        return {'invoice_line_items': invoice_line_items, 'invoice_line_items_array':  invoice_line_items_array, 'booking_balance_issue': booking_balance_issue, 'total_booking_allocation_pool': total_booking_allocation_pool, 'invoice_bpoint': invoice_bpoint,'total_bpoint_amount_available': total_bpoint_amount_available, 'unique_oracle_code_on_booking': json.dumps(unique_oracle_code_on_booking),'bpoint_trans_totals': json.dumps(bpoint_trans_totals)}

    def get_history(self, booking_id, booking_array=[]):
        booking = models.BookingAnnualAdmission.objects.get(pk=booking_id)
        booking.invoices =()
        booking_invoices= models.BookingAnnualInvoice.objects.filter(booking_annual_admission=booking)
        booking_array.append({'booking': booking, 'invoices': booking_invoices})

        #if booking.old_booking:
        #     self.get_history(booking.old_booking.id, booking_array)
        return booking_array


class ChangeBookingView(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/booking/change_booking.html'

    def get(self, request, *args, **kwargs):
        booking_id = kwargs['pk']
        booking = None
        if request.user.is_staff or request.user.is_superuser or Booking.objects.filter(customer=request.user,pk=booking_id).count() == 1:

#            booking = Booking.objects.get(customer=request.user, booking_type__in=(0, 1), is_canceled=False, pk=booking_id)
            booking = Booking.objects.get(pk=booking_id)
            if booking.in_future is True or request.user.is_staff or request.user.is_superuser:
                if booking.booking_type == 4:
                     print ("BOOKING HAS BEEN CANCELLED")
                     messages.error(self.request, 'Sorry this booking is not longer a current active booking.')
                     return HttpResponseRedirect(reverse('home'))
    
                if booking.booking_type == 1:
                    
                    booking_temp = Booking.objects.create(mooringarea=booking.mooringarea,
                                                          booking_type=3,
                                                          expiry_time=timezone.now()+timedelta(seconds=settings.BOOKING_TIMEOUT),
                                                          details=booking.details,
                                                          arrival=booking.arrival,
                                                          departure=booking.departure, 
                                                          old_booking=booking, 
                                                          customer=booking.customer)
              
                    booking_items = MooringsiteBooking.objects.filter(booking=booking)
                    for bi in booking_items:
                         cb =  MooringsiteBooking.objects.create(
                                campsite=bi.campsite,
                                booking_type=3,
                                date=bi.date,
                                from_dt=bi.from_dt,
                                to_dt=bi.to_dt,
                                booking=booking_temp,
                                amount=bi.amount,
                                booking_period_option=bi.booking_period_option
                              )
                         campsite_id= bi.campsite_id
                    change_booking_url_redirect = reverse('mooring_availaiblity2_selector')+'?site_id='+str(booking.mooringarea_id)+'&booking_uuid='+str(booking_temp.uuid)+'&arrival='+str(booking.arrival.strftime('%Y/%m/%d'))+'&departure='+str(booking.departure.strftime('%Y/%m/%d'))+'&vessel_size='+str(booking.details['vessel_size'])+'&vessel_draft='+str(booking.details['vessel_draft'])+'&vessel_beam='+str(booking.details['vessel_beam'])+'&vessel_weight='+str(booking.details['vessel_weight'])+'&vessel_rego='+str(booking.details['vessel_rego'])+'&num_adult='+str(booking.details['num_adults'])+'&num_children='+str(booking.details['num_children'])+'&num_infants='+str(booking.details['num_infants'])+'&distance_radius='+str(booking.mooringarea.park.distance_radius)

                    response = HttpResponse("<script> window.location='"+change_booking_url_redirect+"';</script> <a href='"+change_booking_url_redirect+"'> Redirecting please wait </a>")
                    response.delete_cookie(settings.OSCAR_BASKET_COOKIE_OPEN)
                    return response
                    #return HttpResponseRedirect(reverse('mooring_availaiblity2_selector')+'?site_id='+str(booking.mooringarea_id)+'&arrival='+str(booking.arrival.strftime('%Y/%m/%d'))+'&departure='+str(booking.departure.strftime('%Y/%m/%d'))+'&vessel_size='+str(booking.details['vessel_size'])+'&vessel_draft='+str(booking.details['vessel_draft'])+'&vessel_beam='+str(booking.details['vessel_beam'])+'&vessel_weight='+str(booking.details['vessel_weight'])+'&vessel_rego='+str(booking.details['vessel_rego'])+'&num_adult='+str(booking.details['num_adults'])+'&num_children='+str(booking.details['num_children'])+'&num_infants='+str(booking.details['num_infants'])+'&distance_radius='+str(booking.mooringarea.park.distance_radius)  )
                else:
                     print ("BOOKING NOT ACTIVE")
                     messages.error(self.request, 'Sorry this booking is not longer a current active booking.')
            else:
                 print ("BOOKING IN THE PAST")
                 messages.error(self.request, 'Sorry this booking is not longer a current active booking.')

        return HttpResponseRedirect(reverse('home'))


class AdmissionFeesView(TemplateView):
    template_name = 'mooring/admissions/admissions_form.html'

    def get(self, *args, **kwargs):
        context_processor = template_context(self.request)
        context = {
            'loc': self.kwargs['loc'],
            'context_processor': context_processor,
            'captcha_widget': CaptchaImages().render('captcha', None),
        }
        return render(self.request, self.template_name, context)


def refresh_captcha(request):
    return HttpResponse(CaptchaImages().render('captcha', None), content_type='text/html')


# class AdmissionsCostView(TemplateView):
#     template_name = 'mooring/admissions/admissions_cost.html'

#     def get(self, *args, **kwargs):
#         if self.request.user.is_authenticated:
#             if self.request.user.is_staff:
#                 mg_array = []
#                 mooring_groups = MooringAreaGroup.objects.filter(members__in=[self.request.user])
#                 for mg in mooring_groups: 
#                      mg_array.append({'id': mg.id, 'name' : mg.name})
#                 context = super().get_context_data(**kwargs)
#                 context['mooring_groups'] = json.dumps(mg_array)
#                 return render(self.request, self.template_name, context)
#             return redirect('ps_home')
#         return redirect('ps_home')


class AdmissionsCostView(UserPassesTestMixin, TemplateView):
    template_name = 'mooring/admissions/admissions_cost.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def get_context_data(self, **kwargs):
        print("--- 1. Inside get_context_data method. ---")

        context = super().get_context_data(**kwargs)

        print("--- 2. Context content AFTER super() call: ---")
        print(context)
        print(f"Is 'DEBUG' key in context? {'DEBUG' in context}")

        mg_array = []
        mooring_groups = MooringAreaGroup.objects.filter(members__in=[self.request.user])
        for mg in mooring_groups:
            mg_array.append({'id': mg.id, 'name': mg.name})
        
        context['mooring_groups'] = json.dumps(mg_array)

        return context
    

class MarinastayRoutingView(TemplateView):
    template_name = 'mooring/index.html'

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            if is_officer(self.request.user):
                return redirect('dash-campgrounds')
            return redirect('public_my_bookings')
        kwargs['form'] = LoginForm
        return super(MarinastayRoutingView, self).get(*args, **kwargs)

class InvoicePDFView(InvoiceOwnerMixin,View):
    def get(self, request, *args, **kwargs):
        invoice = get_object_or_404(Invoice, reference=self.kwargs['reference'])
        response = HttpResponse(content_type='application/pdf')
        mooring_var = mooring_url(request)
        api_key = settings.LEDGER_API_KEY
        url = settings.LEDGER_API_URL + '/ledgergw/invoice-pdf/' + api_key + '/' + invoice.reference
        invoice_pdf = requests.get(url=url)
        response.write(invoice_pdf.content)
        return response

    def get_object(self):
        invoice = get_object_or_404(Invoice, reference=self.kwargs['reference'])
        return invoice

class MapView(TemplateView):
    template_name = 'mooring/map.html'

    def get_context_data(self, **kwargs):
        """
        Add data from settings into the context for the template.
        """
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context['data_source_for_map_layers'] = settings.DATA_SOURCE_FOR_MAP_LAYERS

        return context

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/profile.html'


class MooringsiteRateLogView(LoginRequiredMixin, TemplateView):
    template_name = 'mooring/site_rate_log.html'

    def get(self, request, *args, **kwargs):
        mooring_id = kwargs['pk']
        
        rates = MooringsiteRateLog.objects.filter(mooringarea=mooring_id).order_by('-date_start')
        name = MooringArea.objects.get(pk=mooring_id).name

        context = {
            'rates': rates,
            'name': name,
            'mooring_id': mooring_id,
        }
        return render(request, self.template_name, context)

def getLetterFile(request,file_id,extension):
    allow_access = False
    mooring_groups = MooringAreaGroup.objects.filter(members__in=[request.user])
    abbg = AnnualBookingPeriodGroup.objects.get(id=file_id)
    if abbg.mooring_group in mooring_groups:
        allow_access = True

    #if request.user.is_superuser:
    if allow_access == True:
        file_record = AnnualBookingPeriodGroup.objects.get(id=file_id)
        file_name_path = file_record.letter.path
        if os.path.isfile(file_name_path) is True:
                the_file = open(file_name_path, 'rb')
                the_data = the_file.read()
                the_file.close()
                if extension == 'msg':
                    return HttpResponse(the_data, content_type="application/vnd.ms-outlook")
                if extension == 'eml':
                    return HttpResponse(the_data, content_type="application/vnd.ms-outlook")
                return HttpResponse(the_data, content_type=mimetypes.types_map['.'+str(extension)])
    else:
                return
