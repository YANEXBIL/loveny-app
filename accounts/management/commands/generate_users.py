# accounts/management/commands/generate_users.py

from django.core.management.base import BaseCommand
# Import all the choice variables directly from accounts.models
from accounts.models import (
    UserProfile, ProfileImage, GENDER_CHOICES, SEEKING_CHOICES,
    LOOKING_FOR_CHOICES, # Corrected: USER_TYPE_CHOICES to LOOKING_FOR_CHOICES
    HEIGHT_CHOICES, BODY_TYPE_CHOICES, ETHNICITY_CHOICES,
    RELIGION_CHOICES, MARITAL_STATUS_CHOICES, EDUCATION_CHOICES,
    OCCUPATION_CHOICES, DRINKING_CHOICES, SMOKING_CHOICES
)
from django.conf import settings
from faker import Faker
import random
from datetime import date, timedelta
import os
import requests # Import requests for fetching images
from django.core.files.base import ContentFile # Import ContentFile

class Command(BaseCommand):
    help = 'Generates 30 fake Sex Call UserProfile instances for testing purposes.' # Updated help text

    def add_arguments(self, parser):
        parser.add_argument(
            '--num_users',
            type=int,
            default=30, # Changed default to 30
            help='The number of fake users to create (default: 30).' # Updated help text
        )

    def handle(self, *args, **kwargs):
        num_users = kwargs['num_users']
        fake = Faker()
        self.stdout.write(f"Generating {num_users} fake user profiles (all 'Sex Call')...") # Updated output message

        # Clear existing non-superuser profiles to start fresh (optional, but good for testing)
        # self.stdout.write(self.style.WARNING("Deleting existing non-superuser profiles and their images..."))
        # UserProfile.objects.filter(is_superuser=False).delete()
        # self.stdout.write(self.style.SUCCESS("Existing non-superuser profiles cleared."))

        # Default image URL for gallery (can be a placeholder or a static image you have)
        # Using a placeholder service here. You can replace it with a URL to an image in your static files.
        PLACEHOLDER_IMAGE_URL = "https://placehold.co/600x400/FFC0CB/FFF?text=LOVENY" # Pink placeholder

        # Ensure MEDIA_ROOT exists
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'profile_pictures'), exist_ok=True)


        for i in range(num_users):
            username = fake.unique.user_name()
            email = fake.unique.email()
            password = 'password123' # A simple password for all fake users

            # Generate realistic date of birth for age between 18 and 60
            today = date.today()
            max_dob = today - timedelta(days=18*365) # At least 18 years old
            min_dob = today - timedelta(days=60*365) # At most 60 years old
            
            # Faker's date_between handles this well
            date_of_birth = fake.date_between(start_date=min_dob, end_date=max_dob)

            # Use the directly imported choice variables
            gender = random.choice([g[0] for g in GENDER_CHOICES])
            seeking = random.choice([s[0] for s in SEEKING_CHOICES])
            looking_for = 'SEXCALL' # FIXED: Always set to 'SEXCALL' as requested
            
            # Get random choices for other fields
            height = random.choice([h[0] for h in HEIGHT_CHOICES])
            body_type = random.choice([bt[0] for bt in BODY_TYPE_CHOICES])
            ethnicity = random.choice([e[0] for e in ETHNICITY_CHOICES])
            religion = random.choice([r[0] for r in RELIGION_CHOICES])
            marital_status = random.choice([ms[0] for ms in MARITAL_STATUS_CHOICES])
            education = random.choice([ed[0] for ed in EDUCATION_CHOICES])
            occupation = random.choice([oc[0] for oc in OCCUPATION_CHOICES])
            drinking_habits = random.choice([dh[0] for dh in DRINKING_CHOICES])
            smoking_habits = random.choice([sh[0] for sh in SMOKING_CHOICES])
            
            # Randomly assign has_children
            has_children = random.choice([True, False, None]) # Include None for optional field

            try:
                user_profile = UserProfile.objects.create_user(
                    email=email,
                    username=username,
                    password=password,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    bio=fake.paragraph(nb_sentences=3),
                    gender=gender,
                    date_of_birth=date_of_birth,
                    location=fake.city(),
                    phone_number=fake.phone_number(),
                    looking_for=looking_for, # Now fixed to 'SEXCALL'
                    seeking=seeking,
                    is_premium=random.choice([True, False, False, False]), # More non-premium users
                    height=height,
                    body_type=body_type,
                    ethnicity=ethnicity,
                    religion=religion,
                    marital_status=marital_status,
                    has_children=has_children,
                    education=education,
                    occupation=occupation,
                    drinking_habits=drinking_habits,
                    smoking_habits=smoking_habits,
                )

                # Add a few gallery images for some users
                num_gallery_images = random.randint(0, 5) # 0 to 5 images per user
                for j in range(num_gallery_images):
                    try:
                        # Fetch the placeholder image
                        response = requests.get(PLACEHOLDER_IMAGE_URL)
                        response.raise_for_status() # Raise an exception for HTTP errors
                        
                        # Generate a unique filename
                        # Use a more robust filename generation
                        filename = f"{fake.slug()}.png"
                        
                        # Save the image content
                        # Correct path will be handled by user_image_directory_path
                        image_file = ContentFile(response.content, name=filename)
                        
                        ProfileImage.objects.create(
                            user_profile=user_profile,
                            image=image_file,
                            order=j
                        )
                    except Exception as img_e:
                        self.stdout.write(self.style.ERROR(f"  Error adding gallery image for {username}: {img_e}"))

                # Optionally set one of the gallery images as main_additional_image and profile_picture
                if num_gallery_images > 0 and random.random() < 0.7: # 70% chance to set one as main
                    all_images = ProfileImage.objects.filter(user_profile=user_profile)
                    if all_images.exists():
                        main_pic = random.choice(list(all_images))
                        user_profile.profile_picture = main_pic.image
                        user_profile.main_additional_image = main_pic
                        user_profile.save(update_fields=['profile_picture', 'main_additional_image'])


                self.stdout.write(self.style.SUCCESS(f"Successfully created user: {username} ({i+1}/{num_users})"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating user {username}: {e}"))
                # If a unique constraint fails, it will skip this user and continue
                if "UNIQUE constraint failed" in str(e):
                    self.stdout.write(self.style.WARNING("  (Likely a duplicate username/email, skipping)"))

        self.stdout.write(self.style.SUCCESS(f"Finished generating {num_users} fake users."))
