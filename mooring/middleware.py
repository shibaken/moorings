import re
import datetime
import logging
from django.contrib import messages

#from django.core.urlresolvers import reverse
from django.urls import reverse
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseRedirect
from django.utils import timezone
from mooring import settings
from mooring.models import AdmissionsBooking, Booking, BookingAnnualAdmission
import hashlib

from mooring.utils import (
    ACTIVE_ADMISSIONS_COOKIE_NAME,
    calculate_checkouthash_from_admissions_uuid,
    calculate_checkouthash_from_booking_id,
    delete_session_booking,
    validate_payment_checkouthash,
)


logger = logging.getLogger(__name__)

class CacheHeaders(object):
    # def process_response(self, request, response):
    #      if request.path[:5] == '/api/':
    #           response['Cache-Control'] = 'private, no-store'
    #      return response
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'private, no-store'
        return response


CHECKOUT_PATH = re.compile('^/ledger-api')
# CHECKOUT_PATH = re.compile('^/booking')
PROCESS_PAYMENT =  re.compile('^/ledger-api/process-payment')


class BookingTimerMiddleware(object):
    def __init__(self, get_response):            
            self.get_response = get_response

    def process_view(self, request, view_func, view_args, view_kwargs):
        logger.info("in BookingTimerMiddleware.process_view()...")
        if 'annual_admission_booking' in request.session:
            logger.info(f"session['annual_admission_booking']: [{request.session['annual_admission_booking']}] exists.")
            try:
                booking = BookingAnnualAdmission.objects.get(pk=request.session['annual_admission_booking'])
            except:
                # no idea what object is in self.request.session['annual_admission_booking'], ditch it
                del request.session['annual_admission_booking']
                return
            # Note: Don't delete session key based on booking_type here.
            # Views are responsible for session cleanup after successful completion.
            # booking_type changes from 3->1 during payment, but session key needed for success view.
            if CHECKOUT_PATH.match(request.path) and request.method == 'POST':
                # safeguard against e.g. part 1 of the multipart checkout confirmation process passing, then part 2 timing out.
                # on POST boosts remaining time to at least 2 minutes
                booking.save()
        else:
            logger.info(f'session[annual_admission_booking] does not exist.')

        if 'ps_booking' in request.session:
            logger.info(f"session['ps_booking']: [{request.session['ps_booking']}] exists.")

            # Only when user is going to make payment, compare the checkouthash stored in the cookie (sent from the page) with the checkouthash
            # dynamically calculated on the backend to prevent issues caused by users attempting to place orders
            # using multiple browser tabs.
            expected_hash = calculate_checkouthash_from_booking_id(int(request.session["ps_booking"]))
            checkouthash_cookie = request.COOKIES.get('checkouthash')
            logger.info(f'checkouthash dynamically calc: [{expected_hash}]')
            logger.info(f'checkouthash stored in cookie: [{checkouthash_cookie}]')

            is_payment_submission = request.method == 'POST' and request.path.startswith("/ledger-api/process-payment")
            if is_payment_submission:
                hash_ok = validate_payment_checkouthash(request, expected_hash)
            else:
                # For GET requests, bypass checkouthash validation. A stale cookie from a previous 
                # failed/cancelled checkout might be present causing a false positive mismatch. 
                # The client-side JS will overwrite it upon loading, and actual multi-tab protection 
                # is strictly enforced on the POST submission anyway.
                hash_ok = True

            if not hash_ok:
                # Checkouthash mismatch which implies the user is handling multiple browser tabs with different booking details,
                # redirect user to the booking page
                logger.warning(f"checkouthashs are mismatched!")

                if request.path.startswith("/ledger-api/process-payment") or request.path.startswith('/ledger-api/payment-details'):
                    # Redirect user to the booking page when attempting payment processing
                    # due to mismatch between backend booking data and frontend submitted data,
                    # likely caused by multiple browser tabs being open.
                    logger.warning(f"Redirecting user: [{request.user}] to the booking page due to mismatch of the booking data between the one stored in the backend and the one sent from the frontend.")
                    url_redirect = reverse('public_make_booking')
                    response = HttpResponse("<script> window.location='" + url_redirect + "';</script> <center><div class='container'><div class='alert alert-primary' role='alert'><a href='" + url_redirect + "'> Redirecting please wait: " + url_redirect + "</a><div></div></center>")
                    return response 

            try:
                booking = Booking.objects.get(pk=request.session['ps_booking'])
            except:
                # no idea what object is in self.request.session['ps_booking'], ditch it
                delete_session_booking(request.session)
                return

            # Note: Don't delete session key based on booking_type here.
            # Views are responsible for session cleanup after successful completion.
            # booking_type changes from 3->1 during payment, but session key needed for success view.
            if timezone.now() > booking.expiry_time:
                # expiry time has been hit, destroy the Booking then ditch it
                #booking.delete()
                delete_session_booking(request.session)
            elif CHECKOUT_PATH.match(request.path) and request.method == 'POST':
                # safeguard against e.g. part 1 of the multipart checkout confirmation process passing, then part 2 timing out.
                # on POST boosts remaining time to at least 2 minutes
                booking.expiry_time = max(booking.expiry_time, timezone.now()+datetime.timedelta(minutes=3))
                booking.save()
        else:
            logger.info('session[ps_booking] does not exist.')

            if request.path.startswith("/ledger-api/process-payment") or request.path.startswith('/ledger-api/payment-details'):
                admissions_token = request.COOKIES.get(ACTIVE_ADMISSIONS_COOKIE_NAME)
                if admissions_token:
                    expected_hash = calculate_checkouthash_from_admissions_uuid(admissions_token)
                    checkouthash_cookie = request.COOKIES.get('checkouthash')
                    record_exists = AdmissionsBooking.objects.filter(uuid=admissions_token, booking_type=3).exists()

                    is_payment_submission = request.method == 'POST' and request.path.startswith("/ledger-api/process-payment")
                    if is_payment_submission:
                        hash_ok = validate_payment_checkouthash(request, expected_hash)
                    else:
                        # For GET requests, bypass checkouthash validation. A stale cookie from a previous 
                        # failed/cancelled checkout might be present causing a false positive mismatch. 
                        # The client-side JS will overwrite it upon loading, and actual multi-tab protection 
                        # is strictly enforced on the POST submission anyway.
                        hash_ok = True

                    if not hash_ok or not record_exists:
                        logger.warning('Admissions checkouthash validation failed or booking no longer pending; redirecting user.')
                        url_redirect = reverse('home')
                        response = HttpResponse("<script> window.location='" + url_redirect + "';</script> <center><div class='container'><div class='alert alert-primary' role='alert'><a href='" + url_redirect + "'> Redirecting please wait: " + url_redirect + "</a><div></div></center>")
                        return response

        if CHECKOUT_PATH.match(request.path):
            try:
                booking = Booking.objects.get(pk=request.session['ps_booking'])
                if timezone.now() > booking.expiry_time:
                    try:
                        delete_session_booking(request.session)
                    except:
                        pass
                    return HttpResponseRedirect(reverse('public_make_booking'))
            except:
                pass

        # force a redirect if in the checkout
        # Note: 'payment_session' is set by create_basket_session/create_checkout_session in the
        # stateless payment flow (no ps_booking). Allow access to /ledger-api/* when it is present.
        if ('ps_booking_internal' not in request.COOKIES) and CHECKOUT_PATH.match(request.path):
            if ('ps_booking' not in request.session) and CHECKOUT_PATH.match(request.path) and ('annual_admission_booking' not in request.session) and ('payment_session' not in request.session):
                # return HttpResponseRedirect(reverse('public_make_booking'))
                url_redirect = reverse('public_make_booking')
                response = HttpResponse("<script> window.location='"+url_redirect+"';</script> <center><div class='container'><div class='alert alert-primary' role='alert'><a href='"+url_redirect+"'> Redirecting please wait: "+url_redirect+"</a><div></div></center>")
                return response
            else:
                return
        return

    def __call__(self, request):            
            # Run after executing any function code
            return self.pr(request)

    def pr(self, request):
        response= self.get_response(request)
        return response


class ForceDebugInContextMiddleware:
    """
    A middleware that forcefully injects the DEBUG value into the
    template context for every request. This is a workaround for
    when the 'debug' context processor fails to run.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # This part runs before the view is called
        response = self.get_response(request)
        # This part runs after the view is called
        return response

    def process_template_response(self, request, response):
        """
        This method is called only for responses that have a `render` method,
        which indicates they are TemplateResponse objects or similar.
        This is the perfect place to modify the template context.
        """
        if hasattr(response, 'context_data') and response.context_data is not None:
            # Add the DEBUG value to the response's context data
            response.context_data['DEBUG'] = settings.DEBUG
        return response