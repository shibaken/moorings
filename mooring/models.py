from __future__ import unicode_literals

import os
import uuid
import base64
import binascii
import hashlib
import calendar
import json
import logging
from decimal import Decimal as D
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.gis.db import models
from django.db import models as django_models
from django.db import IntegrityError, transaction, connection
from django.http import HttpRequest
from django.utils import timezone
from datetime import date, time, datetime, timedelta
from django.conf import settings
from taggit.managers import TaggableManager
from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save, post_save,pre_delete
from mooring.exceptions import BookingRangeWithinException
from mooring.sanitisation import SanitisationModelMixin
from django.core.cache import cache
# from ledger.payments.models import Invoice
# from ledger.accounts.models import EmailUser
from ledger_api_client.ledger_models import EmailUserRO as EmailUser, Invoice, Basket
from ledger_api_client.utils import Order, update_payments
from django.core.files.storage import FileSystemStorage
from django.core import serializers
from django.utils.crypto import get_random_string
from ledger_api_client import utils as ledger_api_utils
from django.db.models.deletion import ProtectedError

logger = logging.getLogger(__name__)

#today = datetime.now()
#today_path = today.strftime("%Y/%m/%d/%H")
private_storage = FileSystemStorage(location=settings.BASE_DIR+"/private-media/", base_url='/private-media/')


# Create your models here.

PARKING_SPACE_CHOICES = (
    (0, 'Marinaing within site.'),
    (1, 'Marinaing for exclusive use of site occupiers next to site, but separated from tent space.'),
    (2, 'Marinaing for exclusive use of occupiers, short walk from tent space.'),
    (3, 'Shared parking (not allocated), short walk from tent space.')
)

NUMBER_VEHICLE_CHOICES = (
    (0, 'One vehicle'),
    (1, 'Two vehicles'),
    (2, 'One vehicle + small trailer'),
    (3, 'One vehicle + small trailer/large vehicle')
)

class Contact(SanitisationModelMixin, models.Model):
    sanitise_exclude_fields = set()
    name = models.CharField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(max_length=255)
    description = models.TextField(null=True,blank=True)
    opening_hours = models.TextField(null=True)
    other_services = models.TextField(null=True)
    mooring_group = models.ForeignKey('mooring.MooringAreaGroup', blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return "{}: {}".format(self.name, self.phone_number)

    def save(self, *args, **kwargs):
        if self.mooring_group == None:
            raise ValidationError("Mooring Group required, please select from list.")
        else:
            super(Contact,self).save(*args,**kwargs)


class MarinePark(models.Model):

    ZOOM_LEVEL = (
        (0, 'default'),
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '4'),
        (6, '6'),
        (7, '7'),
        (8, '8'),
        (9, '9'),
        (10, '10'),
        (11, '11'),
        (12, '12'),
        (13, '13'),
        (14, '14'),
        (15, '15'),
        (16, '16'),

    )

    name = models.CharField(max_length=255)
    district = models.ForeignKey('District', null=True, on_delete=models.PROTECT)
    ratis_id = models.IntegerField(default=-1)
    entry_fee_required = models.BooleanField(default=True)
    oracle_code = models.CharField(max_length=50, null=True,blank=True)
    wkb_geometry = models.PointField(srid=4326, blank=True, null=True)
    zoom_level = models.IntegerField(choices=ZOOM_LEVEL,default=-1)  
    distance_radius = models.IntegerField(default=25)
    mooring_group = models.ForeignKey('mooring.MooringAreaGroup', blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return '{} - {}'.format(self.name, self.district)

    def clean(self,*args,**kwargs):
        if self.entry_fee_required and not self.oracle_code:
            raise ValidationError('A park entry oracle code is required if entry fee is required.')

    def save(self,*args,**kwargs):
        if self.mooring_group == None:
            raise ValidationError("Mooring Group required, please select from list.")
        else:
            cache.delete('parks')
            self.full_clean()
            super(MarinePark,self).save(*args,**kwargs)

    class Meta:
        unique_together = (('name',),)


class PromoArea(models.Model):


    ZOOM_LEVEL = (
        (0, 'default'),
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '4'),
        (6, '6'),
        (7, '7'),
        (8, '8'),
        (9, '9'),
        (10, '10'),
        (11, '11'),
        (12, '12'),
        (13, '13'),
        (14, '14'),
        (15, '15'),
        (16, '16'),

    )

    name = models.CharField(max_length=255, unique=True)
    wkb_geometry = models.PointField(srid=4326, blank=True, null=True)
    zoom_level = models.IntegerField(choices=ZOOM_LEVEL,default=-1)
    mooring_group = models.ForeignKey('mooring.MooringAreaGroup', blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.mooring_group == None:
            raise ValidationError("Mooring Group required, please select from list.")
        else:
            super(PromoArea,self).save(*args,**kwargs)

def update_mooring_map_filename(instance, filename):
    return 'mooring/mooring_maps/{}/{}'.format(instance.id,filename)


class MooringArea(models.Model):

    MOORING_TYPE_CHOICES = (
        (0, 'Bookable Online'),
        (1, 'Not Bookable Online'),
        (2, 'Public'),
        (3, 'Unpublished'),
    )

    CAMPGROUND_PRICE_LEVEL_CHOICES = (
        (0, 'Mooring level'),
        (1, 'Mooringsite Class level'),
#        (2, 'Mooringsite level'),
    )

    SITE_TYPE_CHOICES = (
        (0, 'Bookable Per Site'),
       (1, 'Bookable Per Site Type'),
        #(2, 'Bookable Per Site Type (hide site number)'),
    )

    MOORING_PHYSICAL_TYPE_CHOICES = (
        (0, 'Mooring'),
        (1, 'Jetty Pen'),
        (2, 'Beach Pen')
    )

    MOORING_CLASS_CHOICES = (
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large','Large')
    )

    MOORING_SPECIFICATION = (
         (1, 'Rental Mooring'),
         (2, 'Private Mooring'),
    )


    name = models.CharField(max_length=255, null=True)
    park = models.ForeignKey('MarinePark', on_delete=models.PROTECT, related_name='marineparks', verbose_name="marine park")
    ratis_id = models.IntegerField(default=-1)
    contact = models.ForeignKey('Contact', on_delete=models.PROTECT, blank=True, null=True)
    mooring_type = models.SmallIntegerField(choices=MOORING_TYPE_CHOICES, default=3)
    promo_area = models.ForeignKey('PromoArea', on_delete=models.PROTECT,blank=True, null=True)
    site_type = models.SmallIntegerField(choices=SITE_TYPE_CHOICES, default=0)
    address = django_models.JSONField(null=True,blank=True)
    features = models.ManyToManyField('Feature')
    description = models.TextField(blank=True, null=True, default="")
    additional_info = models.TextField(blank=True, null=True, default="")
    area_activities = models.TextField(blank=True, null=True)

    # Tags for communications methods available and access type
    tags = TaggableManager(blank=True)
    driving_directions = models.TextField(blank=True, null=True)
    fees = models.TextField(blank=True, null=True)
    othertransport = models.TextField(blank=True, null=True)
    key = models.CharField(max_length=255, blank=True, null=True)
    price_level = models.SmallIntegerField(choices=CAMPGROUND_PRICE_LEVEL_CHOICES, default=0)
    info_url = models.CharField(max_length=255, blank=True)
    long_description = models.TextField(blank=True,null=True)

    wkb_geometry = models.PointField(srid=4326, blank=True, null=True)
    dog_permitted = models.BooleanField(default=False)
    check_in = models.TimeField(default=time(14))
    check_out = models.TimeField(default=time(10))
    max_advance_booking = models.IntegerField(default=180)
    oracle_code = models.CharField(max_length=50,null=True,blank=True)
    mooring_map = models.FileField(upload_to=update_mooring_map_filename,null=True,blank=True)
    vessel_size_limit = models.FloatField(default=0)
    vessel_draft_limit = models.FloatField(default=0)
    vessel_beam_limit = models.FloatField(default=0)
    vessel_weight_limit = models.FloatField(default=0)
    mooring_physical_type = models.SmallIntegerField(choices=MOORING_PHYSICAL_TYPE_CHOICES, default=0)
    mooring_class = models.CharField(choices=MOORING_CLASS_CHOICES, default=0, max_length=20)
    mooring_specification = models.SmallIntegerField(choices=MOORING_SPECIFICATION, default=1)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return unicode(self.name)

    def save(self,*args,**kwargs):
        cache.delete('marina')
        cache.delete('marina_dt')
        cache.delete('MooringAreaMapViewSet')
        cache.delete('MooringArea:_is_open:'+str(self.id))
        cache.delete('MooringArea:_get_current_closure:'+str(self.id))
        cache.delete('MooringAreaViewSet:datatable_list:row:'+str(self.id))
        cache.delete('mooringareas-object:'+str(self.id))
        cache.delete('mooringareas'+str(bool(False)))
        
        super(MooringArea,self).save(*args,**kwargs)

    class Meta:
        unique_together = (('name', 'park'),)
        verbose_name = 'Mooring'
        verbose_name_plural = 'Moorings'

    # Properties
    # =======================================
    @property
    def region(self):
        return self.park.district.region.name

    @property
    def district(self):
        return self.park.district.name

    @property
    def active(self):
        return self._is_open(timezone.now())

    @property
    def current_closure(self):
        closure = self._get_current_closure()
        if closure:
            start = datetime.fromisoformat(closure['fields']['range_start'][:-1])
            range_end = datetime.fromisoformat(closure['fields']['range_end'][:-1])
            #datetime.strptime(,'%Y-%m-%d ')
            #print (datetime.fromisoformat(start[:-1]))
            timestamp = calendar.timegm(start.timetuple())
            local_dt = datetime.fromtimestamp(timestamp)
            start = local_dt.replace(microsecond=start.microsecond)
            start = start.strftime('%d/%m/%Y %H:%M')
            if range_end:
                end = range_end if range_end else ""
                timestamp = calendar.timegm(end.timetuple())
                local_dt = datetime.fromtimestamp(timestamp)
                end = local_dt.replace(microsecond=end.microsecond)
                end = end.strftime('%d/%m/%Y %H:%M')
            else:
                end = ""
            strTime = 'Start: {} - Reopen: {}'.format(start, end)
            return strTime
        return ''



#    @property
#    def current_closure(self):
#        closure = self._get_current_closure()
#        if closure:
#            start = closure.range_start
#            timestamp = calendar.timegm(start.timetuple())
#            local_dt = datetime.fromtimestamp(timestamp)
#            start = local_dt.replace(microsecond=start.microsecond)
#            start = start.strftime('%d/%m/%Y %H:%M')
#            if closure.range_end:
#                end = closure.range_end if closure.range_end else ""
#                timestamp = calendar.timegm(end.timetuple())
#                local_dt = datetime.fromtimestamp(timestamp)
#                end = local_dt.replace(microsecond=end.microsecond)
#                end = end.strftime('%d/%m/%Y %H:%M')
#            else:
#                end = ""
#            strTime = 'Start: {} Reopen: {}'.format(start, end)
#            return strTime
#        return ''

    @property
    def dog_permitted(self):
        try:
            self.features.get(name='NO DOGS')
            return False
        except Feature.DoesNotExist:
            return True

    @property
    def campfires_allowed(self):
        try:
            self.features.get(name='NO CAMPFIRES')
            return False
        except Feature.DoesNotExist:
            return True

    @property
    def campsite_classes(self):
        return list(set([c.campsite_class.id for c in self.campsites.all()]))

    @property
    def first_image(self):
        images = self.images.all()
        if images.count():
            return images[0]
        return None

    @property
    def email(self):
        if self.contact:
            return self.contact.email
        return None

    @property
    def telephone(self):
        if self.contact:
            return self.contact.phone_number
        return None

    # Methods
    # =======================================
    def _is_open(self,period):
        '''Check if the campground is open on a specified datetime
        '''
        json_data = cache.get('MooringArea:_is_open:'+str(self.id))
        
        is_open = False
        if json_data is None:
            open_ranges, closed_ranges = None, None
            # Get all booking ranges
            try:
                open_ranges = self.booking_ranges.filter(Q(status=0),Q(range_start__lte=period), Q(range_end__gte=period) | Q(range_end__isnull=True) ).latest('updated_on')
                is_open = True
            except MooringAreaBookingRange.DoesNotExist:
                pass
            try:
                closed_ranges = self.booking_ranges.filter(Q(range_start__lte=period),Q(status=1),Q(range_end__gte=period)).latest('updated_on')
                #is_open = False
            except MooringAreaBookingRange.DoesNotExist:
                pass
                #return True if open_ranges else False
            if open_ranges:
                 is_open = True
            if closed_ranges:
                 is_open = False
            cache.set('MooringArea:_is_open:'+str(self.id),is_open,60)
        else:
            is_open = json_data
        #if not open_ranges:
        #    return False
        #if open_ranges.updated_on > closed_ranges.updated_on:
        #    return True
        return is_open


    def _get_current_closure(self):
        closure_period = None
        period = timezone.now()
        if not self.active:
            json_data = cache.get('MooringArea:_get_current_closure:'+str(self.id))
            closure = None
            if json_data is None:
                closure = self.booking_ranges.filter(Q(range_start__lte=period),Q(status=1),Q(range_end__gte=period)).order_by('updated_on')
                closure_json_text = serializers.serialize("json", closure)
                cache.set('MooringArea:_get_current_closure:'+str(self.id),closure_json_text,60)
            else:
                closure_json_text = json_data

            closure_json= json.loads(closure_json_text)
            if closure_json:
                closure_period = closure_json[0]
        return closure_period

    def open(self, data):
        if self.active:
            raise ValidationError('This campground is already open.')
        b = MooringAreaBookingRange(**data)
        try:
            within = MooringAreaBookingRange.objects.filter(Q(campground=b.campground),Q(status=0),Q(range_start__lte=b.range_start), Q(range_end__gte=b.range_start) | Q(range_end__isnull=True) ).latest('updated_on')
            if within:
                within.updated_on = timezone.now()
                within.save(skip_validation=True)

        except MooringAreaBookingRange.DoesNotExist:
        #if (self.__get_current_closure().range_start <= b.range_start and not self.__get_current_closure().range_end) or (self.__get_current_closure().range_start <= b.range_start <= self.__get_current_closure().range_end):
        #    self.__get_current_closure().delete()
            b.save()

    def close(self, data):
        mooring_area_booking_range = MooringAreaBookingRange(**data)
        try:
            within = MooringAreaBookingRange.objects.filter(
                Q(campground=mooring_area_booking_range.campground),
                ~Q(status=0),
                Q(range_start__lte=mooring_area_booking_range.range_start),
                Q(range_end__gte=mooring_area_booking_range.range_start) | Q(range_end__isnull=True)
            ).latest('updated_on')
            if within:
                within.updated_on = timezone.now()
                within.save(skip_validation=True)
                if within.range_start != mooring_area_booking_range.range_start or within.range_end != mooring_area_booking_range.range_end:
                    logger.warning(f'Closing a campground that is already closed: {within.campground.name}. Range start: {within.range_start}, Range end: {within.range_end}')
                    raise ValidationError(f'{within.campground.name} is already closed.')
            else:
                mooring_area_booking_range.save()
        except MooringAreaBookingRange.DoesNotExist:
            logger.debug("DEBUG-count pre b save: ", MooringAreaBookingRange.objects.filter(campground=self.id).count())
            mooring_area_booking_range.save()
            logger.debug("DEBUG-count post b save: ", MooringAreaBookingRange.objects.filter(campground=self.id).count())
        except:
            raise

    def createMooringsitePriceHistory(self,data):
        '''Create Multiple campsite rates
        '''
        try:
            with transaction.atomic():
                for c in self.campsites.all():
                    cr = MooringsiteRate(**data)
                    cr.campsite = c
                    cr.save()
                    MooringsiteRateLog.objects.create(change_type=0,mooringarea=self,booking_period=cr.booking_period, date_start=cr.date_start, date_end=cr.date_end,reason=cr.reason,details=cr.details)
        except Exception as e:
            raise

    def updatePriceHistory(self,original,_new):
        '''Update Multiple campsite rates
        '''
        try:
            rates = MooringsiteRate.objects.filter(**original)
            campsites = self.campsites.all()
            with transaction.atomic():
                for r in rates:
                    if r.campsite in campsites and r.update_level == 0:
                        r.update(_new)
                        MooringsiteRateLog.objects.create(change_type=1,mooringarea=self,booking_period=_new['booking_period'], date_start=r.date_start, date_end=_new['date_end'],reason=_new['reason'],details=_new['details'])
        except Exception as e:
            raise

    def deletePriceHistory(self,data):
        '''Delete Multiple campsite rates
        '''
        try:
            rates = MooringsiteRate.objects.filter(**data)
            campsites = self.campsites.all()
            with transaction.atomic():
                for r in rates:
                    if r.campsite in campsites and r.update_level == 0:
                        MooringsiteRateLog.objects.create(change_type=2,mooringarea=self,booking_period=r.booking_period, date_start=r.date_start, date_end=r.date_end,reason=r.reason,details=r.details)
                        r.delete()

        except Exception as e:
            raise

def campground_image_path(instance, filename):
    return '/'.join(['mooring', 'campground_images', filename])


class MooringAreaGroup(models.Model):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(EmailUser, blank=True, through='MooringAreaGroupMember')
    moorings = models.ManyToManyField(MooringArea,blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Mooring Group'
        verbose_name_plural = 'Mooring Groups'


class MooringAreaGroupMember(models.Model):
    """
    A Model introduced to fix the ManyToManyField that stopped working due to the change from EmailUser to EmailUserRO. The existing intermediate table is specified using the db_table option.
    """
    mooringareagroup = models.ForeignKey(MooringAreaGroup, on_delete=models.CASCADE)
    emailuser = models.ForeignKey(EmailUser, on_delete=models.CASCADE)  # By using the field name "emailuser" here, the ManyToMany relationship will function correctly without changing the column name from emailuser_id to emailuserro_id in the existing intermediate table.

    class Meta:
        db_table = 'mooring_mooringareagroup_members'  # Specify the existing intermediate table


class MooringAreaImage(models.Model):
    image = models.ImageField(max_length=255, upload_to=campground_image_path)
    campground = models.ForeignKey(MooringArea, related_name='images', on_delete=models.CASCADE)
    checksum = models.CharField(blank=True, max_length=255, editable=False)

    class Meta:
        ordering = ('id',)

    def get_file_extension(self, file_name, decoded_file):
        import imghdr

        extension = imghdr.what(file_name, decoded_file)
        extension = "jpg" if extension == "jpeg" else extension
        return extension

    def strip_b64_header(self, content):
        if ';base64,' in content:
            header, base64_data = content.split(';base64,')
            return base64_data
        return content

    def _calculate_checksum(self, content):
        checksum = hashlib.md5()
        checksum.update(content.read())
        return base64.b64encode(checksum.digest())

    def createImage(self, content):
        base64_data = self.strip_b64_header(content)
        try:
            decoded_file = base64.b64decode(base64_data)
        except (TypeError, binascii.Error):
            raise ValidationError(self.INVALID_FILE_MESSAGE)
        file_name = str(uuid.uuid4())[:12]
        file_extension = self.get_file_extension(file_name,decoded_file)
        complete_file_name = "{}.{}".format(file_name, file_extension)
        uploaded_image = ContentFile(decoded_file, name=complete_file_name)
        return uploaded_image

    def save(self, *args, **kwargs):
        self.checksum = self._calculate_checksum(self.image)
        self.image.seek(0)
        if not self.pk:
            self.image = self.createImage(base64.b64encode(self.image.read()).decode('ascii'))
        else:
            orig = MooringAreaImage.objects.get(pk=self.pk)
            if orig.image:
                if orig.checksum != self.checksum:
                    if os.path.isfile(orig.image.path):
                        os.remove(orig.image)
                    self.image = self.createImage(base64.b64encode(self.image.read()).decode('ascii'))
                else:
                    pass

        super(MooringAreaImage,self).save(*args,**kwargs)

    def delete(self, *args, **kwargs):
        try:
            os.remove(self.image)
        except:
            pass
        super(MooringAreaImage,self).delete(*args,**kwargs)

class AnnualAdmissionEmail(models.Model):
    mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False, on_delete=models.CASCADE)
    email = models.CharField(max_length=300)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.email



class EmailGroup(models.Model):

    EMAIL_GROUP = (
        (0, 'Mooring Booking Checks'),
        (1, 'Annual Admission Booking Checks'),
        (2, 'Daily Admission Booking Checks'),
    )

    mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False, on_delete=models.CASCADE)
    email_group = models.SmallIntegerField(choices=EMAIL_GROUP, default=0)
    email = models.CharField(max_length=300)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.email


