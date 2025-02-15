import os
from confy import env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# confy.read_environment_file(BASE_DIR+"/.env")
os.environ.setdefault("BASE_DIR", BASE_DIR)
from ledger_api_client.settings_base import *
from decimal import Decimal

BASE_DIR = None
BASE_DIR_ENV = env('BASE_DIR',None)
if BASE_DIR_ENV is None:
   BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
else:
   BASE_DIR = BASE_DIR_ENV

ROOT_URLCONF = 'mooring.urls'
SITE_ID = 1
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_mo')

# number of seconds before expiring a temporary booking
BOOKING_TIMEOUT = 1200

INSTALLED_APPS += [
    'webtemplate_dbca',
    'bootstrap3',
    'mooring',
    'taggit',
    'rest_framework',
    'rest_framework_gis',
    # 'ledger',
    'ledger_api_client',
    'appmonitor_client',
    'crispy_forms',
]

MIDDLEWARE_CLASSES += [
    'mooring.middleware.BookingTimerMiddleware',
    'mooring.middleware.CacheHeaders',
]
MIDDLEWARE = MIDDLEWARE_CLASSES
MIDDLEWARE_CLASSES = None


# maximum number of days allowed for a booking
PS_MAX_BOOKING_LENGTH = 28

# minimum number of remaining campsites to trigger an availaiblity warning
PS_CAMPSITE_COUNT_WARNING = 10

# number of days before clearing un unpaid booking
PS_UNPAID_BOOKING_LAPSE_DAYS = 5

WSGI_APPLICATION = 'mooring.wsgi.application'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'mooring.perms.OfficerPermission',
    )
}

LANGUAGE_CODE = 'en-au'  # This affects time formats.
# disable Django REST Framework UI on prod
if not DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES']=('rest_framework.renderers.JSONRenderer',)
else:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES']=('rest_framework.renderers.JSONRenderer','rest_framework_csv.renderers.CSVRenderer')

del BOOTSTRAP3['css_url'] 
TEMPLATES[0]['DIRS'].append(os.path.join(BASE_DIR, 'mooring', 'templates'))
TEMPLATES[0]['OPTIONS']['context_processors'].append('mooring.context_processors.mooring_url')
#'''BOOTSTRAP3 = {
#    'jquery_url': '/static/common/css/jquery.min.js',
#    'base_url': '/static/common/css//twitter-bootstrap/3.3.6/',
#    'css_url': None,
#    'theme_url': None,
#    'javascript_url': None,
#    'javascript_in_head': False,
#    'include_jquery': False,
#    'required_css_class': 'required-form-field',
#    'set_placeholder': False,
#}'''
LEDGER_TEMPLATE = 'bootstrap5'
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(BASE_DIR, 'mooring', 'cache'),
    }
}
STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, 'mooring', 'static')))


BPAY_ALLOWED = env('BPAY_ALLOWED',False)
OSCAR_BASKET_COOKIE_OPEN = 'mooring_basket'
OSCAR_BASKET_COOKIE_LIFETIME = env('OSCAR_BASKET_COOKIE_LIFETIME', 7 * 24 * 60 * 60)
OSCAR_BASKET_COOKIE_SECURE = env('OSCAR_BASKET_COOKIE_SECURE', False)

CRON_CLASSES = [
    #'mooring.cron.SendBookingsConfirmationCronJob',
    'mooring.cron.UnpaidBookingsReportCronJob',
    'mooring.cron.OracleIntegrationCronJob',
    'mooring.cron.CheckMooringsNoBookingPeriod',
    'mooring.cron.RegisteredVesselsImport',
]

# Additional logging for mooring
LOGGING['disable_existing_loggers'] = False
LOGGING['formatters']['verbose2'] = {
    "format": "%(levelname)s %(asctime)s %(name)s [Line:%(lineno)s][%(funcName)s] %(message)s"
}
LOGGING['handlers']['console']['formatter'] = 'verbose2'
LOGGING['handlers']['console']['level'] = 'DEBUG'
LOGGING['handlers']['file']['formatter'] = 'verbose2'
LOGGING['handlers']['booking_checkout'] = {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'mooring_booking_checkout.log'),
            'formatter': 'verbose',
            'maxBytes': 5242880
        }
LOGGING['loggers']['booking_checkout'] = {
            'handlers': ['booking_checkout'],
            'level': 'INFO'
        }
LOGGING['loggers']['django']['propagate'] = True
LOGGING['loggers']['']['level'] = 'DEBUG'

from pprint import pprint
print("\n=== LOGGING Configuration ===\n")
pprint(LOGGING, indent=2, width=80)

#PS_PAYMENT_SYSTEM_ID = env('PS_PAYMENT_SYSTEM_ID', 'S019')
PS_PAYMENT_SYSTEM_ID = env('PS_PAYMENT_SYSTEM_ID', 'S516')
if not VALID_SYSTEMS:
    VALID_SYSTEMS = [PS_PAYMENT_SYSTEM_ID]

SYSTEM_NAME = env('SYSTEM_NAME', 'Mooring Rental System')
SYSTEM_NAME_SHORT = env('SYSTEM_NAME_SHORT', 'mooring')
CAMPGROUNDS_EMAIL = env('CAMPGROUNDS_EMAIL','mooringbookings@dbca.wa.gov.au')
ROTTNEST_EMAIL = env('ROTTNEST_EMAIL', 'mooringbookings@dbca.wa.gov.au')
DEFAULT_FROM_EMAIL = env('EMAIL_FROM','no-reply@dbca.wa.gov.au')
EXPLORE_PARKS_URL = env('EXPLORE_PARKS_URL','https://mooring.dbca.wa.gov.au/')
PARKSTAY_EXTERNAL_URL = env('PARKSTAY_EXTERNAL_URL','https://mooring.dbca.wa.gov.au/')
DEV_STATIC = env('DEV_STATIC',False)
DEV_STATIC_URL = env('DEV_STATIC_URL')
ROTTNEST_ISLAND_URL = env('ROTTNEST_URL', [])
DEPT_DOMAINS = env('DEPT_DOMAINS', ['dpaw.wa.gov.au', 'dbca.wa.gov.au'])
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Use git commit hash for purging cache in browser for deployment changes
GIT_COMMIT_HASH = ''
GIT_COMMIT_DATE = ''
if  os.path.isdir(BASE_DIR+'/.git/') is True:
    GIT_COMMIT_DATE = os.popen('cd '+BASE_DIR+' ; git log -1 --format=%cd').read()
    GIT_COMMIT_HASH = os.popen('cd  '+BASE_DIR+' ; git log -1 --format=%H').read()
if len(GIT_COMMIT_HASH) == 0: 
    GIT_COMMIT_HASH = os.popen('cat /app/git_hash').read()
    if len(GIT_COMMIT_HASH) == 0:
       print ("ERROR: No git hash provided")
VERSION_NO = '3.10'
os.environ['UPDATE_PAYMENT_ALLOCATION'] = 'True'
UNALLOCATED_ORACLE_CODE = 'NNP449 GST' 

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240 
BOOKING_PROPERTY_CACHE_VERSION = '2.00'
ML_ADMISSION_PAID_CHECK=env('ML_ADMISSION_PAID_CHECK', False)
#os.environ.setdefault("UPDATE_PAYMENT_ALLOCATION", True)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
X_FRAME_OPTIONS = 'SAMEORIGIN'


DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
