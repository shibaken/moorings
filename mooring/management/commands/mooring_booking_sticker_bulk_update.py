from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from mooring import emails
# from ledger.accounts.models import EmailUser, Address, EmailIdentity
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
from mooring import models
from datetime import timedelta, date, datetime
from decimal import Decimal as D
# from ledger.payments.utils import systemid_check
from decimal import Decimal
import itertools

class Command(BaseCommand):
    help = 'Bulk Update Sticker Information'

    def add_arguments(self, parser):
        # CSV File to run the update from        
        parser.add_argument('file',)
        # should be the email account of the developer running this script.  will record your name against the update.
        parser.add_argument('email',)

    def handle(self, *args, **options):
        print ("RUNNING")
        email = options['email']
        user = EmailUser.objects.get(email=email) 
        #days_back = options['days_back'][0]
        file_path = options['file']
        print (file_path)

        booking_updates = []
        booking_errors = []
        refund_success = False

        f = open(file_path)
        for line in f:
            line = line.strip('\n')
            row = line.split(",")
            booking_id = row[0].replace("AA", "")
            sticker_no = row[1]
            print(row[0]+":"+row[1])
            print (booking_id)
            sticker_comment = "Bulk import of sticker"
            try:
                pass
              
                nowdt = datetime.now()
                baa = models.BookingAnnualAdmission.objects.get(id=booking_id)
                sticker_no_history = baa.sticker_no_history
                sticker_no_history.append({'value': sticker_no, 'user_id': user.id, 'first_name': user.first_name, 'last_name': user.last_name,'updated': nowdt.strftime('%Y-%m-%d %H:%M:%S'),'sticker_comment': sticker_comment})
                baa.sticker_no_history=sticker_no_history
                baa.sticker_no=sticker_no
                if baa.sticker_created is None:
                    baa.sticker_created = nowdt
                baa.save()    
                          
                booking_updates.append({'booking_id': booking_id, 'sticker_no': sticker_no})
            except Exception as e:
                print (e)
                booking_errors.append({'line': line, "error": str(e)})
                print ("-----")

        # Send email with success and failed refunds 
        context = {
         "booking_updates":booking_updates,
         "booking_errors": booking_errors 
        }

        email_list = [email,]
        for email_to in settings.NOTIFICATION_EMAIL.split(","):
               email_list.append(email_to)

        print ("SENDING EMAIL")
        print (settings.EMAIL_FROM)

        emails.sendHtmlEmail(tuple(email_list),"Bulk Sticker Update",context,'mooring/email/bulk_sticker_update.html',None,None,settings.EMAIL_FROM,'system-oim',attachments=None)
        print ("COMPLETED")  
        return "Completed"
        #print (sys.argv[0])