class AnnualBookingPeriodGroup(models.Model):

    STATUS = (
        (0, 'Inactive'),
        (1, 'Active'),
    )

    name = models.CharField(max_length=100)
    mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False, on_delete=models.CASCADE)
    start_time = models.DateTimeField(null=True, blank=True)
    finish_time = models.DateTimeField(null=True, blank=True)
    status = models.SmallIntegerField(choices=STATUS, default=1)
    #letter = models.FileField(upload_to=letter_storage,null=True,blank=True)
    letter = models.FileField(max_length=512, upload_to='letter/%Y/%m/%d/%H/', storage=private_storage, null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def save(self, **kwargs):
        if self.letter:
           print (self.letter.name)
           self.letter.name = str(self.id)+'-'+self.letter.name

        super(AnnualBookingPeriodGroup, self).save()         
        #return 'letter/%Y/%m/%d/%H/'+self.id
    def delete(self, **kwargs):
        if BookingAnnualAdmission.objects.filter(annual_booking_period_group=self).count() > 0:
             raise ValidationError('Unable to delete to existing annual admissions bookings linked to this annual admission booking group.')
        else:
            super(AnnualBookingPeriodGroup, self).delete()
class AnnualBookingPeriodOption(models.Model):

    annual_booking_period_group = models.ForeignKey('AnnualBookingPeriodGroup', blank=False, null=False, on_delete=models.CASCADE)
    start_time = models.DateTimeField(null=True, blank=True)
    finish_time = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.start_time.strftime('%Y-%m-%d %H:%M:%S')+' to '+self.finish_time.strftime('%Y-%m-%d %H:%M:%S')


class VesselSizeCategory(models.Model):

    STATUS = (
        (0, 'Inactive'),
        (1, 'Active'),
    )

    name = models.CharField(max_length=100)
    start_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00') 
    end_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    status = models.SmallIntegerField(choices=STATUS, default=1)
    mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Vessel Size Categories"


class AnnualBookingPeriodOptionVesselCategoryPrice(models.Model):

    annual_booking_period_option = models.ForeignKey('AnnualBookingPeriodOption', blank=False, null=False, on_delete=models.CASCADE)
    vessel_category = models.ForeignKey('VesselSizeCategory', blank=False, null=False, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=True, null=True, unique=False)
    oracle_code = models.CharField(max_length=50,null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.price)

class ChangePricePeriod(models.Model):

    REFUND_CALCULATION_TYPE = (
        (0, 'Percentage'),
        (1, 'Fixed Price'),
    )

    calulation_type = models.SmallIntegerField(choices=REFUND_CALCULATION_TYPE, default=0)
    percentage = models.FloatField(blank=True,null=True)
    amount =  models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    days = models.IntegerField()
    oracle_code = models.CharField(max_length=50,null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.calulation_type == 0:
           return 'Percentage - {}% for {} day/s'.format(str(self.percentage), str(self.days))
        else:
           return 'Fixed Price - ${} for {} day/s'.format(str(self.amount), str(self.days))

class ChangeGroup(models.Model):
    name = models.CharField(max_length=100)
    change_period = models.ManyToManyField(ChangePricePeriod, related_name='refund_period_options')
    created = models.DateTimeField(auto_now_add=True)
    mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class CancelPricePeriod(models.Model):

    REFUND_CALCULATION_TYPE = (
        (0, 'Percentage'),
        (1, 'Fixed Price'),
    )

    calulation_type = models.SmallIntegerField(choices=REFUND_CALCULATION_TYPE, default=0)
    percentage = models.FloatField(blank=True,null=True)
    amount =  models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    days = models.IntegerField()
    oracle_code = models.CharField(max_length=50,null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.calulation_type == 0:
           return 'Percentage - {}% for {} day/s'.format(str(self.percentage), str(self.days))
        else:
           return 'Fixed Price - ${} for {} day/s'.format(str(self.amount), str(self.days))

class CancelGroup(models.Model):
    name = models.CharField(max_length=100)
    cancel_period = models.ManyToManyField(CancelPricePeriod, related_name='cancel_period_options')
    created = models.DateTimeField(auto_now_add=True)
    mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class BookingPeriodOption(models.Model):
    period_name = models.CharField(max_length=15)
    option_description = models.CharField(max_length=255)
    small_price = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=True, null=True, unique=False)
    medium_price = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=True, null=True, unique=False)
    large_price = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=True, null=True, unique=False)
    start_time = models.TimeField(null=True, blank=True)
    finish_time = models.TimeField(null=True, blank=True)
    all_day = models.BooleanField(default=True)
    change_group = models.ForeignKey('ChangeGroup',null=True,blank=True, on_delete=models.SET_NULL)
    cancel_group = models.ForeignKey('CancelGroup',null=True,blank=True, on_delete=models.SET_NULL)
    caption = models.TextField(blank=True,null=True, max_length=255)
    created = models.DateTimeField(auto_now_add=True)
    #mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False)

    def __str__(self):
        return self.period_name

    def __unicode__(self):
        return unicode(self.period_name) or u''

class BookingPeriod(models.Model):
    name = models.CharField(max_length=100)
    booking_period = models.ManyToManyField(BookingPeriodOption, related_name='booking_period_options')
    mooring_group = models.ForeignKey('MooringAreaGroup', blank=True, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return unicode(self.name) or u''

    def delete(self, *args, **kwargs):
        try:
            return super().delete(*args, **kwargs)
        except ProtectedError as e:
            logger.warning(f'Deletion of BookingPeriod[{self}] is protected by ProtectedError.')
        except Exception as e:
            logger.error(f'{e}')

class BookingRange(models.Model):
    BOOKING_RANGE_CHOICES = (
        (0, 'Open'),
        (1, 'Closed'),
    )
    created = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now_add=True,help_text='Used to check if the start and end dated were changed')

    status = models.SmallIntegerField(choices=BOOKING_RANGE_CHOICES, default=0)
    closure_reason = models.ForeignKey('ClosureReason', null=True, blank=True, on_delete=models.SET_NULL)
    open_reason = models.ForeignKey('OpenReason', null=True, blank=True, on_delete=models.SET_NULL)
    details = models.TextField(blank=True,null=True)
    range_start = models.DateTimeField(blank=True, null=True)
    range_end = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    # Properties
    # ====================================
    @property
    def editable(self):
        today = timezone.now()
        if self.status != 0 and((self.range_start <= today and not self.range_end) or (self.range_start <= today and self.range_end > today) or (self.range_start > today and not self.range_end) or ( self.range_start >= today <= self.range_end)):
            return True
        elif self.status == 0 and ((self.range_start <= today and not self.range_end) or self.range_start > today):
            return True
        return False

    @property
    def reason(self):
        if self.status == 0:
            return self.open_reason.text
        return self.closure_reason.text

    # Methods
    # =====================================
    def _is_same(self,other):
        if not isinstance(other, BookingRange) and self.id != other.id:
            return False
        if self.range_start == other.range_start and self.range_end == other.range_end:
            return True
        return False

    def clean(self, *args, **kwargs):
        if self.range_end and self.range_end < self.range_start:
            raise ValidationError('The end date cannot be before the start date.')

    def save(self, *args, **kwargs):
        skip_validation = bool(kwargs.pop('skip_validation',False))
        if not skip_validation:
            self.full_clean()
        if self.status == 1 and not self.closure_reason:
            self.closure_reason = ClosureReason.objects.all().first()
        elif self.status == 0 and not self.open_reason:
            self.open_reason = OpenReason.objects.all().first()

        super(BookingRange, self).save(*args, **kwargs)

    def __str__(self):
        return '{} {} - {}'.format(self.status, self.range_start, self.range_end)

