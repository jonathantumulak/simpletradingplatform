# Generated by Django 5.0.6 on 2024-06-10 03:14

import django.db.models.deletion
import django_extensions.db.fields
import trading.constants
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TradeDataFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('uploaded_file', models.FileField(upload_to='uploaded_trade_csv/', verbose_name='Uploaded File')),
                ('status', models.PositiveSmallIntegerField(choices=[(0, 'Pending'), (1, 'Processed'), (2, 'Failed')], default=0, verbose_name='Status')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Completed at')),
                ('errors', models.TextField(blank=True, help_text='Errors encountered on processing', null=True, verbose_name='Errors')),
                ('uploaded_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_trade_data_files', to=settings.AUTH_USER_MODEL, verbose_name='Uploaded by')),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
            bases=(trading.constants.TradeDataFileStatuses, models.Model),
        ),
    ]
