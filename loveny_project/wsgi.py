import os
import sys

# Set Paystack Live API Keys as environment variables for your application
# IMPORTANT: Replace these with your actual Live Public and Secret Keys
os.environ['PAYSTACK_PUBLIC_KEY'] = 'pk_live_6fd34253cf04d94620e50e8c547b5259d052c121'
os.environ['PAYSTACK_SECRET_KEY'] = 'sk_live_62f19d8b261f11fcbd41057d38fc200a471d6ea1'

# Path to your project's root directory (where manage.py is)
path = '/home/loveny/loveny-app'
if path not in sys.path:
    sys.path.append(path)

# Path to your virtual environment's site-packages
# Confirmed python3.9 based on your venv creation
site_packages_path = '/home/loveny/.virtualenvs/loveny-app-venv/lib/python3.9/site-packages'
if site_packages_path not in sys.path:
    sys.path.append(site_packages_path)

# Set the DJANGO_SETTINGS_MODULE environment variable
# This points to your main Django project's settings file
os.environ['DJANGO_SETTINGS_MODULE'] = 'loveny_project.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()