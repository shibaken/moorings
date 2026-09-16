from django.conf import settings
# from django.conf.urls import url, include
from django.urls import include, re_path
from django.conf.urls.static import static
from rest_framework import routers
from mooring import are_migrations_running, views, api
from mooring.payment_api import (
    BookingPaymentNotificationView,
    AdmissionsPaymentNotificationView,
)
from mooring.admin import admin
from django_crispy_jcaptcha import views as jcaptcha_views

# from ledger.urls import urlpatterns as ledger_patterns
from ledger_api_client.urls import urlpatterns as ledger_patterns
from mooring.default_data_manager import DefaultDataManager


# API patterns
router = routers.DefaultRouter()
if settings.SHOW_API_ROOT is not True:
    router.include_root_view = False  

#router.register(r'mooring_map', api.MooringAreaMapViewSet)
#router.register(r'current_booking', api.CurrentBookingViewSet)
router.register(r'mooring_map_filter', api.MooringAreaMapFilterViewSet, basename='mooring_map_filter')
router.register(r'marine_parks_map', api.MarineParksMapViewSet, basename='marine_parks_map')
router.register(r'region_marine_parks_map', api.MarineParksRegionMapViewSet)
#router.register(r'availability', api.AvailabilityViewSet, 'availability')
router.register(r'availability2', api.AvailabilityViewSet2, 'availability2')
router.register(r'availability_admin', api.AvailabilityAdminViewSet, basename='availability_admin')
router.register(r'availability_ratis', api.AvailabilityRatisViewSet, 'availability_ratis')
router.register(r'mooring-areas', api.MooringAreaViewSet, basename='mooringarea3')
router.register(r'mooringsites', api.MooringsiteViewSet)
router.register(r'mooringsite_bookings', api.MooringsiteBookingViewSet)
router.register(r'promo_areas', api.PromoAreaViewSet)
router.register(r'parks', api.MarinaViewSet)
router.register(r'admissions', api.AdmissionsRatesViewSet)
router.register(r'parkentryrate', api.MarinaEntryRateViewSet)
router.register(r'features', api.FeatureViewSet)
router.register(r'regions', api.RegionViewSet)
router.register(r'mooring_groups', api.MooringGroup)
router.register(r'districts', api.DistrictViewSet)
router.register(r'mooringsite_classes', api.MooringsiteClassViewSet)
router.register(r'booking',api.BookingViewSet)
router.register(r'admissionsbooking',api.AdmissionsBookingViewSet)
router.register(r'mooring_booking_ranges',api.MooringAreaBookingRangeViewset)
router.register(r'mooringsite_booking_ranges',api.MooringsiteBookingRangeViewset)
# router.register(r'mooringsite_rate',api.MooringsiteRateViewSet)
router.register(r'mooringsites_stay_history',api.MooringsiteStayHistoryViewSet)
router.register(r'mooring_stay_history',api.MooringAreaStayHistoryViewSet)
router.register(r'rates',api.RateViewset)
router.register(r'closureReasons',api.ClosureReasonViewSet)
router.register(r'openReasons',api.OpenReasonViewSet)
router.register(r'priceReasons',api.PriceReasonViewSet)
router.register(r'admissionsReasons',api.AdmissionsReasonViewSet)
router.register(r'maxStayReasons',api.MaximumStayReasonViewSet)
router.register(r'discountReasons', api.DiscountReasonViewSet)
#router.register(r'users',api.UsersViewSet)
router.register(r'contacts',api.ContactViewSet)
router.register(r'countries', api.CountryViewSet)
router.register(r'bookingPeriodOptions', api.BookingPeriodOptionsViewSet)
router.register(r'bookingPeriod', api.BookingPeriodViewSet)
#router.register(r'registeredVessels', api.RegisteredVesselsViewSet)

