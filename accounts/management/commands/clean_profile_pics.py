from django.core.management.base import BaseCommand
from accounts.models import UserProfile
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Cleans up UserProfile.profile_picture fields that point to the static default_avatar.png path.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting cleanup of UserProfile.profile_picture paths...")

        problematic_paths = [
            settings.DEFAULT_PROFILE_PICTURE_PATH, # e.g., 'default_avatar.png'
            os.path.join('profile_pics', settings.DEFAULT_PROFILE_PICTURE_PATH), # e.g., 'profile_pics/default_avatar.png'
            # Add any other known incorrect paths if you've seen them in your database
        ]
        
        # Normalize paths to handle potential OS differences (e.g., / vs \)
        problematic_paths = [path.replace('\\', '/') for path in problematic_paths]

        cleaned_count = 0
        total_profiles = UserProfile.objects.count()

        for user_profile in UserProfile.objects.all():
            if user_profile.profile_picture:
                current_pic_name = user_profile.profile_picture.name.replace('\\', '/') # Normalize for comparison
                
                is_problematic = False
                for p_path in problematic_paths:
                    if current_pic_name.endswith(p_path):
                        is_problematic = True
                        break

                if is_problematic:
                    # Set to an empty string to signify no file. Django's FileField treats empty string as NULL.
                    user_profile.profile_picture = '' 
                    user_profile.save(update_fields=['profile_picture'])
                    cleaned_count += 1
                    self.stdout.write(self.style.WARNING(f"  Cleaned profile_picture for user '{user_profile.username}': was '{current_pic_name}', now NULL."))
                # else:
                #     self.stdout.write(f"  User '{user_profile.username}' has valid profile picture: '{current_pic_name}'")

        self.stdout.write(self.style.SUCCESS(f"\nCleanup complete. Total profiles: {total_profiles}, Cleaned profiles: {cleaned_count}"))
