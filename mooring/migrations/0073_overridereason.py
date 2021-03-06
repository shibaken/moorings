# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2018-11-27 05:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mooring', '0072_bookingperiodoption_option_description'),
    ]

    operations = [
        migrations.CreateModel(
            name='OverrideReason',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('detailRequired', models.BooleanField(default=False)),
                ('editable', models.BooleanField(default=True, editable=False)),
            ],
            options={
                'ordering': ('id',),
                'abstract': False,
            },
        ),
    ]