class StayHistory(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    # minimum/maximum consecutive days allowed for a booking
    min_days = models.SmallIntegerField(default=1)
    max_days = models.SmallIntegerField(default=28)
    # Minimum and Maximum days that a booking can be made before arrival
    min_dba = models.SmallIntegerField(default=0)
    max_dba = models.SmallIntegerField(default=180)

    reason = models.ForeignKey('MaximumStayReason', blank=True, null=True, on_delete=models.SET_NULL)
    details = models.TextField(blank=True,null=True)
    range_start = models.DateField(blank=True, null=True)
    range_end = models.DateField(blank=True, null=True)

    class Meta:
        abstract = True

    # Properties
    # ====================================
    @property
    def editable(self):
        now = datetime.now().date()
        if (self.range_start <= now and not self.range_end) or ( self.range_start <= now <= self.range_end):
            return True
        elif (self.range_start >= now and not self.range_end) or ( self.range_start >= now <= self.range_end):
            return True
        return False

    # Methods
    # =====================================
    def clean(self, *args, **kwargs):
        if self.min_days < 1:
            raise ValidationError('The minimum days should be greater than 0.')
        if self.max_days > 28:
            raise ValidationError('The maximum days should not be greater than 28.')

class MooringAreaBookingRange(BookingRange):
    campground = models.ForeignKey('MooringArea', on_delete=models.CASCADE,related_name='booking_ranges', verbose_name="mooring")
    # minimum/maximum number of campsites allowed for a booking
    min_sites = models.SmallIntegerField(default=1)
    max_sites = models.SmallIntegerField(default=12)

    # Properties
    # ====================================

    # Methods
    # =====================================
    def _is_same(self,other):
        if not isinstance(other, MooringAreaBookingRange) and self.id != other.id:
            return False
        if self.range_start == other.range_start and self.range_end == other.range_end:
            return True
        return False

    def clean(self, *args, **kwargs):
        original = None

        # Preventing ranges within other ranges
        within = MooringAreaBookingRange.objects.filter(Q(campground=self.campground),~Q(pk=self.pk),Q(status=self.status),Q(range_start__lte=self.range_start), Q(range_end__gte=self.range_start) | Q(range_end__isnull=True) )
        #if within:
            #raise BookingRangeWithinException('This Booking Range is within the range of another one')
        if self.pk:
            original = MooringAreaBookingRange.objects.get(pk=self.pk)
            if not original.editable:
                raise ValidationError('This Booking Range is not editable')
            if self.range_start < timezone.now() and original.range_start != self.range_start:
                raise ValidationError('The start date can\'t be in the past')
        super(MooringAreaBookingRange,self).clean(*args, **kwargs)

class MooringsiteRateLog(models.Model):
    CHANGE_TYPE = (
        (0, 'New'),
        (1, 'Change'),
        (2, 'Delete')
    )

    change_type = models.SmallIntegerField(choices=CHANGE_TYPE, default=None, null=True, blank=True)
    mooringarea= models.ForeignKey('MooringArea', on_delete=models.PROTECT, related_name='marinearea', verbose_name="mooring")
    booking_period = models.ForeignKey(BookingPeriod, on_delete=models.PROTECT, null=True, blank=True)
    date_start = models.DateField(default=date.today)
    date_end = models.DateField(null=True, blank=True)
    reason = models.ForeignKey('PriceReason', null=True, blank=True, on_delete=models.SET_NULL)
    details = models.TextField(null=True,blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True,blank=True)

    def __str__(self):
        return self.mooringarea

class Mooringsite(models.Model):
    mooringarea = models.ForeignKey('MooringArea', db_index=True, on_delete=models.CASCADE, related_name='campsites', verbose_name="mooring")
    name = models.CharField(max_length=255)
    mooringsite_class = models.ForeignKey('MooringsiteClass', on_delete=models.PROTECT, null=True,blank=True, related_name='campsites')
    wkb_geometry = models.PointField(srid=4326, blank=True, null=True)
    features = models.ManyToManyField('Feature')
    tent = models.BooleanField(default=True)
    campervan = models.BooleanField(default=False)
    caravan = models.BooleanField(default=False)
    min_people = models.SmallIntegerField(default=1)
    max_people = models.SmallIntegerField(default=12)
    description = models.TextField(null=True)

    def __str__(self):
        return '{} - {}'.format(self.mooringarea, self.name)

    class Meta:
        unique_together = (('mooringarea', 'name'),)

    # Properties
    # ==============================
    @property
    def type(self):
        return self.mooringsite_class.name

    @property
    def price(self):
        return 'Set at {}'.format(self.mooringarea.get_price_level_display())

    @property
    def can_add_rate(self):
        return self.mooringarea.price_level == 2

    @property
    def active(self):
        return self._is_open(datetime.now().date())

    @property
    def campground_open(self):
        return self.__is_campground_open()

    @property
    def current_closure(self):
        closure = self.__get_current_closure()
        if closure:
            return 'Start: {} End: {}'.format(closure.range_start.strftime('%d/%m/%Y'), closure.range_end.strftime('%d/%m/%Y') if closure.range_end else "")
        return ''
    # Methods
    # =======================================
    def __is_campground_open(self):
        return self.mooringarea.active

    def _is_open(self,period):
        '''Check if the campsite is open on a specified datetime
        '''
        if self.__is_campground_open():
            open_ranges, closed_ranges = None, None
            # Get all booking ranges
            try:
                open_ranges = self.booking_ranges.filter(Q(status=0),Q(range_start__lte=period), Q(range_end__gte=period) | Q(range_end__isnull=True) ).latest('updated_on')
            except MooringsiteBookingRange.DoesNotExist:
                pass
            try:
                closed_ranges = self.booking_ranges.filter(Q(range_start__lte=period),~Q(status=0),Q(range_end__gte=period) ).latest('updated_on')
            except MooringsiteBookingRange.DoesNotExist:
                return True if open_ranges else False

            if not open_ranges:
                return False
            if open_ranges.updated_on > closed_ranges.updated_on:
                return True
        return False

    def __get_current_closure(self):
        if self.__is_campground_open():
            closure_period = None
            period = datetime.now().date()
            if not self.active:
                closure = self.booking_ranges.get(Q(range_start__lte=period),Q(status=1),Q(range_end__gte=period))
                closure_period = closure
            return closure_period
        else:
            return self.campground._get_current_closure()

    def open(self, data):
        if not self.campground_open:
            raise ValidationError('You can\'t open this campsite until the campground is open')
        if self.active:
            raise ValidationError('This campsite is already open.')
        b = MooringsiteBookingRange(**data)
        try:
            within = MooringsiteBookingRange.objects.filter(Q(campsite=b.campsite),Q(status=0),Q(range_start__lte=b.range_start), Q(range_end__gte=b.range_start) | Q(range_end__isnull=True) ).latest('updated_on')
            if within:
                within.updated_on = timezone.now()
                within.save(skip_validation=True)
        except MooringsiteBookingRange.DoesNotExist:
            b.save()

    def close(self, data):
        if not self.active:
            raise ValidationError('This is already closed.')
        b = MooringsiteBookingRange(**data)
        try:
            within = MooringsiteBookingRange.objects.filter(Q(campsite=b.campsite),~Q(status=0),Q(range_start__lte=b.range_start), Q(range_end__gte=b.range_start) | Q(range_end__isnull=True) ).latest('updated_on')
            if within:
                within.updated_on = timezone.now()
                within.save(skip_validation=True)
        except MooringsiteBookingRange.DoesNotExist:
            b.save()

    @staticmethod
    def bulk_create(number,data):
        try:
            created_campsites = []
            with transaction.atomic():
                campsites = []
                latest = 0
                current_campsites = Mooringsite.objects.filter(campground=data['campground'])
                cs_numbers = [int(c.name) for c in current_campsites if c.name.isdigit()]
                if cs_numbers:
                    latest = max(cs_numbers)
                for i in range(number):
                    latest += 1
                    c = Mooringsite(**data)
                    name = str(latest)
                    if len(name) == 1:
                        name = '0{}'.format(name)
                    c.name = name
                    c.save()
                    if c.campsite_class:
                        for attr in ['tent', 'campervan', 'caravan', 'min_people', 'max_people', 'description']:
                            if attr not in data:
                                setattr(c, attr, getattr(c.campsite_class, attr))
                        c.features = c.campsite_class.features.all()
                        c.save()
                    created_campsites.append(c)
            return created_campsites
        except Exception:
            raise

class MooringsiteBookingRange(BookingRange):
    campsite = models.ForeignKey('Mooringsite', on_delete=models.CASCADE,related_name='booking_ranges', verbose_name="mooring site")

    # Properties
    # ====================================

    # Methods
    # =====================================
    def _is_same(self,other):
#        if not isinstance(other, MooringsiteBookingRange) and self.id != other.id:
#            return False
#        if self.range_start == other.range_start and self.range_end == other.range_end:
#            return True
        return False

#    def clean(self, *args, **kwargs):
#        original = None
#        # Preventing ranges within other ranges
#        within = MooringsiteBookingRange.objects.filter(Q(campsite=self.campsite),~Q(pk=self.pk),Q(status=self.status),Q(range_start__lte=self.range_start), Q(range_end__gte=self.range_start) | Q(range_end__isnull=True) )
#        if within:
#            raise BookingRangeWithinException('This Booking Range is within the range of another one')
#        if self.pk:
#            original = MooringsiteBookingRange.objects.get(pk=self.pk)
#            if not original.editable:
#                raise ValidationError('This Booking Range is not editable')
#            if self.range_start < datetime.now().date() and original.range_start != self.range_start:
#                raise ValidationError('The start date can\'t be in the past')

    def __str__(self):
        return '{}: {} {} - {}'.format(self.campsite, self.status, self.range_start, self.range_end)

class MooringsiteStayHistory(StayHistory):
    campsite = models.ForeignKey('Mooringsite', on_delete=models.CASCADE,related_name='stay_history', verbose_name="mooring site")

class MooringAreaStayHistory(StayHistory):
    mooringarea = models.ForeignKey('MooringArea', on_delete=models.CASCADE,related_name='stay_history', verbose_name="mooring")

class Feature(models.Model):
    TYPE_CHOICES = (
        (0, 'Campground'),
        (1, 'Mooringsite'),
        (2, 'Not Linked')
    )
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True)
    image = models.ImageField(null=True)
    type = models.SmallIntegerField(choices=TYPE_CHOICES,default=2,help_text="Set the model where the feature is located.")

    def __str__(self):
        return self.name