api_patterns = [
    re_path(r'^api/profile$',api.GetProfile.as_view(), name='get-profile'),
    re_path(r'^api/profile-admin$',api.GetProfileAdmin.as_view(), name='get-profile-admin'),
    re_path(r'^api/profile/update_personal$',api.UpdateProfilePersonal.as_view(), name='update-profile-personal'),
    re_path(r'^api/profile/update_contact$',api.UpdateProfileContact.as_view(), name='update-profile-contact'),
    re_path(r'^api/profile/update_address$',api.UpdateProfileAddress.as_view(), name='update-profile-address'),
    re_path(r'^api/oracle_job$',api.OracleJob.as_view(), name='get-oracle'),
    # re_path(r'^api/bulkPricing', api.BulkPricingView.as_view(),name='bulkpricing-api'),
    re_path(r'^api/registeredVessels/', api.get_paid_admissions,name='get_vessel_info'),
    re_path(r'^api/search_suggest', api.search_suggest, name='search_suggest'),
    re_path(r'^api/mooring_specification', api.mooring_specification, name='mooring_specification'),
    re_path(r'^api/get_country_provinces/(?P<country_code>[A-Z]+)/', api.get_provinces_by_country, name='get_country_provinces'),
    re_path(r'^api/get_annual_admission_pricing/(?P<annual_booking_period_id>[0-9]+)/(?P<vessel_size>[0-9]+.[0-9]+)/', api.get_annual_admission_pricing, name='get_annual_admission_pricing_float'),
    re_path(r'^api/get_annual_admission_pricing/(?P<annual_booking_period_id>[0-9]+)/(?P<vessel_size>[0-9]+)/', api.get_annual_admission_pricing, name='get_annual_admission_pricing'),
    re_path(r'^api/booking/annual-admissions/', api.get_annual_admission_booking, name='get_annual_admission_booking'),
    re_path(r'^api/booking/cancel-annual-admissions/', api.cancel_annual_admissions, name='cancel-annual-admissions'),
    re_path(r'^api/booking/update_sticker_admission_booking/', api.update_sticker_admission_booking, name='update_sticker_admission_booking'),
    re_path(r'^api/get_vessel_info/', api.get_vessel_info, name='get_vessel_info'),
    re_path(r'^api/create_booking', api.create_booking, name='create_booking'),
    re_path(r'^api/mooring_map/', api.mooring_map_view, name='mooring_map_api'),
    re_path(r'^api/create_admissions_booking', api.create_admissions_booking, name="create_admissions_booking"),
    # Payment notification endpoints (session-less, called by Ledger)
    re_path(r'^api/booking-payment-notification/(?P<booking_token>[0-9a-f-]{36})/$',
            BookingPaymentNotificationView.as_view(),
            name='api-booking-payment-notification'),
    re_path(r'^api/admissions-payment-notification/(?P<booking_token>[0-9a-f-]{36})/$',
            AdmissionsPaymentNotificationView.as_view(),
            name='api-admissions-payment-notification'),
    re_path(r'api/get_confirmation/(?P<booking_id>[0-9]+)/$', api.get_confirmation, name='get_confirmation'),
    re_path(r'api/get_confirmation/(?P<booking_token>[0-9a-f-]{36})/$', api.get_confirmation_by_uuid, name='get_confirmation_by_uuid'),
    re_path(r'^api/get_aa_letter/(?P<booking_id>[0-9]+)/$', api.get_annual_admission_letter, name='get_aa_letter'),
    re_path(r'api/get_admissions_confirmation/(?P<booking_id>[0-9]+)/$', api.get_admissions_confirmation, name='get_admissions_confirmation'),
    re_path(r'api/get_admissions_confirmation/(?P<booking_token>[0-9a-f-]{36})/$', api.get_admissions_confirmation_by_uuid, name='get_admissions_confirmation_by_uuid'),
    re_path(r'^api/reports/booking_refunds$', api.BookingRefundsReportView.as_view(),name='booking-refunds-report'),
    re_path(r'^api/reports/bookings$', api.BookingReportView.as_view(),name='bookings-report'),
    re_path(r'^api/reports/booking-mooring-created$', api.BookingCreatedReportView.as_view(),name='bookings-created-report'),
    re_path(r'^api/reports/booking-mooring-departure$', api.BookingDepartureReportView.as_view(),name='booking-mooring-departure'),
    re_path(r'^api/reports/booking-admission-created$', api.AdmissionBookingCreatedReportView.as_view(),name='booking-admission-created'),
    re_path(r'^api/reports/booking_settlements$', api.BookingSettlementReportView.as_view(),name='booking-settlements-report'),
    re_path(r'^api/booking/create$', api.add_booking,name='add_booking'),
    re_path(r'^api/booking/delete$', api.delete_booking,name='del_booking'),
    re_path(r'^api/current_booking$', api.current_booking,name='current_booking'),
    re_path(r'^api/global_settings$', api.GlobalSettingsView.as_view(), name='global_setting'),
    re_path(r'^api/check_oracle_code$', api.CheckOracleCodeView.as_view(), name='check_oracle_code'),
    re_path(r'^api/refund_oracle$', api.RefundOracleView.as_view(), name='refund_oracle'),
    re_path(r'^api/annual_admissions_refund_oracle$', api.AnnualAdmissionRefundOracleView.as_view(), name='annual_admissions_refund_oracle'),
    re_path(r'^api/ip-check/', api.ip_check),
    # External System API's - START
    re_path(r'^api/external/vessel-create-update/(?P<apikey>.+)/', api.vessel_create_update),
    re_path(r'^api/external/licence-create-update/(?P<apikey>.+)/', api.licence_create_update),
    re_path(r'^api/external/marine-parks/(?P<apikey>.+)/', api.marine_parks),
    re_path(r'^api/external/vessels-details/(?P<apikey>.+)/', api.vessels_details),
    re_path(r'^api/external/mooring-groups/(?P<apikey>.+)/', api.mooring_groups), 
    re_path(r'^api/external/all-mooring/(?P<apikey>.+)/', api.get_mooring),
    re_path(r'^api/external/bookings/(?P<apikey>.+)/', api.get_bookings),
   
    # External System API's - END
    #    url(r'^api/admissions_key$', api.AdmissionsKeyFromURLView.as_view(), name='admissions_key'),
    re_path(r'^api/',include(router.urls))
]
# URL Patterns
urlpatterns = [
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^jcaptcha/image-selection/(?P<hashkey>\w+).(?P<extension>\w\w\w)$', jcaptcha_views.getImagePrimary, name='jcaptcha-image-primary'),
    re_path(r'^jcaptcha/image-match/(?P<hashkey>\w+).(?P<extension>\w\w\w)$', jcaptcha_views.getImageHash, name='jcaptcha-image-match'),
    re_path(r'', include(api_patterns)),
    re_path(r'^forbidden', views.ForbiddenView.as_view(), name='forbidden-view'),
    re_path(r'^account/', views.ProfileView.as_view(), name='account'),
    # url(r'^$', views.MarinastayRoutingView.as_view(), name='ps_home'),
    re_path(r'^$', views.MarinastayRoutingView.as_view(), name='home'),
    re_path(r'^mooringsites/(?P<ground_id>[0-9]+)/$', views.MooringsiteBookingSelector.as_view(), name='campsite_booking_selector'),
    re_path(r'^availability/$', views.MooringsiteAvailabilitySelector.as_view(), name='campsite_availaiblity_selector'),
    re_path(r'^availability2/$', views.MooringAvailability2Selector.as_view(), name='mooring_availaiblity2_selector'),
    re_path(r'^availability_admin/$', views.AvailabilityAdmin.as_view(), name='availability_admin'),
    #url(r'^ical/campground/(?P<ground_id>[0-9]+)/$', views.MooringAreaFeed(), name='campground_calendar'),
    re_path(r'^dashboard/moorings/$', views.DashboardView.as_view(), name='dash-campgrounds'),
    # re_path(r'^dashboard/mooringsite-types$', views.DashboardView.as_view(), name='dash-campsite-types'),
    re_path(r'^dashboard/bookings/annual-admissions/$', views.DashboardAnnualAdmissionView.as_view(), name='annual-admissions-dash-bookings'),
    re_path(r'^dashboard/bookings/edit/', views.DashboardView.as_view(), name='dash-bookings'),
    re_path(r'^dashboard/bookings$', views.DashboardView.as_view(), name='dash-bookings'),
    # re_path(r'^dashboard/bulkpricing$', views.DashboardView.as_view(), name='dash-bulkpricing'),
    re_path(r'^dashboard/booking-policy-change/(?P<pk>[0-9]+)/edit', views.BookingPolicyEditChangeGroup.as_view(), name='dash-booking-policy-change-edit'),
    re_path(r'^dashboard/booking-policy-change/(?P<pk>[0-9]+)', views.BookingPolicyChangeView.as_view(), name='dash-booking-policy-change-view'),
    re_path(r'^dashboard/booking-policy-cancel/(?P<pk>[0-9]+)/edit', views.BookingPolicyEditCancelGroup.as_view(), name='dash-booking-policy-cancel-edit'),
    re_path(r'^dashboard/booking-policy-cancel/(?P<pk>[0-9]+)', views.BookingPolicyCancelView.as_view(), name='dash-booking-policy-cancel-view'),
    re_path(r'^dashboard/booking-policy-change-option/(?P<cg>[0-9]+)/edit/(?P<pk>[0-9]+)', views.BookingPolicyEditChangeOption.as_view(), name='dash-booking-policy-change-option-edit'),
    re_path(r'^dashboard/booking-policy-cancel-option/(?P<cg>[0-9]+)/edit/(?P<pk>[0-9]+)', views.BookingPolicyEditCancelOption.as_view(), name='dash-booking-policy-cancel-option-edit'),
    re_path(r'^dashboard/booking-policy-change-option/(?P<pk>[0-9]+)', views.BookingPolicyAddChangeOption.as_view(), name='dash-booking-policy-change-option-view'),
    re_path(r'^dashboard/booking-policy-cancel-option/(?P<pk>[0-9]+)', views.BookingPolicyAddCancelOption.as_view(), name='dash-booking-policy-cancel-option-view'),
    re_path(r'^dashboard/booking-policy/create-change', views.BookingPolicyAddChangeGroup.as_view(), name='dash-booking-policy-create-change'),
    re_path(r'^dashboard/booking-policy/create-cancel', views.BookingPolicyAddCancelGroup.as_view(), name='dash-booking-policy-create-cancel'),
    re_path(r'^dashboard/booking-policy', views.BookingPolicyView.as_view(), name='dash-bookingpolicy'),
    re_path(r'^dashboard/booking-periods-option/(?P<bp_group_id>[0-9]+)/create', views.BookingPeriodAddOption.as_view(), name='dash-booking-period-option-add'),
    re_path(r'^dashboard/booking-periods-option/(?P<bp_group_id>[0-9]+)/edit/(?P<pk>[0-9]+)', views.BookingPeriodEditOption.as_view(), name='dash-booking-period-option-edit'),
    re_path(r'^dashboard/booking-periods-option/(?P<bp_group_id>[0-9]+)/delete/(?P<pk>[0-9]+)', views.BookingPeriodDeleteOption.as_view(), name='dash-booking-period-option-delete'),
    re_path(r'^dashboard/bookingperiods/create', views.BookingPeriodAddChangeGroup.as_view(), name='dash-bookingperiod-group-add'),
    re_path(r'^dashboard/bookingperiods/(?P<pk>[0-9]+)/edit', views.BookingPeriodEditChangeGroup.as_view(), name='dash-bookingperiod-group-edit'),
    re_path(r'^dashboard/bookingperiods/(?P<pk>[0-9]+)/delete', views.BookingPeriodDeleteGroup.as_view(), name='dash-bookingperiod-group-delete'),
    re_path(r'^dashboard/bookingperiods/(?P<pk>[0-9]+)/view', views.BookingPeriodView.as_view(), name='dash-bookingperiod-group-view'),
    re_path(r'^dashboard/bookingperiods', views.BookingPeriodGroupView.as_view(), name='dash-bookingperiod'),
    re_path(r'^dashboard/annual-bookingperiods-option/(?P<bp_group_id>[0-9]+)/edit/(?P<pk>[0-9]+)', views.AnnualBookingPeriodEditOption.as_view(), name='dash-annual-booking-period-option-edit'),
    re_path(r'^dashboard/annual-bookingperiods-option/(?P<bp_group_id>[0-9]+)/delete/(?P<pk>[0-9]+)', views.AnnualBookingPeriodDeleteOption.as_view(), name='dash-annual-booking-period-option-delete'),
    re_path(r'^dashboard/annual-bookingperiods-option/(?P<bp_group_id>[0-9]+)/create', views.AnnualBookingPeriodAddOption.as_view(), name='dash-annual-booking-period-option-add'),
    re_path(r'^dashboard/annual-bookingperiods/(?P<pk>[0-9]+)/view', views.AnnualBookingPeriodView.as_view(), name='dash-annual-bookingperiod-group-view'),
    re_path(r'^dashboard/annual-bookingperiods/(?P<pk>[0-9]+)/edit', views.AnnualBookingPeriodEditChangeGroup.as_view(), name='dash-annual-bookingperiod-group-edit'),
    re_path(r'^dashboard/annual-bookingperiods/(?P<pk>[0-9]+)/delete', views.AnnualBookingPeriodDeleteGroup.as_view(), name='dash-annual-bookingperiod-group-delete'),
    re_path(r'^dashboard/annual-bookingperiods/create', views.AnnualBookingPeriodAddChangeGroup.as_view(), name='dash-annual-bookingperiod-group-add'),
    re_path(r'^dashboard/annual-bookingperiods', views.AnnualBookingPeriodGroupView.as_view(), name='dash-annualbookingperiod'),
    re_path(r'^dashboard/failed-refunds/(?P<pk>[0-9]+)/complete', views.RefundFailedCompleted.as_view(), name='dash-complete_failed_refund'),
    re_path(r'^dashboard/failed-refunds-completed', views.RefundFailedCompletedView.as_view(), name='dash-failed_refunds_completed'),
    re_path(r'^dashboard/failed-refunds', views.RefundFailedView.as_view(), name='dash-failedrefunds'),
    re_path(r'^dashboard/', views.DashboardView.as_view(), name='dash'),
    #url(r'^dashboard/bookingperiods2', views.DashboardView.as_view(), name='dash-bookingperiod2'),
    re_path(r'^booking/abort$', views.abort_booking_view, name='public_abort_booking'),
    re_path(r'^booking/make/(?P<booking_uuid>[0-9a-f-]{36})/', views.MakeBookingsView.as_view(), name='public_make_booking_uuid'),
    re_path(r'^booking/', views.MakeBookingsView.as_view(), name='public_make_booking'),
    # re_path(r'^refund-payment/', views.RefundPaymentView.as_view(), name='refund_payment'),
    # re_path(r'^no-payment/', views.ZeroBookingView.as_view(), name='no_payment_booking'),
    re_path(r'^mybookings/', views.MyBookingsView.as_view(), name='public_my_bookings'),
    re_path(r'^annual-admissions/(?P<loc>[a-z]+)/$', views.AnnualAdmissionsView.as_view(), name='annual_admissions_view'),
    re_path(r'^booking-history/(?P<pk>[0-9]+)/', views.ViewBookingHistory.as_view(), name='view_booking_history'),
    re_path(r'^booking-history-refund/(?P<pk>[0-9]+)/', views.RefundBookingHistory.as_view(), name='view_refund_booking_history'),
    re_path(r'^annual-admissions-booking-history-refund/(?P<pk>[0-9]+)/', views.RefundAnnualBookingHistory.as_view(), name='view_refund_annual_admissions_booking_history'),
    re_path(r'^view-booking/(?P<pk>[0-9]+)/', views.ViewBookingView.as_view(), name='public_view_booking'),
    re_path(r'^change-booking/(?P<pk>[0-9]+)/', views.ChangeBookingView.as_view(), name='public_change_booking'),
    re_path(r'^cancel-booking/(?P<pk>[0-9]+)/', views.CancelBookingView.as_view(), name='public_cancel_booking'),
    re_path(r'^cancel-admissions-booking/(?P<pk>[0-9]+)/', views.CancelAdmissionsBookingView.as_view(), name='public_cancel_admissions_booking'),
    re_path(r'^success/(?P<booking_token>[0-9a-f-]{36})/', views.BookingSuccessView.as_view(), name='public_booking_success'),
    re_path(r'^annual-admission-success/', views.AnnualAdmissionSuccessView.as_view(), name='public_booking_annual_admission_success'),
    re_path(r'^cancel-completed/(?P<booking_id>[0-9]+)/', views.BookingCancelCompletedView.as_view(), name='public_booking_cancelled'),
    re_path(r'^cancel-admission-completed/(?P<booking_id>[0-9]+)/', views.AdmissionBookingCancelCompletedView.as_view(), name='public_admission_booking_cancelled'),
    re_path(r'^success_admissions/(?P<booking_token>[0-9a-f-]{36})/', views.AdmissionsBookingSuccessView.as_view(), name='public_admissions_success'),
    re_path(r'^createdbasket/', views.AdmissionsBasketCreated.as_view(), name='created_basket'),
    re_path(r'^map/', views.MapView.as_view(), name='map'),
    re_path(r'^admissions/(?P<loc>[a-z]+)/$', views.AdmissionFeesView.as_view(), name='admissions'),
    re_path(r'^admissions/captcha/refresh/$', views.refresh_captcha, name='admissions-captcha-refresh'),
    re_path(r'^admissions-cost/$', views.AdmissionsCostView.as_view(), name='admissions_cost'),
    re_path(r'mooring/payments/invoice-pdf/(?P<reference>\d+)',views.InvoicePDFView.as_view(), name='mooring-invoice-pdf'),
    re_path(r'^mooringsiteratelog/(?P<pk>[0-9]+)/', views.MooringsiteRateLogView.as_view(), name='mooringsiteratelog'),
    re_path(r'^private-media/letter/[0-9]+/[0-9]+/[0-9]+/[0-9]+/(?P<file_id>\d+)-\w+.(?P<extension>\w\w\w\w)$', views.getLetterFile, name='view_private_file2'),

##    url(r'^static/(?P<path>.*)$', 'django.conf.urls.static'),
#    {'document_root': settings.STATIC_ROOT},
] + ledger_patterns 


if settings.DEBUG:  # Serve media locally in development.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
