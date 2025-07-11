# Generated by Django 5.2.3 on 2025-06-24 22:48

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_userprofile_profile_picture'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='phone_number',
            field=models.CharField(default=1234567890, help_text='Your WhatsApp phone number including country code (e.g., +2348012345678)', max_length=20, unique=True, validators=[django.core.validators.RegexValidator(message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.", regex='^\\+?\\d{9,15}$')]),
            preserve_default=False,
        ),
    ]