class Region(models.Model):

    ZOOM_LEVEL = (
        (0, 'default'),
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '4'),
        (6, '6'),
        (7, '7'),
        (8, '8'),
        (9, '9'),
        (10, '10'),
        (11, '11'),
        (12, '12'),
        (13, '13'),
        (14, '14'),
        (15, '15'),
        (16, '16'),

    )


    name = models.CharField(max_length=255, unique=True)
    abbreviation = models.CharField(max_length=16, null=True, unique=True)
    ratis_id = models.IntegerField(default=-1)
    wkb_geometry = models.PointField(srid=4326, blank=True, null=True)
    zoom_level = models.IntegerField(choices=ZOOM_LEVEL,default=-1)
    mooring_group = models.ForeignKey(MooringAreaGroup, blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name
        
    def save(self, *args, **kwargs):
        if self.mooring_group == None:
            raise ValidationError("Mooring Group required, please select from list.")
        else:
            super(Region,self).save(*args,**kwargs)

class District(models.Model):
    name = models.CharField(max_length=255, unique=True)
    abbreviation = models.CharField(max_length=16, null=True, unique=True)
    region = models.ForeignKey('Region', on_delete=models.PROTECT)
    ratis_id = models.IntegerField(default=-1)
    mooring_group = models.ForeignKey(MooringAreaGroup, blank=True, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.mooring_group == None:
            raise ValidationError("Mooring Group required, please select from list.")
        else:
            super(District,self).save(*args,**kwargs)


class MooringsiteClass(models.Model):

    name = models.CharField(max_length=255, unique=True)
    camp_unit_suitability = TaggableManager()
    tent = models.BooleanField(default=True)
    campervan = models.BooleanField(default=False)
    caravan = models.BooleanField(default=False)
    min_people = models.SmallIntegerField(default=1)
    max_people = models.SmallIntegerField(default=12)
    features = models.ManyToManyField('Feature')
    deleted = models.BooleanField(default=False)
    description = models.TextField(null=True)
    max_vehicles = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.name

    def delete(self, permanently=False,using=None):
        if not permanently:
            self.deleted = True
            self.save()
        else:
            super(MooringsiteClass, self).delete(using)

    # Property
    # ===========================
    def can_add_rate(self):
        can_add = False
        campsites = self.campsites.all()
        for c in campsites:
            if c.mooringarea.price_level == 1:
                can_add = True
                break
        return can_add

    # Methods
    # ===========================
    def createMooringsitePriceHistory(self,data):
        '''Create Multiple campsite rates
        '''
        try:
            with transaction.atomic():
                for c in self.campsites.all():
                    cr = MooringsiteRate(**data)
                    cr.campsite = c
                    cr.save()
        except Exception as e:
            raise

    def updatePriceHistory(self,original,_new):
        '''Update Multiple campsite rates
        '''
        try:
            rates = MooringsiteRate.objects.filter(**original)
            campsites = self.campsites.all()
            with transaction.atomic():
                for r in rates:
                    if r.campsite in campsites and r.update_level == 1:
                        r.update(_new)
        except Exception as e:
            raise

    def deletePriceHistory(self,data):
        '''Delete Multiple campsite rates
        '''
        try:
            rates = MooringsiteRate.objects.filter(**data)
            campsites = self.campsites.all()
            with transaction.atomic():
                for r in rates:
                    if r.campsite in campsites and r.update_level == 1:
                        r.delete()
        except Exception as e:
            raise


class MooringsiteBooking(models.Model):
    BOOKING_TYPE_CHOICES = (
        (0, 'Reception booking'),
        (1, 'Internet booking'),
        (2, 'Black booking'),
        (3, 'Temporary reservation'),
        (4, 'Cancelled Booking'),
        (5, 'Changed Booking')
    )

    campsite = models.ForeignKey('Mooringsite', db_index=True, on_delete=models.PROTECT, verbose_name="mooring site")
    date = models.DateField(db_index=True)
    # ria multiple booking
    from_dt = models.DateTimeField(blank=True, null=True, verbose_name="date_from")
    to_dt = models.DateTimeField(blank=True, null=True, verbose_name="date_to")
    amount = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=True, null=True, unique=False) 
    booking = models.ForeignKey('Booking', related_name="campsites", on_delete=models.CASCADE, null=True)
    booking_type = models.SmallIntegerField(choices=BOOKING_TYPE_CHOICES, default=0)
    booking_period_option = models.ForeignKey('BookingPeriodOption', related_name="booking_period_option", on_delete=models.PROTECT, null=True)

    def __str__(self):
        return '{} - {}'.format(self.campsite, self.date)

#    class Meta:
#        unique_together = (('campsite', 'date'),)


class Rate(models.Model):
    mooring = models.DecimalField(max_digits=8, decimal_places=2, default='10.00', unique=False)
    adult = models.DecimalField(max_digits=8, decimal_places=2, default='10.00', blank=True, null=True, unique=False)
    concession = models.DecimalField(max_digits=8, decimal_places=2, default='6.60', blank=True, null=True, unique=False)
    child = models.DecimalField(max_digits=8, decimal_places=2, default='2.20', blank=True, null=True, unique=False)
    infant = models.DecimalField(max_digits=8, decimal_places=2, default='0', blank=True, null=True, unique=False)

    def __str__(self):
        return 'Mooring: ${} '.format(self.mooring,)
        #return 'adult: ${}, concession: ${}, child: ${}, infant: ${}'.format(self.adult, self.concession, self.child, self.infant)

    #class Meta:
    #    unique_together = (('adult', 'concession', 'child', 'infant'),)

    # Properties
    # =================================
    @property
    def name(self):
        return 'Mooring: ${} '.format(self.mooring,)
        #return 'adult: ${}, concession: ${}, child: ${}, infant: ${}'.format(self.adult, self.concession, self.child, self.infant)

class MooringsiteRate(models.Model):
    RATE_TYPE_CHOICES = (
        (0, 'Standard'),
        (1, 'Discounted'),
    )

    UPDATE_LEVEL_CHOICES = (
        (0, 'Mooring level'),
        (1, 'Mooring site Class level'),
        (2, 'Mooring site level'),
    )

    PRICE_MODEL_CHOICES = (
        (0, 'Price per Person'),
        (1, 'Fixed Price'),
    )

    campsite = models.ForeignKey('Mooringsite', on_delete=models.PROTECT, related_name='rates', verbose_name="mooring site")
    rate = models.ForeignKey('Rate', on_delete=models.PROTECT)
    booking_period = models.ForeignKey(BookingPeriod, on_delete=models.PROTECT, null=True, blank=True)
    allow_public_holidays = models.BooleanField(default=True)
    date_start = models.DateField(default=date.today)
    date_end = models.DateField(null=True, blank=True)
    rate_type = models.SmallIntegerField(choices=RATE_TYPE_CHOICES, default=0)
    price_model = models.SmallIntegerField(choices=PRICE_MODEL_CHOICES, default=0)
    reason = models.ForeignKey('PriceReason', null=True, blank=True, on_delete=models.SET_NULL)
    details = models.TextField(null=True,blank=True)
    update_level = models.SmallIntegerField(choices=UPDATE_LEVEL_CHOICES, default=0)
   
    def get_rate(self, num_adult=0, num_concession=0, num_child=0, num_infant=0):
        return self.rate.adult*num_adult + self.rate.concession*num_concession + \
                self.rate.child*num_child + self.rate.infant*num_infant

    def __str__(self):
        return '{} - ({})'.format(self.campsite, self.rate)

    class Meta:
        unique_together = (('campsite', 'rate', 'date_start','date_end'),)

    # Properties
    # =================================
    @property
    def deletable(self):
        today = datetime.now().date()
        if self.date_start >= today:
            return True
        return False

    @property
    def editable(self):
        today = datetime.now().date()
        if (self.date_start > today and not self.date_end) or ( self.date_start > today <= self.date_end):
            return True
        return True 

    # Methods
    # =================================
    def update(self,data):
        for attr, value in data.items():
            setattr(self, attr, value)
        self.save()

class BookingAnnualAdmission(SanitisationModelMixin, models.Model):
    sanitise_exclude_fields = set()

    BOOKING_TYPE_CHOICES = (
        (0, 'Reception booking'),
        (1, 'Internet booking'),
        (2, 'Black booking'),
        (3, 'Temporary reservation'),
        (4, 'Cancelled Booking'),
        (5, 'Changed Booking')
    )

    # customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)
    customer_id = models.IntegerField(blank=True, null=True)
    start_dt = models.DateTimeField()
    expiry_dt = models.DateTimeField()
    details = django_models.JSONField(null=True, blank=True)
    rego_no = models.CharField(max_length=255, blank=True,null=True) 
    booking_type = models.SmallIntegerField(choices=BOOKING_TYPE_CHOICES, default=0)
    annual_booking_period_group = models.ForeignKey('AnnualBookingPeriodGroup',null=True, blank=True, on_delete=models.SET_NULL)
    cost_total = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    override_price = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    override_reason = models.ForeignKey('DiscountReason', null=True, blank=True, on_delete=models.SET_NULL)
    override_reason_info = models.TextField(blank=True, null=True)
    # overridden_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, blank=True, null=True, related_name='overridden_annual_bookings')
    overridden_by_id = models.IntegerField(blank=True, null=True)
    is_canceled = models.BooleanField(default=False)
    send_invoice = models.BooleanField(default=False)
    cancellation_reason = models.TextField(null=True,blank=True)
    cancelation_time = models.DateTimeField(null=True,blank=True)
    confirmation_sent = models.BooleanField(default=False)
    created = models.DateTimeField(default=timezone.now)
    # created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, blank=True, null=True,related_name='created_by_annual_booking')
    created_by_id = models.IntegerField(blank=True, null=True)
    # canceled_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, blank=True, null=True,related_name='canceled_annual_bookings')
    canceled_by_id = models.IntegerField(blank=True, null=True)
    override_lines = django_models.JSONField(null=True, blank=True, default=dict)
    sticker_no = models.TextField(blank=True, null=True) 
    sticker_created = models.DateTimeField(null=True,blank=True, editable=False)
    sticker_no_history = django_models.JSONField(null=True, blank=True, default=dict)

    def __str__(self):
         return str(self.id)


    @property
    def confirmation_number(self):
         return 'AA{}'.format(self.id)


class BookingAnnualInvoice(models.Model):
    booking_annual_admission = models.ForeignKey(BookingAnnualAdmission, related_name='annual_booking_invoices', on_delete=models.CASCADE)
    invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    system_invoice = models.BooleanField(default=False)

    def __str__(self):
        return 'Booking {} : Invoice #{}'.format(self.id,self.invoice_reference)

    # Properties
    # ==================
    @property
    def active(self):
        try:
            invoice = Invoice.objects.get(reference=self.invoice_reference)
            return False if invoice.voided else True
        except Invoice.DoesNotExist:
            pass
        return False



class Booking(SanitisationModelMixin, models.Model):
    sanitise_exclude_fields = set()
    BOOKING_TYPE_CHOICES = (
        (0, 'Reception booking'),
        (1, 'Internet booking'),
        (2, 'Black booking'),
        (3, 'Temporary reservation'),
        (4, 'Cancelled Booking'),
        (5, 'Changed Booking')
    )

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)
    legacy_id = models.IntegerField(unique=True, blank=True, null=True)
    legacy_name = models.CharField(max_length=255, blank=True,null=True)
    arrival = models.DateField()
    departure = models.DateField()
    details = django_models.JSONField(null=True, blank=True)
    booking_type = models.SmallIntegerField(choices=BOOKING_TYPE_CHOICES, default=0)
    expiry_time = models.DateTimeField(blank=True, null=True)
    cost_total = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    override_price = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    override_reason = models.ForeignKey('DiscountReason', null=True, blank=True, on_delete=models.SET_NULL)
    override_reason_info = models.TextField(blank=True, null=True)
    overridden_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, blank=True, null=True, related_name='overridden_bookings')
    mooringarea = models.ForeignKey('MooringArea', null=True, on_delete=models.SET_NULL, verbose_name="mooring")
    is_canceled = models.BooleanField(default=False)  # This might not be used...???  Instead, BOOKING_TYPE_CHOICES[4] might be used
    send_invoice = models.BooleanField(default=False)
    cancellation_reason = models.TextField(null=True,blank=True)
    cancelation_time = models.DateTimeField(null=True,blank=True)
    confirmation_sent = models.BooleanField(default=False)
    updated = models.DateTimeField(default=timezone.now)
    created = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, blank=True, null=True,related_name='created_by_booking')
    canceled_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, blank=True, null=True,related_name='canceled_bookings')
    old_booking = models.ForeignKey('Booking', null=True, blank=True, on_delete=models.SET_NULL)
    admission_payment = models.ForeignKey('AdmissionsBooking', null=True, blank=True, on_delete=models.SET_NULL)
    override_lines = django_models.JSONField(null=True, blank=True, default=dict)
    property_cache = django_models.JSONField(null=True, blank=True, default=dict)
    property_cache_version = models.CharField(max_length=10, blank=True, null=True)
    property_cache_stale = models.BooleanField(default=True)
    # UUID for stateless payment flow (external public URLs)
    # Note: unique constraint will be added in a separate migration after data backfill
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, null=False, unique=True, db_index=True)


    def save(self, *args,**kwargs):
        self.updated = timezone.now()
        self.property_cache_stale = True
        if 'cache_updated' in kwargs:
            if kwargs['cache_updated'] is True:
                self.property_cache_stale = False
                del kwargs['cache_updated']
        super(Booking,self).save(*args,**kwargs)

    #def save(self, *args,**kwargs):
    #    self.update_property_cache(False)
    #    super(Booking,self).save(*args,**kwargs)

    def get_property_cache(self):
        if len(self.property_cache) == 0:
            self.update_property_cache()
        return self.property_cache

    def update_property_cache(self, save=True):
        self.property_cache['cache_version'] = settings.BOOKING_PROPERTY_CACHE_VERSION
        self.property_cache['amount_paid'] = str(self.amount_paid)
        self.property_cache['refund_status'] = self.refund_status
        self.property_cache['outstanding'] = str(self.outstanding)
        self.property_cache['status'] = self.status
        self.property_cache['invoice_status'] = self.invoice_status
        self.property_cache['has_history'] = self.has_history
        self.property_cache['vehicle_payment_status'] = self.vehicle_payment_status
        self.property_cache['cancellation_reason'] = self.cancellation_reason
        self.property_cache['paid'] = self.paid
        self.property_cache['invoices'] = [i.invoice_reference for i in self.invoices.all()]
        self.property_cache['active_invoices'] = [i.invoice_reference for i in self.invoices.all() if i.active]
        self.property_cache_stale = False
        if self.customer:
            if self.customer.id:
                self.property_cache['customer_id'] = self.customer.id
            if self.customer.phone_number:
                self.property_cache['customer_phone_number'] = self.customer.phone_number
            if self.customer.mobile_number:
                self.property_cache['customer_mobile_number'] = self.customer.mobile_number
            if self.customer.email:
                self.property_cache['customer_email'] = self.customer.email
        if self.canceled_by:
            if self.canceled_by.first_name:
                self.property_cache['canceled_by_first_name'] = self.canceled_by.first_name
            if self.canceled_by.last_name:
                self.property_cache['canceled_by_last_name'] = self.canceled_by.last_name

        self.property_cache_version = settings.BOOKING_PROPERTY_CACHE_VERSION
        if save is True:
           self.save()
        return self.property_cache

    # Properties
    # =================================
    @property
    def num_days(self):
        return (self.departure-self.arrival).days

    @property
    def stay_dates(self):
        count = self.num_days
        return '{} to {} ({} day{})'.format(self.arrival.strftime('%d/%m/%Y'), self.departure.strftime('%d/%m/%Y'), count, '' if count == 1 else 's')

    @property
    def stay_guests(self):
        num_adult = self.details.get('num_adult', 0)
        num_concession = self.details.get('num_concession', 0)
        num_infant = self.details.get('num_infant', 0)
        num_child = self.details.get('num_child', 0)
        num_mooring = self.details.get('num_mooring', 0)
        return '{} adult{}, {} concession{}, {} child{}, {} infant{}, {} mooring{}'.format(
            num_adult, '' if num_adult == 1 else 's',
            num_concession, '' if num_concession == 1 else 's',
            num_child, '' if num_child == 1 else 'ren',
            num_infant, '' if num_infant == 1 else 's',
            num_mooring, '' if num_mooring == 1 else 's',
        )

    @property
    def num_guests(self):
        if self.details:
            num_adult = self.details.get('num_adult', 0)
            num_concession = self.details.get('num_concession', 0)
            num_infant = self.details.get('num_infant', 0)
            num_child = self.details.get('num_child', 0)
            num_mooring = self.details.get('num_mooring', 0)
            return num_adult + num_concession + num_infant + num_child + num_mooring
        return 0

    @property
    def guests(self):
        if self.details:
            num_adult = self.details.get('num_adult', 0)
            num_concession = self.details.get('num_concession', 0)
            num_infant = self.details.get('num_infant', 0)
            num_child = self.details.get('num_child', 0)
            num_mooring = self.details.get('num_mooring', 0)
            return {
                "adults" : num_adult,
                "concession" : num_concession,
                "infants" : num_infant,
                "children": num_child,
                "mooring" : num_mooring
            }
        return {
            "adults" : 0,
            "concession" : 0,
            "infants" : 0,
            "children": 0,
            "mooring" : 0,
        }

    @property
    def first_campsite(self):
        cb = self.campsites.all().first()
        return cb.campsite if cb else None

    @property
    def editable(self):
        today = datetime.now().date()
        if today <= self.departure:
            if not self.is_canceled:
                return True
        return True

    @property
    def campsite_id_list(self):
        return list(set([x['campsite'] for x in self.campsites.all().values('campsite')]))

    @property
    def campsite_name_list(self):
        return list(set(self.campsites.values_list('campsite__name', flat=True)))

    @property
    def paid(self):
        if self.legacy_id and self.invoices.count() < 1:
            return True
        else:
            payment_status = self.__check_payment_status()
            if payment_status == 'paid' or payment_status == 'over_paid':
                return True
        return False

    @property
    def unpaid(self):
        if self.legacy_id and self.invoices.count() < 1:
            return False
        else:
            payment_status = self.__check_payment_status()
            if payment_status == 'unpaid':
                return True
        return False

    @property
    def amount_paid(self):
        return self.__check_payment_amount()

    @property
    def refund_status(self):
        return self.__check_refund_status()

    @property
    def outstanding(self):
        return self.__outstanding_amount()

    @property
    def status(self):
        if (self.legacy_id and self.invoices.count() >= 1) or not self.legacy_id:
            payment_status = self.__check_payment_status()
            status =  ''
            parts = payment_status.split('_')
            for p in parts:
                status += '{} '.format(p.title())
            status = status.strip()
            if self.is_canceled:
                if payment_status == 'over_paid' or payment_status == 'paid':
                    return 'Cancelled - Payment ({})'.format(status)
                else:
                    return 'Cancelled'
            else:
                return status
        return 'Paid'
    @property
    def invoice_status(self):
        return self.__check_invoice_payment_status()

    @property
    def confirmation_number(self):
        return 'PS{}'.format(self.pk)

    @property
    def active_invoice(self):
        active_invoices = Invoice.objects.filter(reference__in=[x.invoice_reference for x in self.invoices.all()]).order_by('-created')
        return active_invoices[0] if active_invoices else None

    @property
    def has_history(self):
        return self.history.count() > 0

    @property
    def in_future(self):
        return self.departure > date.today()

    # Methods
    # =================================
    def clean(self,*args,**kwargs):
        #Check for existing bookings in current date range
        arrival = self.arrival
        departure = self.departure
        customer = self.customer

        other_bookings = Booking.objects.filter(Q(departure__gt=arrival,departure__lte=departure) | Q(arrival__gte=arrival,arrival__lt=departure),customer=customer)
        if self.pk:
            other_bookings.exclude(id=self.pk)
        #if customer and other_bookings and (self.booking_type != 3 or self.booking_type != 4):
        #    raise ValidationError('You cannot make concurrent bookings.')
        #if not self.mooringarea.oracle_code:
        #    raise ValidationError('Campground does not have an Oracle code.')
        if self.mooringarea.park.entry_fee_required and not self.mooringarea.park.oracle_code:
            raise ValidationError('MarinePark does not have an Oracle code.')
        super(Booking,self).clean(*args,**kwargs)

    def __str__(self):
        return '{}: {} - {}'.format(self.customer, self.arrival, self.departure)

    def __check_payment_amount(self):
        invoices = []
        amount = D('0.0')
        references = [i.invoice_reference for i in self.invoices.all()]
        #invoices = Invoice.objects.filter(reference__in=references,voided=False)
        if self.active_invoice:
            amount = self.active_invoice.payment_amount
        elif self.legacy_id:
            amount =  D(self.cost_total)
        return amount

    def __check_invoice_payment_status(self):
        invoices = []
        payment_amount = D('0.0')
        invoice_amount = D('0.0')
        references = self.invoices.all().values('invoice_reference')
        for r in references:
            try:
                invoices.append(Invoice.objects.get(reference=r.get("invoice_reference")))
            except Invoice.DoesNotExist:
                pass
        for i in invoices:
            if not i.voided:
                payment_amount += i.payment_amount
                invoice_amount += i.amount

        if invoice_amount == payment_amount:
            return 'paid'
        if payment_amount > invoice_amount:
            return 'over_paid'
        return "unpaid"

    def __check_payment_status(self):
        invoices = []
        amount = D('0.0')
        references = self.invoices.all().values('invoice_reference')
        for r in references:
            try:
                invoices.append(Invoice.objects.get(reference=r.get("invoice_reference")))
            except Invoice.DoesNotExist:
                pass
        for i in invoices:
            if not i.voided:
                amount += i.payment_amount

        if amount == 0:
            return 'unpaid'
        if self.cost_total < amount:
            return 'over_paid'
        elif self.cost_total > amount:
            return 'partially_paid'
        else:return "paid"

    def __check_refund_status(self):
        invoices = []
        amount = D('0.0')
        refund_amount = D('0.0')
        references = self.invoices.all().values_list('invoice_reference', flat=True)
        invoices = Invoice.objects.filter(reference__in=references)
        for i in invoices:
            if i.voided:
                amount += i.total_payment_amount
                refund_amount += i.refund_amount

        if amount == 0:
            return 'Not Paid'
        if refund_amount > 0 and amount > refund_amount:
            return 'Partially Refunded'
        elif refund_amount == amount:
            return 'Refunded'
        else:return "Not Refunded"

    def __outstanding_amount(self):
        invoices = []
        amount = D('0.0')
        references = self.invoices.all().values('invoice_reference')
        for r in references:
            try:
                invoices.append(Invoice.objects.get(reference=r.get("invoice_reference")))
            except Invoice.DoesNotExist:
                pass
        for i in invoices:
            if not i.voided:
                amount += i.balance

        return amount

    def cancelBooking(self,reason,user=None):
        if not reason:
            raise ValidationError('A reason is needed before canceling a booking')
        today = datetime.now().date()
        if today > self.departure:
            raise ValidationError('You cannot cancel a booking past the departure date.')
        self._generate_history(user=user)
        if user:
            self.canceled_by = user
        self.cancellation_reason = reason
        self.is_canceled = True
        self.cancelation_time = timezone.now()
        self.campsites.all().delete()
        references = self.invoices.all().values('invoice_reference')
        for r in references:
            try:
                i = Invoice.objects.get(reference=r.get("invoice_reference"))
                i.voided = True
                i.save()
            except Invoice.DoesNotExist:
                pass

        self.save()

    def _generate_history(self,user=None):
        campsites = list(set([x.campsite.name for x in self.campsites.all()]))
        vessels = [{'rego':x.rego,'type':x.type,'entry_fee':x.entry_fee,'park_entry_fee':x.park_entry_fee} for x in self.regos.all()]
        BookingHistory.objects.create(
            booking = self,
            updated_by=user,
            arrival = self.arrival,
            departure = self.departure,
            details = self.details,
            cost_total = self.cost_total,
            confirmation_sent = self.confirmation_sent,
            campground = self.mooringarea.name,
            campsites = campsites,
            vessels = vessels,
            invoice=self.active_invoice
        )
    
    @property
    def vehicle_payment_status(self):
        # Get current invoice
        inv  = None
        payment_dict = []
        references = [i.invoice_reference for i in self.invoices.all()]
        #temp_invoices = Invoice.objects.filter(reference__in=references,voided=False)
        temp_invoices = [self.active_invoice] if self.active_invoice else []
        if len(temp_invoices) == 1 or self.legacy_id:
            if not self.legacy_id:
                inv = temp_invoices[0]
            # Get all lines 
            total_paid = D('0.0')
            total_due = D('0.0')
            lines = []
            if not self.legacy_id:
                lines = ledger_api_utils.OrderLine.objects.filter(number=inv.order_number, oracle_code=self.mooringarea.park.oracle_code)

            price_dict = {}
            for line in lines:
                total_paid += line.paid
                total_due += line.unit_price_incl_tax * line.quantity
                price_dict[line.oracle_code] = line.unit_price_incl_tax

            remainder_amount = total_due - total_paid
            # Allocate amounts to each vehicle
            for r in self.regos.all():
                paid = False
                show_paid = True
                if self.legacy_id:
                    paid = False
                elif not r.park_entry_fee:
                    show_paid = False
                    paid = True
                elif remainder_amount == 0:
                    paid = True
                elif total_paid == 0:
                    pass
                else:
                    required_total = D('0.0')
                    for k,v in price_dict.items():
                        required_total += D(v)
                    if required_total <= total_paid:
                        total_paid -= required_total
                        paid = True
                data = {
                    'Rego': r.rego.upper(),
                    'Type': r.get_type_display(),
                    'original_type': r.type,
                    'Fee': r.entry_fee,
                }
                if show_paid:
                    data['Paid'] = 'pass_required' if not r.entry_fee and not self.legacy_id else 'Yes' if paid else 'No'
                payment_dict.append(data)
        else:
            pass
        return payment_dict

    def _get_success_context(self, invoice_reference=None):
        """
        Build context dictionary for success page/notifications.
        Used by process_payment_notification to return consistent data.
        """
        from mooring.models import BookingInvoice, RefundFailed
        
        book_inv = None
        if invoice_reference:
            book_inv = BookingInvoice.objects.filter(
                booking=self, 
                invoice_reference=invoice_reference
            ).first()
        
        refund_failed = None
        if RefundFailed.objects.filter(booking=self).count() > 0:
            refund_failed = RefundFailed.objects.filter(booking=self)
        
        return {
            'booking': self,
            'book_inv': [book_inv] if book_inv else [],
            'refund_failed': refund_failed
        }

    @transaction.atomic
    def process_payment_notification(self, invoice_reference):
        """
        Process payment notification from Ledger (idempotent).
        
        This method handles payment confirmation for a booking, whether called
        from the user-facing success view or from a background notification endpoint.
        It's designed to be idempotent - safe to call multiple times with the same
        invoice_reference.
        
        Args:
            invoice_reference (str): Invoice reference from Ledger payment system
            
        Returns:
            dict: Context dictionary with booking data for email/display
            
        Raises:
            ValueError: If invoice validation fails
            Invoice.DoesNotExist: If invoice not found in Ledger
        """
        from mooring.models import (
            BookingInvoice, MooringsiteBooking, AdmissionsBooking, 
            AdmissionsBookingInvoice, AdmissionsLine, VesselDetail
        )
        from mooring import emails
        
        logger.info(f'Processing payment notification for booking {self.id}, invoice {invoice_reference}')
        
        if not invoice_reference:
            logger.error(f'Missing invoice_reference for booking {self.id}')
            raise ValueError(f'Missing invoice_reference for booking {self.id}')
        
        # Lock booking row to prevent race conditions
        booking = Booking.objects.select_for_update().get(id=self.id)
        
        # Idempotency check - if already processed, return current state
        if booking.booking_type == 1:
            logger.info(f'Booking {booking.id} already processed (booking_type=1), returning current state')
            return booking._get_success_context(invoice_reference)
        
        # Validate invoice exists and belongs to this booking
        try:
            inv = Invoice.objects.get(reference=invoice_reference)
        except Invoice.DoesNotExist:
            logger.error(f'{booking.customer.get_full_name() if booking.customer else "Anonymous user"} '
                        f'tried making a booking with an incorrect invoice {invoice_reference}')
            raise
        
        # Verify invoice is from correct payment system
        if inv.system not in ['0516']:
            logger.error(f'{booking.customer.get_full_name() if booking.customer else "Anonymous user"} '
                        f'tried making a booking with an invoice from another system: {inv.system}, '
                        f'invoice reference: {inv.reference}')
            raise ValueError(f'Invoice {invoice_reference} is from wrong system: {inv.system}')
        
        # Fetch the corresponding Order
        try:
            order = Order.objects.get(number=inv.order_number)
        except Order.DoesNotExist:
            logger.error(f'Order {inv.order_number} not found for invoice {invoice_reference}')
            raise ValueError(f'Order not found for invoice {invoice_reference}')
        
        # Verify that the invoice has been paid in full or overpaid
        if inv.payment_amount < inv.amount:
            logger.error(f'Invoice {invoice_reference} for booking {booking.id} is not fully paid (amount: {inv.amount}, paid: {inv.payment_amount})')
            raise ValueError(f'Invoice {invoice_reference} is not fully paid')
        
        # Verify order belongs to the booking's customer
        if not booking.customer:
            logger.error(f'Booking {booking.id} has no customer')
            raise ValueError(f'Booking {booking.id} has no customer')
        
        if order.user_id != booking.customer.id:
            logger.error(f'Order {order.number} user_id {order.user_id} does not match booking {booking.id} customer {booking.customer.id}')
            raise ValueError(f'Invoice ownership validation failed - user mismatch for booking {booking.id}')
        
        # Verify a basket exists for this booking with correct status
        booking_reference = settings.MOORING_BOOKING_REF_PREFIX + str(booking.id)
        basket = Basket.objects.filter(
            status='Submitted',
            system=settings.PAYMENT_SYSTEM_ID,
            booking_reference=booking_reference
        ).order_by('-id')
        
        if not basket.exists():
            logger.error(f'No submitted basket found for booking {booking.id} with reference {booking_reference}')
            raise ValueError(f'No submitted basket found for booking {booking.id}')
        
        logger.info(f'Verified invoice {invoice_reference} belongs to booking {booking.id} via user_id {order.user_id} and basket verification')
        
        # Create/get BookingInvoice linking record
        book_inv, created = BookingInvoice.objects.get_or_create(
            booking=booking, 
            invoice_reference=invoice_reference
        )
        
        if created:
            logger.info(f'Created BookingInvoice for booking {booking.id}, invoice {invoice_reference}')
        else:
            logger.info(f'BookingInvoice already exists for booking {booking.id}, invoice {invoice_reference}')
        
        # Handle old_booking cancellation (for booking changes)
        if booking.old_booking:
            logger.info(f'Cancelling old booking {booking.old_booking.id} for booking change')
            old_booking = Booking.objects.get(id=booking.old_booking.id)
            old_booking.booking_type = 4  # Cancelled Booking
            old_booking.cancelation_time = datetime.now()
            old_booking.canceled_by = booking.created_by
            old_booking.save()
            
            # Cancel old booking's mooringsite bookings
            booking_items = MooringsiteBooking.objects.filter(booking=old_booking)
            for bi in booking_items:
                bi.booking_type = 4
                bi.save()
            
            # Cancel old booking's admission payment if exists
            if old_booking.admission_payment:
                old_booking.admission_payment.booking_type = 4
                old_booking.admission_payment.cancelation_time = datetime.now()
                old_booking.admission_payment.canceled_by = booking.created_by
                old_booking.admission_payment.save()
        
        # Apply override_lines amounts to booking items
        booking_items_current = MooringsiteBooking.objects.filter(booking=booking)
        for bi in booking_items_current:
            if str(bi.id) in booking.override_lines:
                bi.amount = D(booking.override_lines[str(bi.id)])
            bi.save()
        
        # Update arrival and departure dates from mooringsite bookings
        msb = MooringsiteBooking.objects.filter(booking=booking).order_by('from_dt')
        if msb.exists():
            from_date = msb[0].from_dt
            to_date = msb[msb.count()-1].to_dt
            
            # Convert timezone-aware datetime to date
            timestamp = calendar.timegm(from_date.timetuple())
            local_dt = datetime.fromtimestamp(timestamp)
            from_dt = local_dt.replace(microsecond=from_date.microsecond)
            from_date_converted = from_dt.date()
            
            timestamp = calendar.timegm(to_date.timetuple())
            local_dt = datetime.fromtimestamp(timestamp)
            to_dt = local_dt.replace(microsecond=to_date.microsecond)
            to_date_converted = to_dt.date()
            
            booking.arrival = from_date_converted
            booking.departure = to_date_converted
        
        # Update booking state - set to confirmed
        booking.booking_type = 1  # Internet booking (confirmed)
        booking.expiry_time = None
        
        # Update payments via ledger
        try:
            update_payments()
            logger.info(f'Updated payments for invoice {invoice_reference}')
        except Exception as e:
            logger.warning(f'Error updating payments for invoice {invoice_reference}: {e}')
            # Don't fail the whole transaction for payment update errors
        
        # Handle admission payment if exists
        if booking.admission_payment:
            logger.info(f'Processing admission payment {booking.admission_payment.id}')
            ad_booking = AdmissionsBooking.objects.get(pk=booking.admission_payment.pk)
            ad_booking.created_by = booking.created_by
            ad_booking.booking_type = 1
            ad_booking.save()
            
            # Create admission invoice record
            ad_invoice, created = AdmissionsBookingInvoice.objects.get_or_create(
                admissions_booking=ad_booking, 
                invoice_reference=invoice_reference
            )
            
            # Apply admission override lines
            for al in ad_booking.override_lines.keys():
                ad_line = AdmissionsLine.objects.get(id=int(al))
                ad_line.cost = ad_booking.override_lines[str(al)]
                ad_line.save()
        
        # Update/create VesselDetail records from booking.details
        if booking.details and 'vessel_rego' in booking.details:
            try:
                vessel_rego = booking.details['vessel_rego']
                if VesselDetail.objects.filter(rego_no=vessel_rego).exists():
                    # Update existing vessel
                    vd = VesselDetail.objects.filter(rego_no=vessel_rego).first()
                    vd.vessel_size = booking.details.get('vessel_size', vd.vessel_size)
                    vd.vessel_draft = booking.details.get('vessel_draft', vd.vessel_draft)
                    vd.vessel_beam = booking.details.get('vessel_beam', vd.vessel_beam)
                    vd.vessel_weight = booking.details.get('vessel_weight', vd.vessel_weight)
                    vd.save()
                    logger.info(f'Updated VesselDetail for rego {vessel_rego}')
                else:
                    # Create new vessel
                    VesselDetail.objects.create(
                        rego_no=vessel_rego,
                        vessel_size=booking.details.get('vessel_size', D('0.00')),
                        vessel_draft=booking.details.get('vessel_draft', D('0.00')),
                        vessel_beam=booking.details.get('vessel_beam', D('0.00')),
                        vessel_weight=booking.details.get('vessel_weight', D('0.00'))
                    )
                    logger.info(f'Created VesselDetail for rego {vessel_rego}')
            except Exception as e:
                logger.error(f'Error creating/updating VesselDetail for booking {booking.id}: {e}')
                # Don't fail the whole transaction for vessel detail errors
        
        # Save booking
        booking.save()
        logger.info(f'Successfully processed payment notification for booking {booking.id}')
        
        # Return context dict for email/display
        return booking._get_success_context(invoice_reference)
    
    def send_payment_emails(self, request_or_context):
        """
        Send payment confirmation and invoice emails.
        
        This method can be called from either:
        1. Success views with HttpRequest (sync flow after payment redirect)
        2. API notification endpoints with context dict (async background callback)
        
        Args:
            request_or_context: Either HttpRequest object or dict containing context data
        
        Raises:
            No exceptions - email errors are logged but don't fail the transaction
        """
        from mooring import emails
        from mooring.context_processors import template_context, mooring_url_group
        
        try:
            # Determine if input is HttpRequest or dict context
            if isinstance(request_or_context, HttpRequest):
                # Sync flow - extract context from request
                context_processor = template_context(request_or_context)
                logger.info(f'Sending payment emails for booking {self.id} (sync flow with HttpRequest)')
            else:
                # Async flow - use provided context dict and ensure required template variables
                context_processor = request_or_context.copy() if isinstance(request_or_context, dict) else {}
                
                # Add default template group and other required context variables if not present
                if 'TEMPLATE_GROUP' not in context_processor:
                    # Default to 'pvs' template group
                    default_context = mooring_url_group('pvs')
                    context_processor.update(default_context)
                    logger.info(f'Added default template context for booking {self.id} (TEMPLATE_GROUP: {default_context.get("TEMPLATE_GROUP")})')
                
                logger.info(f'Sending payment emails for booking {self.id} (async flow with context dict)')
            
            # Send invoice email
            try:
                emails.send_booking_invoice(self, context_processor)
                logger.info(f'Successfully sent invoice email for booking {self.id}')
            except Exception as e:
                logger.error(f'Error sending invoice email for booking {self.id}: {e}', exc_info=True)
            
            # Send confirmation email
            try:
                emails.send_booking_confirmation(self, context_processor)
                logger.info(f'Successfully sent confirmation email for booking {self.id}')
            except Exception as e:
                logger.error(f'Error sending confirmation email for booking {self.id}: {e}', exc_info=True)
                
        except Exception as e:
            # Catch-all for any unexpected errors - log but don't fail
            logger.error(f'Unexpected error sending payment emails for booking {self.id}: {e}', exc_info=True)

