# -*- coding: utf-8 -*-
# Generated by Django 1.10.8 on 2018-09-20 02:26
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mooring', '0063_updateviews'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='mooringsitebooking',
            unique_together=set([]),
        ),
    ]
