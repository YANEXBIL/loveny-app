# Generated by Django 5.2.3 on 2025-06-24 23:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_userprofile_phone_number'),
    ]

    operations = [
        migrations.RenameField(
            model_name='userprofile',
            old_name='user_type',
            new_name='looking_for',
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='phone_number',
            field=models.CharField(blank=True, help_text='Your WhatsApp phone number including country code (e.g., +2348012345678)', max_length=20, null=True),
        ),
    ]