class BookingHistory(models.Model):
    booking = models.ForeignKey(Booking, related_name='history', null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    arrival = models.DateField()
    departure = models.DateField()
    details = django_models.JSONField()
    cost_total = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    confirmation_sent = models.BooleanField()
    campground = models.CharField(max_length=100)
    campsites = django_models.JSONField()
    vessels = django_models.JSONField()
    updated_by = models.ForeignKey(EmailUser,on_delete=models.PROTECT, blank=True, null=True)
    invoice=models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL)

class OutstandingBookingRecipient(models.Model):
    email = models.EmailField()

    def __str__(self):
        return self.email


class BookingInvoice(models.Model):
    booking = models.ForeignKey(Booking, related_name='invoices', on_delete=models.CASCADE)
    invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    system_invoice = models.BooleanField(default=False)
 
    def __str__(self):
        return 'Booking {} : Invoice #{}'.format(self.id,self.invoice_reference)

    def save(self, *args,**kwargs):
        super(BookingInvoice,self).save(*args,**kwargs)
        print ("COMPLETED POST CREATE")
        self.booking.save()
        #self.booking.update_property_cache()



    # Properties
    # ==================
    @property
    def active(self):
        try:
            invoice = Invoice.objects.get(reference=self.invoice_reference)
            return False if invoice.voided else True
        except Invoice.DoesNotExist:
            pass
        return False

