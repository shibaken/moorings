# Generated by Django 3.2.24 on 2024-10-04 02:32

from django.conf import settings
import django.core.files.storage
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ledger_api_client', '0015_alter_systemuser_first_name_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mooring', '0165_auto_20220928_1052'),
    ]

    operations = [
        migrations.AlterField(
            model_name='admissionsbooking',
            name='location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.admissionslocation'),
        ),
        migrations.AlterField(
            model_name='admissionsbooking',
            name='override_lines',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AlterField(
            model_name='admissionsline',
            name='location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.admissionslocation'),
        ),
        migrations.AlterField(
            model_name='admissionsreason',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='annualbookingperiodgroup',
            name='letter',
            field=models.FileField(blank=True, max_length=512, null=True, storage=django.core.files.storage.FileSystemStorage(base_url='/private-media/', location='/data/data/projects/moorings/private-media/'), upload_to='letter/%Y/%m/%d/%H/'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='admission_payment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.admissionsbooking'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='details',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='booking',
            name='mooringarea',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringarea'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='old_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.booking'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='override_lines',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AlterField(
            model_name='booking',
            name='override_reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.discountreason'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='property_cache',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AlterField(
            model_name='bookingannualadmission',
            name='annual_booking_period_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.annualbookingperiodgroup'),
        ),
        migrations.AlterField(
            model_name='bookingannualadmission',
            name='details',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='bookingannualadmission',
            name='override_lines',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AlterField(
            model_name='bookingannualadmission',
            name='override_reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.discountreason'),
        ),
        migrations.AlterField(
            model_name='bookingannualadmission',
            name='sticker_no_history',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
        migrations.AlterField(
            model_name='bookinghistory',
            name='booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='history', to='mooring.booking'),
        ),
        migrations.AlterField(
            model_name='bookinghistory',
            name='campsites',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='bookinghistory',
            name='details',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='bookinghistory',
            name='invoice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ledger_api_client.invoice'),
        ),
        migrations.AlterField(
            model_name='bookinghistory',
            name='vessels',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='bookingperiod',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='bookingperiodoption',
            name='cancel_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.cancelgroup'),
        ),
        migrations.AlterField(
            model_name='bookingperiodoption',
            name='change_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.changegroup'),
        ),
        migrations.AlterField(
            model_name='closurereason',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='contact',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='discountreason',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='district',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='marinepark',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='maximumstayreason',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='mooringarea',
            name='address',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='mooringareabookingrange',
            name='closure_reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.closurereason'),
        ),
        migrations.AlterField(
            model_name='mooringareabookingrange',
            name='open_reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.openreason'),
        ),
        migrations.AlterField(
            model_name='mooringareastayhistory',
            name='reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.maximumstayreason'),
        ),
        migrations.AlterField(
            model_name='mooringsitebookingrange',
            name='closure_reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.closurereason'),
        ),
        migrations.AlterField(
            model_name='mooringsitebookingrange',
            name='open_reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.openreason'),
        ),
        migrations.AlterField(
            model_name='mooringsiterate',
            name='reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.pricereason'),
        ),
        migrations.AlterField(
            model_name='mooringsiteratelog',
            name='reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.pricereason'),
        ),
        migrations.AlterField(
            model_name='mooringsitestayhistory',
            name='reason',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.maximumstayreason'),
        ),
        migrations.AlterField(
            model_name='openreason',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='pricereason',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='promoarea',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='refundfailed',
            name='admission_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.admissionsbooking'),
        ),
        migrations.AlterField(
            model_name='refundfailed',
            name='basket_json',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='refundfailed',
            name='booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='booking_refund', to='mooring.booking'),
        ),
        migrations.AlterField(
            model_name='refundfailed',
            name='completed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='RefundFailed_completed_by', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='region',
            name='mooring_group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='mooring.mooringareagroup'),
        ),
        migrations.AlterField(
            model_name='updatelog',
            name='json_context',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]
