# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-01-01 19:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app03', '0016_auto_20180101_1919'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='last_consult_date',
            field=models.DateField(blank=True, null=True, verbose_name='最后跟进日期'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='recv_date',
            field=models.DateField(blank=True, null=True, verbose_name='顾问接单日期'),
        ),
    ]