class BookingVehicleRego(models.Model):
    """docstring for BookingVehicleRego."""
    VEHICLE_CHOICES = (
#        ('vehicle','Vehicle'),
        ('vessel','Vessel'),
#        ('motorbike','Motorcycle'),
#        ('concession','Vehicle (concession)')
    )

    booking = models.ForeignKey(Booking, related_name = "regos", on_delete=models.CASCADE)
    rego = models.CharField(max_length=50)
    type = models.CharField(max_length=10,choices=VEHICLE_CHOICES)
    entry_fee = models.BooleanField(default=False)
    park_entry_fee = models.BooleanField(default=False)

    class Meta:
        unique_together = ('booking','rego')

class MarinaEntryRate(models.Model):

    vehicle = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    concession = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    motorbike = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    period_start = models.DateField()
    period_end = models.DateField(null=True,blank=True)
    reason = models.ForeignKey("PriceReason",on_delete=models.PROTECT)
    details = models.TextField(null = True, blank= True)

    def clean(self,*args,**kwargs):
        if self.reason.id == 1 and not self.details:
            raise ValidationError("Details cannot be empty if reason is Other")
        super(MarinaEntryRate,self).clean(*args,**kwargs)

    def save(self, *args,**kwargs):
        self.full_clean()
        super(MarinaEntryRate,self).save(*args,**kwargs)

    @property
    def editable(self):
        today = datetime.now().date()
        return (self.period_start > today and not self.period_end) or ( self.period_start > today <= self.period_end)


class VesselDetail(models.Model):
    rego_no = models.CharField(max_length=200)
    vessel_name = models.CharField(max_length=400) 
    vessel_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name_plural = "Vessel Details"

    def __str__(self):
        return self.rego_no


class RegisteredVesselsMooringLicensing(models.Model):
    rego_no = models.CharField(max_length=200)
    vessel_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    updated = models.DateTimeField(default=timezone.now, editable=False)
    created = models.DateTimeField(default=timezone.now, editable=False)

    def save(self, *args,**kwargs):
        self.updated = timezone.now()
        UpdateLog.objects.create(model_name='RegisteredVesselsMooringLicensing', json_context={'rego_no':self.rego_no,'vessel_size': self.vessel_size, 'vessel_draft': self.vessel_draft, 'vessel_beam': self.vessel_beam, 'vessel_weight':self.vessel_weight,})
        super(RegisteredVesselsMooringLicensing,self).save(*args,**kwargs)

    class Meta:
        verbose_name = "Registered Vessel (Mooring Licensing)"
        verbose_name_plural = "Registered Vessels (Mooring Licensing)"

class RegisteredVessels(models.Model):
    rego_no = models.CharField(max_length=200, unique=True)
    vessel_size = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_draft = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_beam = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    vessel_weight = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    sticker_l = models.IntegerField(default=None, blank=True, null=True)
    sticker_au = models.IntegerField(default=None, blank=True, null=True)
    sticker_an = models.IntegerField(default=None, blank=True, null=True)
    expiry_l = models.DateField(null=True, blank=True)
    expiry_au = models.DateField(null=True, blank=True)
    expiry_an = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Registered Vessel (Lotus)"
        verbose_name_plural = "Registered Vessels (Lotus)"

    @property
    def admissionsPaid(self):
        sticker_l = self.sticker_l
        sticker_au = self.sticker_au
        sticker_an = self.sticker_an
        if sticker_l is None:
            sticker_l = 0
        if sticker_au is None:
             sticker_au = 0
        if sticker_an is None:
            sticker_an = 0

        if sticker_l > 0 or sticker_au > 0 or sticker_an > 0:
            return True
        else:
            return False


# REASON MODELS
# =====================================
class Reason(models.Model):
    text = models.TextField()
    detailRequired = models.BooleanField(default=False)
    editable = models.BooleanField(default=True,editable=False)
    mooring_group = models.ForeignKey(MooringAreaGroup, blank=True, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ('id',)
        abstract = True

    def save(self, *args, **kwargs):
        if self.mooring_group == None:
            raise ValidationError("Mooring Group required, please select from list.")
        else:
            super(Reason,self).save(*args,**kwargs)

    # Properties
    # ==============================
    def code(self):
        return self.__get_code()

    # Methods
    # ==============================
    def __get_code(self):
        length = len(str(self.id))
        val = '0'
        return '{}{}'.format((val*(4-length)),self.id)

class MaximumStayReason(Reason):
    pass

class ClosureReason(Reason):
    pass

class OpenReason(Reason):
    pass

class PriceReason(Reason):
    pass
class AdmissionsReason(Reason):
    pass
class DiscountReason(Reason):
    pass


# VIEWS
# =====================================
class ViewPriceHistory(models.Model):

    # Created because id was used as a primary_key to a foriegn model link as such need to create unique row id..
    id = models.IntegerField(primary_key=True)
    date_start = models.DateField()
    date_end = models.DateField()
    rate_id = models.IntegerField()
    booking_period_id = models.IntegerField()
    mooring = models.DecimalField(max_digits=8, decimal_places=2)
    adult = models.DecimalField(max_digits=8, decimal_places=2)
    concession = models.DecimalField(max_digits=8, decimal_places=2)
    child = models.DecimalField(max_digits=8, decimal_places=2)
    details = models.TextField()
    reason_id = models.IntegerField()
    infant = models.DecimalField(max_digits=8, decimal_places=2)
    price_id = models.IntegerField()

    class Meta:
        abstract =True

    # Properties
    # ====================================

    @property
    def deletable(self):
        today = datetime.now().date()
        if self.date_start >= today:
            return True
        return False

    @property
    def editable(self):
        today = datetime.now().date()
        #if (self.date_start > today and not self.date_end) or ( self.date_start > today <= self.date_end):
        if self.date_end is None:
             return True
        elif self.date_end > today:
            return True
        return False

    @property
    def reason(self):
        reason = ''
        if self.reason_id:
            reason = self.reason_id
        return reason

class MooringAreaPriceHistory(ViewPriceHistory):
    class Meta:
        managed = False
        db_table = 'mooring_mooringarea_pricehistory_v'
        ordering = ['-date_start',]

class MooringsiteClassPriceHistory(ViewPriceHistory):
    class Meta:
        managed = False
        db_table = 'mooring_mooringsiteclass_pricehistory_v'
        ordering = ['-date_start',]

class AdmissionsLocation(models.Model):
    key = models.CharField(max_length=5, blank=False, null=False, unique=True)
    text = models.CharField(max_length=255, blank=False, null=False)
    mooring_group = models.ForeignKey(MooringAreaGroup, blank=False, null=False, on_delete=models.CASCADE)
    annual_admissions_terms = models.CharField(max_length=1024, blank=False, null=False, default ='')
    annual_admissions_more_price_info_url = models.CharField(max_length=1024, blank=False, null=False, default ='')
    daily_admissions_terms = models.CharField(max_length=1024, blank=False, null=False, default ='')
    daily_admissions_more_price_info_url = models.CharField(max_length=1024, blank=False, null=False, default ='')
    mooring_booking_terms = models.CharField(max_length=1024, blank=False, null=False, default ='')

    def save(self,*args,**kwargs):
        cache.delete('AdmissionsLocation:'+self.key)
        super(AdmissionsLocation,self).save(*args,**kwargs)


    def __str__(self):
        return self.text

class AdmissionsBooking(SanitisationModelMixin, models.Model):
    sanitise_exclude_fields = set()
    BOOKING_TYPE_CHOICES = (
        (0, 'Reception booking'),
        (1, 'Internet booking'),
        (2, 'Black booking'),
        (3, 'In-complete booking'),
        (4, 'Cancelled booking')
    )
    # customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True)
    customer_id = models.IntegerField(blank=True, null=True)
    booking_type = models.SmallIntegerField(choices=BOOKING_TYPE_CHOICES, default=0)
    vesselRegNo = models.CharField(max_length=200, blank=True )
    noOfAdults = models.IntegerField()
    noOfConcessions = models.IntegerField()
    noOfChildren = models.IntegerField()
    noOfInfants = models.IntegerField()
    warningReferenceNo = models.CharField(max_length=200, blank=True)
    totalCost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    # created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, blank=True, null=True,related_name='created_by_admissions')
    created_by_id = models.IntegerField(blank=True, null=True)
    # canceled_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT, blank=True, null=True,related_name='canceled_bookings_admissions')
    canceled_by_id = models.IntegerField(blank=True, null=True)
    cancelation_time = models.DateTimeField(null=True,blank=True)
    cancellation_reason = models.TextField(null=True,blank=True)
    created = models.DateTimeField(default=timezone.now)
    location = models.ForeignKey(AdmissionsLocation, blank=True, null=True, on_delete=models.SET_NULL)    
    override_lines = django_models.JSONField(null=True, blank=True, default=dict)
    mobile = models.CharField(max_length=50, blank=True, null=True)
    # UUID for stateless payment flow (public notification and success URLs)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, null=False, unique=True, db_index=True)

    def __str__(self):
        email = ''
        if self.customer:
            email = self.customer.email
        return 'AD{} : {}'.format(self.id, email)

    @property
    def customer(self):
        if self.customer_id:
            return EmailUser.objects.get(id=self.customer_id)
        return None

    @customer.setter
    def customer(self, value):
        if value is None:
            self.customer_id = None
        else:
            self.customer_id = value.id

    @property
    def confirmation_number(self):
        return 'AD{}'.format(self.id)

    @property
    def total_admissions(self):
        return self.noOfAdults + self.noOfConcessions + self.noOfChildren + self.noOfInfants

    @property
    def in_future(self):
        lines = AdmissionsLine.objects.filter(admissionsBooking=self)
        future = False
        for line in lines:
            if line.arrivalDate > date.today():
                future = True
                break
        return future

    @property
    def part_booking(self):
        res = Booking.objects.filter(admission_payment=self).count()
        if res == 0:
            return False
        else:
            return True

    @property
    def admissions_line(self):
        lines = AdmissionsLine.objects.filter(admissionsBooking=self)
        return lines

    @property
    def active_invoice(self):
        active_invoices = Invoice.objects.filter(reference__in=[x.invoice_reference for x in self.invoices.all()]).order_by('-created')
        return active_invoices[0] if active_invoices else None

    def _get_success_context(self, invoice_reference=None):
        """
        Build context dictionary for success page/notifications.
        Used by process_payment_notification to return consistent data.
        """
        from mooring.models import AdmissionsLine, AdmissionsBookingInvoice
        
        # Get arrival date and overnight status from first AdmissionsLine
        arrival = None
        overnight = False
        admissions_lines = AdmissionsLine.objects.filter(admissionsBooking=self)
        if admissions_lines.exists():
            arrival = admissions_lines[0].arrivalDate
            overnight = admissions_lines[0].overnightStay
        
        # Get invoice objects (not just reference strings)
        invoice_objs = []
        if invoice_reference:
            # Try to get the specific invoice object
            invoice_obj = AdmissionsBookingInvoice.objects.filter(
                admissions_booking=self, 
                invoice_reference=invoice_reference
            ).first()
            if invoice_obj:
                invoice_objs = [invoice_obj]
        
        # Fallback: get all invoices for this booking if none found
        if not invoice_objs:
            invoice_objs = list(AdmissionsBookingInvoice.objects.filter(admissions_booking=self).order_by('-id'))
        
        return {
            'admissionsBooking': self,
            'arrival': arrival,
            'overnight': overnight,
            'admissionsInvoice': invoice_objs
        }

    @transaction.atomic
    def process_payment_notification(self, invoice_reference):
        """
        Process payment notification from Ledger for admissions booking (idempotent).
        
        This method handles payment confirmation for an admissions booking, whether called
        from the user-facing success view or from a background notification endpoint.
        It's designed to be idempotent - safe to call multiple times with the same
        invoice_reference.
        
        Args:
            invoice_reference (str): Invoice reference from Ledger payment system
            
        Returns:
            dict: Context dictionary with booking data for email/display
            
        Raises:
            ValueError: If invoice validation fails
            Invoice.DoesNotExist: If invoice not found in Ledger
        """
        from mooring.models import AdmissionsBookingInvoice, AdmissionsLine
        from mooring import emails
        
        logger.info(f'Processing payment notification for admissions booking {self.id}, invoice {invoice_reference}')
        
        if not invoice_reference:
            logger.error(f'Missing invoice_reference for admissions booking {self.id}')
            raise ValueError(f'Missing invoice_reference for admissions booking {self.id}')
        
        # Lock booking row to prevent race conditions
        booking = AdmissionsBooking.objects.select_for_update().get(id=self.id)
        
        # Idempotency check - if already processed, return current state
        if booking.booking_type == 1:
            logger.info(f'AdmissionsBooking {booking.id} already processed (booking_type=1), returning current state')
            context = self._get_success_context(invoice_reference)
            context.update({
                'TEMPLATE_GROUP': 'ria',
                'PUBLIC_URL': getattr(settings, 'PUBLIC_URL', ''),
            })
            return context
        
        # Validate invoice exists and belongs to this booking
        try:
            inv = Invoice.objects.get(reference=invoice_reference)
        except Invoice.DoesNotExist:
            logger.error(f'{booking.customer.get_full_name() if booking.customer else "Anonymous user"} '
                        f'tried making an admissions booking with an incorrect invoice {invoice_reference}')
            raise
        
        # Verify invoice is from correct payment system
        if inv.system not in ['0516']:
            logger.error(f'{booking.customer.get_full_name() if booking.customer else "Anonymous user"} '
                        f'tried making an admissions booking with an invoice from another system: {inv.system}, '
                        f'invoice reference: {inv.reference}')
            raise ValueError(f'Invoice {invoice_reference} is from wrong system: {inv.system}')
        
        # Verify that the invoice has been paid in full or overpaid
        if inv.payment_amount < inv.amount:
            logger.error(f'Invoice {invoice_reference} for admissions booking {booking.id} is not fully paid (amount: {inv.amount}, paid: {inv.payment_amount})')
            raise ValueError(f'Invoice {invoice_reference} is not fully paid')
        
        # Verify invoice ownership via basket booking_reference
        booking_reference = settings.DAILY_ADMISSION_REF_PREFIX + str(booking.id)
        basket = Basket.objects.filter(
            status='Submitted',
            system=settings.PAYMENT_SYSTEM_ID,
            booking_reference=booking_reference
        ).order_by('-id')
        
        if not basket.exists():
            logger.error(f'No basket found for admissions booking {booking.id} with reference {booking_reference}')
            raise ValueError(f'No basket found for admissions booking {booking.id}')
        
        # Verify invoice order matches basket
        order = Order.objects.get(number=inv.order_number)
        order_user_id = getattr(order, 'user_id', None)
        booking_user_id = booking.customer.id if booking.customer else None

        logger.info(f"Validating ownership: Ledger Order User={order_user_id}, Booking Customer={booking_user_id}")

        if order_user_id != booking_user_id:
            logger.error(f'Invoice {invoice_reference} order does not match basket for admissions booking {booking.id}')
            raise ValueError(f'Invoice ownership validation failed for admissions booking {booking.id}')
        
        # Check if invoice has already been used (duplicate check)
        existing_invoice = AdmissionsBookingInvoice.objects.filter(invoice_reference=invoice_reference).exclude(admissions_booking=booking)
        if existing_invoice.exists():
            logger.error(f'{booking.customer.get_full_name() if booking.customer else "Anonymous user"} '
                        f'tried making an admission booking with an already used invoice {invoice_reference}')
            raise ValueError(f'Invoice {invoice_reference} has already been used')
        
        # Create/get AdmissionsBookingInvoice linking record
        admissions_invoice, created = AdmissionsBookingInvoice.objects.get_or_create(
            admissions_booking=booking,
            invoice_reference=invoice_reference
        )
        
        if created:
            logger.info(f'Created AdmissionsBookingInvoice for booking {booking.id}, invoice {invoice_reference}')
        else:
            logger.info(f'AdmissionsBookingInvoice already exists for booking {booking.id}, invoice {invoice_reference}')
        
        # Apply override_lines amounts to admissions lines
        for al_id in booking.override_lines.keys():
            try:
                ad_line = AdmissionsLine.objects.get(id=int(al_id))
                ad_line.cost = booking.override_lines[str(al_id)]
                ad_line.save()
                logger.info(f'Applied override amount {booking.override_lines[str(al_id)]} to AdmissionsLine {al_id}')
            except AdmissionsLine.DoesNotExist:
                logger.warning(f'AdmissionsLine {al_id} not found for override in booking {booking.id}')
        
        # Update booking state - set to confirmed
        booking.booking_type = 1  # Internet booking (confirmed)
        
        # Save booking
        booking.save()
        logger.info(f'Successfully processed payment notification for admissions booking {booking.id}')
        
        # Return context dict for email/display
        # return booking._get_success_context(invoice_reference)
        context = booking._get_success_context(invoice_reference)
        context.update({
            'TEMPLATE_GROUP': 'ria',
            'PUBLIC_URL': getattr(settings, 'PUBLIC_URL', ''),
            'SITE_URL': getattr(settings, 'SITE_URL', ''),
        })
        return context
    
    def send_payment_emails(self, request_or_context):
        """
        Send payment confirmation and invoice emails for admissions booking.
        
        This method can be called from either:
        1. Success views with HttpRequest (sync flow after payment redirect)
        2. API notification endpoints with context dict (async background callback)
        
        Args:
            request_or_context: Either HttpRequest object or dict containing context data
        
        Raises:
            No exceptions - email errors are logged but don't fail the transaction
        """
        from mooring import emails
        from mooring.context_processors import template_context
        
        try:
            # Determine if input is HttpRequest or dict context
            if isinstance(request_or_context, HttpRequest):
                # Sync flow - extract context from request
                context_processor = template_context(request_or_context)
                logger.info(f'Sending payment emails for admissions booking {self.id} (sync flow with HttpRequest)')
            else:
                # Async flow - use provided context dict
                context_processor = request_or_context
                logger.info(f'Sending payment emails for admissions booking {self.id} (async flow with context dict)')
            
            # Send invoice email
            try:
                emails.send_admissions_booking_invoice(self, context_processor)
                logger.info(f'Successfully sent invoice email for admissions booking {self.id}')
            except Exception as e:
                logger.error(f'Error sending invoice email for admissions booking {self.id}: {e}', exc_info=True)
            
            # Send confirmation email
            try:
                emails.send_admissions_booking_confirmation(self, context_processor)
                logger.info(f'Successfully sent confirmation email for admissions booking {self.id}')
            except Exception as e:
                logger.error(f'Error sending confirmation email for admissions booking {self.id}: {e}', exc_info=True)
                
        except Exception as e:
            # Catch-all for any unexpected errors - log but don't fail
            logger.error(f'Unexpected error sending payment emails for admissions booking {self.id}: {e}', exc_info=True)


class AdmissionsLine(models.Model):
    arrivalDate = models.DateField()
    overnightStay = models.BooleanField(default=False)
    admissionsBooking = models.ForeignKey(AdmissionsBooking, on_delete=models.PROTECT, blank=False, null=False)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00')
    location = models.ForeignKey(AdmissionsLocation, blank=True, null=True, on_delete=models.SET_NULL)
    

class AdmissionsOracleCode(models.Model):
    oracle_code = models.CharField(max_length=50, null=True,blank=True)
    mooring_group = models.OneToOneField('MooringAreaGroup', blank=False, null=False, on_delete=models.PROTECT)


class AdmissionsBookingInvoice(models.Model):
    admissions_booking = models.ForeignKey(AdmissionsBooking, related_name='invoices', on_delete=models.CASCADE)
    invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    system_invoice = models.BooleanField(default=False)

    def __str__(self):
        return 'Fee Payment {} : Invoice #{}'.format(self.id,self.invoice_reference)

    # Properties
    # ==================
    @property
    def active(self):
        try:
            invoice = Invoice.objects.get(reference=self.invoice_reference)
            return False if invoice.voided else True
        except Invoice.DoesNotExist:
            pass
        return False

class AdmissionsRate(models.Model):
    period_start = models.DateField(blank=False, null=False)
    period_end = models.DateField(blank=True, null=True)
    adult_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    adult_overnight_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    concession_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    concession_overnight_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    children_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    children_overnight_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    infant_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    infant_overnight_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    family_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    family_overnight_cost = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)
    comment = models.CharField(max_length=250, blank=True, null=True)
    reason = models.ForeignKey('AdmissionsReason', on_delete=models.CASCADE)
    mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False, on_delete=models.CASCADE)

    def __str__(self):
        return '{} - {} ({})'.format(self.period_start, self.period_end, self.comment)
    
    # Properties
    # =================================
    @property
    def deletable(self):
        today = datetime.now().date()
        if self.date_start >= today:
            return True
        return False

    @property
    def editable(self):
        today = datetime.now().date()
        if (self.period_start > today and not self.period_end) or ( self.period_start > today <= self.period_end):
            return True
        return False

        
