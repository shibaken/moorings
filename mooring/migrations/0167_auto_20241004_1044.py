# Generated by Django 3.2.24 on 2024-10-04 02:44

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mooring', '0166_auto_20241004_1032'),
    ]

    operations = [
        migrations.CreateModel(
            name='MooringAreaGroupMember',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('emailuser', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('mooringareagroup', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mooring.mooringareagroup')),
            ],
            options={
                'db_table': 'mooring_mooringareagroup_members',
            },
        ),
        migrations.AlterField(
            model_name='mooringareagroup',
            name='members',
            field=models.ManyToManyField(blank=True, through='mooring.MooringAreaGroupMember', to=settings.AUTH_USER_MODEL),
        ),
    ]
