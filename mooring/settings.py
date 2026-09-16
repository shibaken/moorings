import os
import sys
import hashlib
# from confy import env
import decouple
import logging
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# confy.read_environment_file(BASE_DIR+"/.env")
os.environ.setdefault("BASE_DIR", BASE_DIR)
from ledger_api_client.settings_base import *
from decimal import Decimal


logger = logging.getLogger(__name__)

DEBUG = decouple.config('DEBUG', default=True, cast=bool)
# Controls visibility of the DRF API root view, independent of DEBUG
SHOW_API_ROOT = decouple.config('SHOW_API_ROOT', default=False, cast=bool)
BASE_DIR = None
BASE_DIR_ENV = decouple.config('BASE_DIR', default=None)
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
    'django_bootstrap5',
    'mooring',
    'taggit',
    'rest_framework',
    'rest_framework_gis',
    # 'ledger',
    'ledger_api_client',
    'appmonitor_client',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_vite',
    'django_crispy_jcaptcha',
]

JCAPTCHA_IMAGE_LIST = 'jcaptcha2'

MIDDLEWARE_CLASSES += [
    'mooring.middleware.BookingTimerMiddleware',
    'mooring.middleware.CacheHeaders',
    'mooring.middleware.ForceDebugInContextMiddleware',
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
    ),
    'EXCEPTION_HANDLER': 'mooring.exceptions.custom_exception_handler',
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
LEDGER_UI_ACCOUNTS_MANAGEMENT = [
            {'first_name': {'options' : {'view': True, 'edit': True}}},
            {'last_name': {'options' : {'view': True, 'edit': True}}},
            {'residential_address': {'options' : {'view': True, 'edit': True}}},
            {'phone_number' : {'options' : {'view': True, 'edit': True}}},
            {'mobile_number' : {'options' : {'view': True, 'edit': True}}},
]
LEDGER_UI_ACCOUNTS_MANAGEMENT_KEYS = []
for am in LEDGER_UI_ACCOUNTS_MANAGEMENT:
    LEDGER_UI_ACCOUNTS_MANAGEMENT_KEYS.append(list(am.keys())[0])
LEDGER_UI_CARDS_MANAGEMENT = True
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(BASE_DIR, 'mooring', 'cache'),
    }
}
STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, 'mooring', 'static')))
STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, "mooring", "static", "moorings_vue")))
STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, "mooring", "static", "exploreparks_vue")))
STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, "mooring", "static", "admissions_vue")))
STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, "mooring", "static", "availability2_vue")))

BPAY_ALLOWED = decouple.config('BPAY_ALLOWED', default=False, cast=bool)
OSCAR_BASKET_COOKIE_OPEN = 'mooring_basket'
OSCAR_BASKET_COOKIE_LIFETIME = decouple.config('OSCAR_BASKET_COOKIE_LIFETIME',  default=(7 * 24 * 60 * 60))
OSCAR_BASKET_COOKIE_SECURE = decouple.config('OSCAR_BASKET_COOKIE_SECURE', default=False, cast=bool)

CRON_CLASSES = [
    #'mooring.cron.SendBookingsConfirmationCronJob',
    'mooring.cron.UnpaidBookingsReportCronJob',
    'mooring.cron.OracleIntegrationCronJob',
    'mooring.cron.CheckMooringsNoBookingPeriod',
    'mooring.cron.RegisteredVesselsImport',
    'appmonitor_client.cron.CronJobAppMonitorClient',
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
            'formatter': 'verbose2',
            'maxBytes': 5242880
        }
LOGGING['loggers']['booking_checkout'] = {
            'handlers': ['booking_checkout'],
            'level': 'INFO'
        }
LOGGING['loggers']['django']['propagate'] = True
LOGGING['loggers']['']['level'] = 'DEBUG'

# from pprint import pprint
# print("\n=== LOGGING Configuration ===\n")
# pprint(LOGGING, indent=2, width=80)

#PS_PAYMENT_SYSTEM_ID = env('PS_PAYMENT_SYSTEM_ID', 'S019')
PS_PAYMENT_SYSTEM_ID = decouple.config('PS_PAYMENT_SYSTEM_ID', default='S516')
PAYMENT_SYSTEM_ID = PS_PAYMENT_SYSTEM_ID
if not VALID_SYSTEMS:
    VALID_SYSTEMS = [PS_PAYMENT_SYSTEM_ID]

# External callback URL for development environments
# EXTERNAL_CALLBACK_URL is used in development when the app runs behind a proxy
# or in a container with non-routable internal IPs. Ledger's payment system needs
# a publicly accessible URL to send payment notifications. In production, this
# should be None (uses relative URLs). For local dev, use ngrok or similar tunneling.
#
# Authentication for notification endpoints is handled by validating invoice ownership
# via direct Ledger API queries (basket.booking_reference verification).
#
# Example: 'https://dev-moorings.example.com' or 'https://abc123.ngrok.io'
# Leave as None for production (uses relative URLs)
EXTERNAL_CALLBACK_URL = decouple.config('EXTERNAL_CALLBACK_URL', default=None)