class GlobalSettings(models.Model):
    keys = (
        (0, 'Non Online Booking Fee'),
        (1, 'Max Stay'),
        (2, 'Max Advance Booking'),
        (3, 'Max Length Small'),
        (4, 'Max Length Medium'),
        (5, 'Max Length Large'),
        (6, 'Max Draft Small'),
        (7, 'Max Draft Medium'),
        (8, 'Max Draft Large'),
        (9, 'Max Beam Small'),
        (10, 'Max Beam Medium'),
        (11, 'Max Beam Large'),
        (12, 'Max Weight Small'),
        (13, 'Max Weight Medium'),
        (14, 'Max Weight Large'),
        (15, 'URL - Internal'),
        (16, 'URL - External'),
        (17, 'Non Online Booking Oracle Code'),
        (18, 'Max Advance Booking (Open Time)')
    )
    mooring_group = models.ForeignKey('MooringAreaGroup', blank=False, null=False, on_delete=models.CASCADE)
    key = models.SmallIntegerField(choices=keys, blank=False, null=False)
    value = models.CharField(max_length=255)

    class Meta:
        unique_together = ('mooring_group', 'key',)
        verbose_name_plural = "Global Settings"

    def clean(self):
        if self.key == 18:
            import re
            r = re.compile(r'^\d\d:\d\d$')
            print ("MATCH")
            print (r.match(self.value))
            if r.match(self.value) is None:
                print ("NOT VA")
                raise ValidationError("Invalid time. Must be 24 hour format, example:15:00")
            else:
                v = self.value.split(":")
                if int(v[0]) > 23:
                     raise ValidationError("Hour can not be greater than 23")
                if int(v[1]) > 59:
                     raise ValidationError("Minute can not be greater than 59")

    def save(self, *args, **kwargs):
        try:
            if self.key < 15:
                int(self.value)

        except Exception as e:
            pass

        self.full_clean()
        super(GlobalSettings,self).save(*args,**kwargs)


class RefundFailed(models.Model):
    STATUS = (
        (0, 'Pending'),
        (1, 'Refund Completed'),
    )


    booking = models.ForeignKey(Booking, related_name = "booking_refund", null=True, blank=True, on_delete=models.SET_NULL)
    admission_booking = models.ForeignKey(AdmissionsBooking, null=True, blank=True, on_delete=models.SET_NULL)
    invoice_reference = models.CharField(max_length=50, null=True, blank=True, default='')
    refund_amount = models.DecimalField(max_digits=8, decimal_places=2, default='0.00', blank=False, null=False)            
    status = models.SmallIntegerField(choices=STATUS, default=0)
    basket_json = django_models.JSONField(null=True,blank=True)
    created = models.DateTimeField(default=timezone.now)
    completed_date = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(EmailUser, blank=True, null=True, related_name="RefundFailed_completed_by", on_delete=models.SET_NULL) 

# LISTENERS
# ======================================
class MooringAreaBookingRangeListener(object):
    """
    Event listener for MooringAreaBookingRange 
    """

    @staticmethod
    @receiver(pre_save, sender=MooringAreaBookingRange)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = MooringAreaBookingRange.objects.get(pk=instance.pk)
            setattr(instance, "_original_instance", original_instance)

            if not instance._is_same(original_instance):
                instance.updated_on = timezone.now()
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")
        else:
            try:
                within = MooringAreaBookingRange.objects.filter(~Q(id=instance.id),Q(campground=instance.campground),Q(range_start__lte=instance.range_start), Q(range_end__gte=instance.range_start) | Q(range_end__isnull=True) )
                for w in within:
                    w.range_end = instance.range_start
                    w.save(skip_validation=True)
            except MooringAreaBookingRange.DoesNotExist:
                pass
        if instance.status == 0 and not instance.range_end:
            try:
                another_open = MooringAreaBookingRange.objects.filter(campground=instance.campground,range_start=instance.range_start+timedelta(seconds=1),status=0).latest('updated_on')
                instance.range_end = instance.range_start
            except MooringAreaBookingRange.DoesNotExist:
                pass

    @staticmethod
    @receiver(post_delete, sender=MooringAreaBookingRange)
    def _post_delete(sender, instance, **kwargs):
        today = timezone.now()
        if instance.status != 0 and instance.range_end:
            try:
                linked_open = MooringAreaBookingRange.objects.filter(range_start=instance.range_end + timedelta(seconds=1), status=0).order_by('updated_on')
                if instance.range_start >= today:
                    if linked_open:
                        linked_open = linked_open[0]
                        linked_open.range_start = instance.range_start
                    else:
                        linked_open = None
                else:
                    if linked_open:
                        linked_open = linked_open[0]
                        linked_open.range_start = today
                    else:
                        linked_open = None
                if linked_open:
                    linked_open.save(skip_validation=True)
            except MooringAreaBookingRange.DoesNotExist:
                pass
        elif instance.status != 0 and not instance.range_end:
            try:
                if instance.range_start >= today:
                    MooringAreaBookingRange.objects.create(campground=instance.campground,range_start=instance.range_start,status=0)
                else:
                    MooringAreaBookingRange.objects.create(campsite=instance.campground,range_start=today,status=0)
            except:
                pass
        cache.delete('campgrounds_dt')

    @staticmethod
    @receiver(post_save, sender=MooringAreaBookingRange)
    def _post_save(sender, instance, **kwargs):
        original_instance = getattr(instance, "_original_instance") if hasattr(instance, "_original_instance") else None
        if not original_instance:
            pass

        # Check if its a closure and has an end date to create new opening range
        if instance.status != 0 and instance.range_end:
            another_open = MooringAreaBookingRange.objects.filter(campground=instance.campground,range_start=instance.range_end+timedelta(seconds=1),status=0)
            if not another_open:
                try:
                    MooringAreaBookingRange.objects.create(campground=instance.campground,range_start=instance.range_end+timedelta(seconds=1),status=0)
                except BookingRangeWithinException as e:
                    pass

class MarinaAreaListener(object):
    """
    Event listener for Campgrounds
    """

    @staticmethod
    @receiver(pre_save, sender=MooringArea)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = MarinePark.objects.filter(pk=instance.pk)
            if original_instance.exists():
                setattr(instance, "_original_instance", original_instance.first())
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")

    @staticmethod
    @receiver(post_save, sender=MooringArea)
    def _post_save(sender, instance, **kwargs):
        original_instance = getattr(instance, "_original_instance") if hasattr(instance, "_original_instance") else None
        if not original_instance:
            pass
            # Create an opening booking range on creation of Campground
            #MooringAreaBookingRange.objects.create(campground=instance,range_start=datetime.now().date(),status=0)
        else:
            pass
            #if original_instance.price_level != instance.price_level:
                # Get all campsites
            #    today = datetime.now().date()
            #    campsites = instance.campsites.all()
            #    campsite_list = campsites.values_list('id', flat=True)
            #    rates = MooringsiteRate.objects.filter(campsite__in=campsite_list,update_level=original_instance.price_level)
            #    current_rates = rates.filter(Q(date_end__isnull=True),Q(date_start__lte =  today)).update(date_end=today)
            #    future_rates = rates.filter(date_start__gt = today).delete()
            #    if instance.price_level == 1:
            #        #Check if there are any existant campsite class rates
            #        for c in campsites:
            #            try:
            #                ch = MooringsiteClassPriceHistory.objects.get(Q(date_end__isnull=True),id=c.campsite_class_id,date_start__lte = today)
            #                cr = MooringsiteRate(campsite=c,rate_id=ch.rate_id,date_start=today + timedelta(days=1))
            #                cr.save()
            #            except MooringsiteClassPriceHistory.DoesNotExist:
             #               pass
             #           except Exception:
             #               pass

class MooringsiteBookingRangeListener(object):
    """
    Event listener for MooringsiteBookingRange
    """

    @staticmethod
    @receiver(pre_save, sender=MooringsiteBookingRange)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = MooringsiteBookingRange.objects.get(pk=instance.pk)
            setattr(instance, "_original_instance", original_instance)

            if not instance._is_same(original_instance):
                instance.updated_on = timezone.now()
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")
        else:
            try:
                within = MooringsiteBookingRange.objects.get(Q(campsite=instance.campsite),Q(range_start__lte=instance.range_start), Q(range_end__gte=instance.range_start) | Q(range_end__isnull=True) )
                within.range_end = instance.range_start
                within.save(skip_validation=True)
            except MooringsiteBookingRange.DoesNotExist:
                pass
        if instance.status == 0 and not instance.range_end:
            try:
                another_open = MooringsiteBookingRange.objects.filter(campsite=instance.campsite,range_start=instance.range_start+timedelta(days=1),status=0).latest('updated_on')
                instance.range_end = instance.range_start
            except MooringsiteBookingRange.DoesNotExist:
                pass

    @staticmethod
    @receiver(post_delete, sender=MooringsiteBookingRange)
    def _post_delete(sender, instance, **kwargs):
        today = datetime.now().date()
        if instance.status != 0 and instance.range_end:
            try:
                linked_open = MooringsiteBookingRange.objects.get(range_start=instance.range_end + timedelta(days=1), status=0)
                if instance.range_start >= today:
                    if linked_open:
                        linked_open = linked_open[0]
                        linked_open.range_start = instance.range_start
                    else:
                        linked_open = None
                else:
                    if linked_open:
                        linked_open = linked_open[0]
                        linked_open.range_start = today
                    else:
                        linked_open = None
                if linked_open:
                    linked_open.save(skip_validation=True)
            except MooringsiteBookingRange.DoesNotExist:
                pass
        elif instance.status != 0 and not instance.range_end:
            try:
                if instance.range_start >= today:
                    MooringsiteBookingRange.objects.create(campsite=instance.campsite,range_start=instance.range_start,status=0)
                else:
                    MooringsiteBookingRange.objects.create(campsite=instance.campsite,range_start=today,status=0)
            except:
                pass

    @staticmethod
    @receiver(post_save, sender=MooringsiteBookingRange)
    def _post_save(sender, instance, **kwargs):
        original_instance = getattr(instance, "_original_instance") if hasattr(instance, "_original_instance") else None
        if not original_instance:
            pass

        # Check if its a closure and has an end date to create new opening range
        if instance.status != 0 and instance.range_end:
            another_open = MooringsiteBookingRange.objects.filter(campsite=instance.campsite,range_start=datetime.now().date()+timedelta(days=1),status=0)

            if not another_open:
                try:
                    MooringsiteBookingRange.objects.create(campsite=instance.campsite,range_start=instance.range_end+timedelta(days=1),status=0)
                except BookingRangeWithinException as e:
                    pass

class BookingListener(object):
    """
    Event listener for Bookings
    """

    @staticmethod
    @receiver(pre_save, sender=Booking)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = Booking.objects.filter(pk=instance.pk)
            if original_instance.exists():
                setattr(instance, "_original_instance", original_instance.first())
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")
        else:
            instance.full_clean()

class MooringsiteListener(object):
    """
    Event listener for Mooringsites
    """

    @staticmethod
    @receiver(pre_save, sender=Mooringsite)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = Mooringsite.objects.filter(pk=instance.pk)
            if original_instance.exists():
                setattr(instance, "_original_instance", original_instance.first())
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")

    @staticmethod
    @receiver(post_save, sender=Mooringsite)
    def _post_save(sender, instance, **kwargs):
        original_instance = getattr(instance, "_original_instance") if hasattr(instance, "_original_instance") else None
        if not original_instance:
            # Create an opening booking range on creation of Campground
             MooringsiteBookingRange.objects.create(campsite=instance,range_start=datetime.now().date(),status=0)

class MooringsiteRateListener(object):
    """
    Event listener for Mooringsite Rate
    """

    @staticmethod
    @receiver(pre_save, sender=MooringsiteRate)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = MooringsiteRate.objects.filter(pk=instance.pk)
            if original_instance.exists():
                setattr(instance, "_original_instance", original_instance.first())
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")
        else:
            try:
                within = MooringsiteRate.objects.get(Q(campsite=instance.campsite),Q(date_start__lte=instance.date_start), Q(date_end__gte=instance.date_start) | Q(date_end__isnull=True) )
                within.date_end = instance.date_start - timedelta(days=1)
                within.save()
            except MooringsiteRate.DoesNotExist:
                pass
            # check if there is a newer record and set the end date as the previous record minus 1 day
            x = MooringsiteRate.objects.filter(Q(campsite=instance.campsite),Q(date_start__gte=instance.date_start), Q(date_end__gte=instance.date_start) | Q(date_end__isnull=True) ).order_by('date_start')
            if x:
                x = x[0]
                instance.date_end = x.date_start - timedelta(days=1)

    @staticmethod
    @receiver(pre_delete, sender=MooringsiteRate)
    def _pre_delete(sender, instance, **kwargs):
        if not instance.date_end:
            c = MooringsiteRate.objects.filter(campsite=instance.campsite).order_by('-date_start').exclude(id=instance.id)
            if c:
                c = c[0] 
                c.date_end = None
                c.save() 

class MooringsiteStayHistoryListener(object):
    """
    Event listener for Mooringsite Stay History
    """

    @staticmethod
    @receiver(pre_save, sender=MooringsiteStayHistory)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = MooringsiteStayHistory.objects.filter(pk=instance.pk)
            if original_instance.exists():
                setattr(instance, "_original_instance", original_instance.first())
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")
        else:
            try:
                within = MooringsiteStayHistory.objects.get(Q(campsite=instance.campsite),Q(range_start__lte=instance.range_start), Q(range_end__gte=instance.range_start) | Q(range_end__isnull=True) )
                within.range_end = instance.range_start - timedelta(days=1)
                within.save()
            except MooringsiteStayHistory.DoesNotExist:
                pass

    @staticmethod
    @receiver(post_delete, sender=MooringsiteStayHistory)
    def _post_delete(sender, instance, **kwargs):
        if not instance.range_end:
            MooringsiteStayHistory.objects.filter(range_end=instance.range_start- timedelta(days=1),campsite=instance.campsite).update(range_end=None)

class MarinaAreaStayHistoryListener(object):
    """
    Event listener for Campground Stay History
    """

    @staticmethod
    @receiver(pre_save, sender=MooringAreaStayHistory)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = MooringAreaStayHistory.objects.filter(pk=instance.pk)
            if original_instance.exists():
                setattr(instance, "_original_instance", original_instance.first())
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")
        else:
            try:
                within = MooringAreaStayHistory.objects.get(Q(mooringarea=instance.mooringarea),Q(range_start__lte=instance.range_start), Q(range_end__gte=instance.range_start) | Q(range_end__isnull=True) )
                within.range_end = instance.range_start - timedelta(days=2)
                within.save()
            except MooringAreaStayHistory.DoesNotExist:
                pass

            # check if there is a newer record and set the end date as the previous record minus 1 day
            x = MooringAreaStayHistory.objects.filter(Q(mooringarea=instance.mooringarea),Q(range_start__gte=instance.range_start), Q(range_end__gte=instance.range_start) | Q(range_end__isnull=True) ).order_by('range_start')
            if x:
                x = x[0]
                instance.date_end = x.date_start - timedelta(days=2)

    @staticmethod
    @receiver(pre_delete, sender=MooringAreaStayHistory)
    def _pre_delete(sender, instance, **kwargs):
        if not instance.range_end:
            c = MooringAreaStayHistory.objects.filter(mooringarea=instance.mooringarea).order_by('-range_start').exclude(id=instance.id)
            if c:
                c = c[0]
                c.date_end = None
                c.save()

class MarinaEntryRateListener(object):
    """
    Event listener for MarinaEntryRate
    """

    @staticmethod
    @receiver(pre_save, sender=MarinaEntryRate)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = MarinaEntryRate.objects.filter(pk=instance.pk)
            if original_instance.exists():
                setattr(instance, "_original_instance", original_instance.first())
            price_before = MarinaEntryRate.objects.filter(period_start__lt=instance.period_start).order_by("-period_start")
            if price_before:
                price_before = price_before[0]
                price_before.period_end = instance.period_start
                instance.period_start = instance.period_start + timedelta(days=1)
                price_before.save()
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")
        else:
            try:
                price_before = MarinaEntryRate.objects.filter(period_start__lt=instance.period_start).order_by("-period_start")
                if price_before:
                    price_before = price_before[0]
                    price_before.period_end = instance.period_start
                    price_before.save()
                    instance.period_start = instance.period_start + timedelta(days=1)
                price_after = MarinaEntryRate.objects.filter(period_start__gt=instance.period_start).order_by("period_start")
                if price_after:
                    price_after = price_after[0]
                    instance.period_end = price_after.period_start - timedelta(days=1)
            except Exception as e:
                pass

    @staticmethod
    @receiver(post_delete, sender=MarinaEntryRate)
    def _post_delete(sender, instance, **kwargs):
        price_before = MarinaEntryRate.objects.filter(period_start__lt=instance.period_start).order_by("-period_start")
        price_after = MarinaEntryRate.objects.filter(period_start__gt=instance.period_start).order_by("period_start")
        if price_after:
            price_after = price_after[0]
            if price_before:
                price_before = price_before[0]
                price_before.period_end =  price_after.period_start - timedelta(days=1)
                price_before.save()
        elif price_before:
            price_before = price_before[0]
            price_before.period_end = None
            price_before.save()


class AdmissionsRateListener(object):
    """
    Event listener for AdmissionsRate
    """

    @staticmethod
    @receiver(pre_save, sender=AdmissionsRate)
    def _pre_save(sender, instance, **kwargs):
        if instance.pk:
            original_instance = AdmissionsRate.objects.filter(pk=instance.pk)
            if original_instance.exists():
                setattr(instance, "_original_instance", original_instance.first())
            price_before = AdmissionsRate.objects.filter(mooring_group=instance.mooring_group, period_start__lt=instance.period_start).order_by("-period_start")
            if price_before:
                if price_before[0].pk == instance.pk:
                    price_before = price_before[1]
                else:
                    price_before = price_before[0]
                price_before.period_end = instance.period_start + timedelta(days=-1)
                price_before.save()
        elif hasattr(instance, "_original_instance"):
            delattr(instance, "_original_instance")
        else:
            try:
                price_before = AdmissionsRate.objects.filter(mooring_group=instance.mooring_group, period_start__lt=instance.period_start).order_by("-period_start")
                if price_before:
                    price_before = price_before[0]
                    price_before.period_end = instance.period_start 
                    price_before.save()
                    instance.period_start = instance.period_start + timedelta(days=1)
                price_after = AdmissionsRate.objects.filter(mooring_group=instance.mooring_group, period_start__gt=instance.period_start).order_by("period_start")
                if price_after:
                    price_after = price_after[0]
                    instance.period_end = price_after.period_start - timedelta(days=1)
            except Exception as e:
                pass

    @staticmethod
    @receiver(post_delete, sender=AdmissionsRate)
    def _post_delete(sender, instance, **kwargs):
        price_before = AdmissionsRate.objects.filter(mooring_group=instance.mooring_group, period_start__lt=instance.period_start).order_by("-period_start")
        price_after = AdmissionsRate.objects.filter(mooring_group=instance.mooring_group, period_start__gt=instance.period_start).order_by("period_start")
        if price_after:
            price_after = price_after[0]
            if price_before:
                price_before = price_before[0]
                price_before.period_end =  price_after.period_start - timedelta(days=1)
                price_before.save()
        elif price_before:
            price_before = price_before[0]
            price_before.period_end = None
            price_before.save()



class API(models.Model):
    STATUS = (
       (0, 'Inactive'),
       (1, 'Active'),
    )


    system_name = models.CharField(max_length=512)
    api_key = models.CharField(max_length=512,null=True, blank=True, default='', help_text="Key is auto generated,  Leave blank or blank out to create a new key")
    allowed_ips = models.TextField(null=True, blank=True, default='', help_text="Use network ranges format: eg 1 ip = 10.1.1.1/32 or for a c class block of ips use 192.168.1.0/24 etc")
    active = models.SmallIntegerField(choices=STATUS, default=0)

    def save(self, *args, **kwargs):
        if self.api_key is not None:

             if len(self.api_key) > 1:
                  pass
             else:
                  self.api_key = self.get_random_key(100)
        else:
            self.api_key = self.get_random_key(100)
        super(API,self).save(*args,**kwargs)


    def get_random_key(self,key_length=100):
        return get_random_string(length=key_length, allowed_chars=u'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')




class VesselLicence(models.Model): 

    STATUS = (
       (0, 'Cancelled'),
       (1, 'Active'),
    )

    LICENCE_TYPE = (
       (1, 'Licence'),
       (2, 'Authorised User'),
       (3, 'Annual Admission'),
    )

    vessel_rego = models.CharField(max_length=100)
    licence_id = models.IntegerField(null=True, blank=True)
    licence_type= models.IntegerField(choices=LICENCE_TYPE, default=None, null=True)
    start_date = models.DateField(default=None, null=True)
    expiry_date = models.DateField(default=None, null=True)
    status = models.SmallIntegerField(choices=STATUS, default=1) 
    updated = models.DateTimeField(default=timezone.now, editable=False)
    created = models.DateTimeField(default=timezone.now, editable=False)

    def save(self, *args,**kwargs):
        self.updated = timezone.now()
        UpdateLog.objects.create(model_name='VesselLicence', json_context={'vessel_rego':self.vessel_rego,'licence_id': self.licence_id, 'licence_type': dict(self.LICENCE_TYPE).get(self.licence_type), 'licence_type_id': self.licence_type,'start_date': self.start_date.isoformat() if self.start_date else None, 'expiry_date':self.expiry_date.isoformat() if self.expiry_date else None,'status': dict(self.STATUS).get(self.status), 'status_id': self.status  })
        super(VesselLicence, self).save(*args,**kwargs)



class UpdateLog(models.Model):

    model_name = models.CharField(max_length=200)
    json_context = django_models.JSONField(null=True,blank=True, default=dict)
    created = models.DateTimeField(default=timezone.now, editable=False)
    