SYSTEM_NAME = decouple.config('SYSTEM_NAME', default='Mooring Rental System')
SYSTEM_NAME_SHORT = decouple.config('SYSTEM_NAME_SHORT', default='mooring')
CAMPGROUNDS_EMAIL = decouple.config('CAMPGROUNDS_EMAIL', default='mooringbookings@dbca.wa.gov.au')
ROTTNEST_EMAIL = decouple.config('ROTTNEST_EMAIL', default='mooringbookings@dbca.wa.gov.au')
DEFAULT_FROM_EMAIL = decouple.config('EMAIL_FROM', default='no-reply@dbca.wa.gov.au')
EXPLORE_PARKS_URL = decouple.config('EXPLORE_PARKS_URL', default='https://mooring.dbca.wa.gov.au/')
PARKSTAY_EXTERNAL_URL = decouple.config('PARKSTAY_EXTERNAL_URL', default='https://mooring.dbca.wa.gov.au/')
ROTTNEST_ISLAND_URL = decouple.config('ROTTNEST_URL', default=[])
DEPT_DOMAINS = decouple.config('DEPT_DOMAINS', default=['dpaw.wa.gov.au', 'dbca.wa.gov.au'])
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
ML_ADMISSION_PAID_CHECK=decouple.config('ML_ADMISSION_PAID_CHECK', default=False, cast=bool)
#os.environ.setdefault("UPDATE_PAYMENT_ALLOCATION", True)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
X_FRAME_OPTIONS = 'SAMEORIGIN'


DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

CSRF_TRUSTED_ORIGINS_STRING = decouple.config("CSRF_TRUSTED_ORIGINS", default='[]')
CSRF_TRUSTED_ORIGINS = json.loads(str(CSRF_TRUSTED_ORIGINS_STRING))

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

GROUP_NAME_MOORING_ADMIN = 'Mooring Admin'
GROUP_NAME_MOORING_INVENTORY = 'Mooring Inventory'
GROUP_NAME_PAYMENTS_OFFICERS = 'Payments Officers'
GROUP_NAME_CHOICES = [
    GROUP_NAME_MOORING_ADMIN,
    GROUP_NAME_MOORING_INVENTORY,
    GROUP_NAME_PAYMENTS_OFFICERS,
]

RUNNING_DEVSERVER = len(sys.argv) > 1 and sys.argv[1] == "runserver"
EMAIL_INSTANCE = decouple.config("EMAIL_INSTANCE", default="DEV")

# Make sure this returns True when in local development
# so you can use the vite dev server with hot module reloading
DJANGO_VITE_DEV_MODE = RUNNING_DEVSERVER and EMAIL_INSTANCE == "DEV" and DEBUG is True  # DJANGO_VITE_DEV_MODE is preserved word.

logger.debug(f'DJANGO_VITE_DEV_MODE: {DJANGO_VITE_DEV_MODE}')

DJANGO_VITE = {
    "moorings_app": {
        "dev_mode": DJANGO_VITE_DEV_MODE,  # Indicates whether to serve assets via the ViteJS development server or from compiled production assets.
        "dev_server_host": "localhost", # Default host for vite (can change if needed)
        "dev_server_port": 8080, # Default port for vite (can change if needed)
        "static_url_prefix": "/static/moorings_vue" if DJANGO_VITE_DEV_MODE else "moorings_vue/",  # The directory prefix for static files built by ViteJS.
    },
    "exploreparks_app": {
        "dev_mode": DJANGO_VITE_DEV_MODE,
        "dev_server_host": "localhost",
        "dev_server_port": 8083,
        "static_url_prefix": "/static/exploreparks_vue" if DJANGO_VITE_DEV_MODE else "exploreparks_vue/",
    },
    "admissions_app": {
        "dev_mode": DJANGO_VITE_DEV_MODE,
        "dev_server_host": "localhost",
        "dev_server_port": 8081,
        "static_url_prefix": "/static/admissions_vue" if DJANGO_VITE_DEV_MODE else "admissions_vue/",
    },
    "availability2_app": {
        "dev_mode": DJANGO_VITE_DEV_MODE,
        "dev_server_host": "localhost",
        "dev_server_port": 8082,
        "static_url_prefix": "/static/availability2_vue" if DJANGO_VITE_DEV_MODE else "availability2_vue/",
    },
}

VUE3_ENTRY_SCRIPT_MOORINGS = decouple.config(  # This is not a reserved keyword.
    "VUE3_ENTRY_SCRIPT_MOORINGS",
    default="src/apps/main.js",  # This path will be auto prefixed with the static_url_prefix from DJANGO_VITE above
)  # Path of the vue3 entry point script served by vite
VUE3_ENTRY_SCRIPT_EXPLOREPARKS = decouple.config(
    "VUE3_ENTRY_SCRIPT_EXPLOREPARKS",
    default="src/main.js",
)
VUE3_ENTRY_SCRIPT_ADMISSIONS = decouple.config(
    "VUE3_ENTRY_SCRIPT_ADMISSIONS",
    default="src/main.js",
)
VUE3_ENTRY_SCRIPT_AVAILABILITY2 = decouple.config(
    "VUE3_ENTRY_SCRIPT_AVAILABILITY2",
    default="src/main.js",
)

DATA_SOURCE_FOR_MAP_LAYERS = decouple.config('DATA_SOURCE_FOR_MAP_LAYERS', default='https://kb.dbca.wa.gov.au')
MOORING_BOOKING_REF_PREFIX = decouple.config('MOORING_BOOKING_REF_PREFIX', 'PS')
DAILY_ADMISSION_REF_PREFIX = decouple.config('DAILY_ADMISSION_REF_PREFIX', 'AD')

SESSION_ENGINE = 'django.contrib.sessions.backends.file'
SESSION_FILE_PATH = decouple.config('SESSION_FILE_PATH', default='/app/session_store/')
# Whether to use a secure cookie for the session cookie
SESSION_COOKIE_SECURE = decouple.config('SESSION_COOKIE_SECURE', default=True, cast=bool)
# Whether to use a secure cookie for the CSRF cookie
CSRF_COOKIE_SECURE = decouple.config('CSRF_COOKIE_SECURE', default=True, cast=bool)
