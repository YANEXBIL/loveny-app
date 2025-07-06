# accounts/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.conf import settings
import requests
import json
import os
import errno # Import errno for checking OS errors
from datetime import timedelta
from django.db import transaction
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
import secrets # For generating unique references
import uuid # For generating unique transaction IDs for Paystack
from decimal import Decimal # To handle monetary values precisely


# Import all models and forms
from .forms import CustomUserCreationForm, UserProfileForm
from .models import UserProfile, Like, SubscriptionPlan, UserSubscription, ProfileImage, PaymentTransaction, LOOKING_FOR_CHOICES, GENDER_CHOICES, SEEKING_CHOICES
# Import the Notification model - CORRECTED THIS LINE
from .models import Notification


class CustomLoginView(LoginView):
    """Custom login view."""
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    """Custom logout view."""
    next_page = reverse_lazy('accounts:login')


class SignUpView(CreateView):
    """View for user registration."""
    form_class = CustomUserCreationForm
    template_name = 'accounts/registration_form.html'
    success_url = reverse_lazy('accounts:profile_edit')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


# View for Account Deletion
@login_required
def account_delete(request):
    """
    Handles the account deletion process.
    GET: Displays a confirmation page.
    POST: Deletes the user account and logs out.
    """
    if request.method == 'POST':
        user = request.user
        username = user.username # Store username for messages

        try:
            logout(request) # Log out the user first
            user.delete() # Delete the user and cascading related objects (like UserProfile)
            messages.success(request, f"Your account '{username}' has been successfully deleted. We're sad to see you go!")
            return redirect('home') # Redirect to your home page or a goodbye page
        except Exception as e:
            messages.error(request, f"An error occurred while deleting your account: {e}")
            return redirect('accounts:profile_edit') # Redirect back to profile edit or a relevant page

    # For GET request, display the confirmation page
    return render(request, 'accounts/confirm_delete.html')


@login_required
def profile_view(request):
    """Displays the current logged-in user's profile."""
    user_profile = request.user
    # Fetch user's subscription
    user_subscription = None
    try:
        user_subscription = UserSubscription.objects.get(user=user_profile)
    except UserSubscription.DoesNotExist:
        pass # No subscription found for the user

    context = {
        'user_profile': user_profile,
        'user_subscription': user_subscription, # Pass subscription to template
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit_view(request):
    """Allows the current logged-in user to edit their profile, including images.
    This view now handles AJAX submissions from the new frontend.
    """
    user_profile = request.user
    profile_form = UserProfileForm(request.POST or None, request.FILES or None, instance=user_profile, user=request.user)

    # --- Start Revised Logic for Image Data Preparation for initial page load ---
    all_images_for_frontend = []

    # Get the ID of the ProfileImage currently linked as the main_additional_image
    current_main_profile_image_id = None
    if user_profile.main_additional_image:
        current_main_profile_image_id = user_profile.main_additional_image.id

    # Add the current main profile picture first
    # Only add it if it's not already represented by a ProfileImage instance
    # (i.e., if it's the direct upload, or a default)
    is_main_from_profile_image_model = False
    if current_main_profile_image_id:
        # Check if the profile_picture field actually points to the image file of main_additional_image
        # (This avoids duplicating a gallery image that's also the main one in the initial load list)
        if user_profile.profile_picture and user_profile.main_additional_image.image.name == user_profile.profile_picture.name:
            is_main_from_profile_image_model = True

    if user_profile.profile_picture and not is_main_from_profile_image_model:
        all_images_for_frontend.append({
            'id': 'main_direct_upload', # Unique ID for direct uploads that are not from gallery
            'image__url': user_profile.profile_picture.url,
            'order': -2, # Special order for direct main upload
            'is_main': True
        })

    # Add all additional images (from the gallery model)
    all_profile_images_db = ProfileImage.objects.filter(user_profile=user_profile).order_by('order', 'pk')

    for img in all_profile_images_db:
        # Determine if this gallery image is currently set as the main profile picture
        is_this_img_main = (current_main_profile_image_id == img.id)

        all_images_for_frontend.append({
            'id': img.id,
            'image__url': img.image.url,
            'order': img.order,
            'is_main': is_this_img_main # Set is_main flag based on actual link
        })

    # Ensure a default image is always present for users without a profile_picture
    if not user_profile.profile_picture or user_profile.profile_picture.name == '': # Added check for empty string name
        if hasattr(settings, 'DEFAULT_PROFILE_PICTURE_PATH'): # Check if setting exists
            all_images_for_frontend.append({
                'id': 'default_fallback_id',
                'image__url': settings.STATIC_URL + settings.DEFAULT_PROFILE_PICTURE_PATH, # Use STATIC_URL for default static image
                'order': -3,
                'is_main': True # Make the fallback the main one if no other is present
            })


    initial_images_json = json.dumps({'data': all_images_for_frontend})
    # --- End Revised Logic for Image Data Preparation for initial page load ---

    context = {
        'profile_form': profile_form,
        'user_profile': user_profile,
        'initial_images_json': initial_images_json,
    }
    return render(request, 'accounts/profile_edit.html', context)


@require_POST
@login_required
@transaction.atomic
def ajax_profile_save(request):
    try:
        user_profile = request.user
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile, user=request.user)

        if form.is_valid():
            profile_instance = form.save(commit=False)

            # --- Helper function for robust file deletion ---
            def delete_file_safely(file_field_name, file_object):
                print(f"--- Attempting to delete {file_field_name} ---")
                if not file_object or not getattr(file_object, 'name', None):
                    print(f"DEBUG: {file_field_name} file_object is empty or has no 'name' attribute. Skipping deletion.")
                    return

                # Check if the file being deleted is the configured default profile picture
                # If so, do not delete it as it's a shared default resource.
                if hasattr(settings, 'DEFAULT_PROFILE_PICTURE_PATH') and file_object.name == settings.DEFAULT_PROFILE_PICTURE_PATH:
                    print(f"INFO: Skipping deletion of default profile picture: {file_object.name}")
                    return

                # Get the relative path (as stored in the model's FileField)
                relative_path = file_object.name

                # Construct the absolute path on the filesystem
                # Note: default_storage.delete typically works with the relative path
                # but for existence check, an absolute path is better.
                absolute_file_path = os.path.join(settings.MEDIA_ROOT, relative_path)

                print(f"DEBUG: {file_field_name} Relative path: {relative_path}")
                print(f"DEBUG: {file_field_name} Absolute path: {absolute_file_path}")

                if os.path.exists(absolute_file_path):
                    print(f"DEBUG: {file_field_name} File EXISTS on disk at: {absolute_file_path}")
                    try:
                        default_storage.delete(relative_path) # default_storage expects relative path relative to MEDIA_ROOT
                        print(f"Successfully deleted {file_field_name}: {relative_path}")
                    except OSError as e: # Catch OSError for file system errors
                        if e.errno == errno.ENOENT: # Error 2: No such file or directory
                            print(f"WARNING: {file_field_name} file not found during default_storage.delete() (errno 2). It might have been deleted by another process. Path: {relative_path}")
                        else:
                            print(f"ERROR: Failed to delete {file_field_name} file ({relative_path}): {e}")
                    except Exception as e:
                        print(f"ERROR: Unexpected error during deletion of {file_field_name} file ({relative_path}): {e}")
                else:
                    print(f"WARNING: {file_field_name} file does NOT EXIST on disk at: {absolute_file_path}. Skipping deletion.")

            # --- Handle Main Profile Picture ---
            # Scenario 1: New main profile picture file was uploaded directly (from mainProfilePic area)
            if 'profile_picture_file' in request.FILES:
                # Delete old profile picture if it exists and is a file, BUT NOT if it's the default
                if profile_instance.profile_picture and profile_instance.profile_picture.name != settings.DEFAULT_PROFILE_PICTURE_PATH:
                    delete_file_safely('old profile picture', profile_instance.profile_picture)
                profile_instance.profile_picture = request.FILES['profile_picture_file']
                profile_instance.main_additional_image = None # Disassociate from any ProfileImage
            # Scenario 2: An existing gallery image was promoted to main
            elif 'main_image_id' in request.POST and request.POST['main_image_id']:
                main_image_id = request.POST.get('main_image_id')
                try:
                    gallery_img_as_main = ProfileImage.objects.get(id=main_image_id, user_profile=user_profile)

                    # Delete old profile picture ONLY if it's different from the one being promoted
                    # AND the old one is not the default image path.
                    if profile_instance.profile_picture and \
                       profile_instance.profile_picture.name != gallery_img_as_main.image.name and \
                       profile_instance.profile_picture.name != settings.DEFAULT_PROFILE_PICTURE_PATH:
                        delete_file_safely('old profile picture (when promoting gallery image)', profile_instance.profile_picture)

                    profile_instance.profile_picture = gallery_img_as_main.image
                    profile_instance.main_additional_image = gallery_img_as_main
                except ProfileImage.DoesNotExist:
                    return JsonResponse({'success': False, 'errors': {'main_image_id': ['Selected main image not found.']}}, status=400)
            else:
                # No new main image or main_image_id provided in POST.
                # This means the profile_picture field was not explicitly changed by a file upload
                # or promotion from gallery. Django form handles keeping the existing value.
                pass

            profile_instance.save() # Save the profile instance now (updates profile_picture and main_additional_image)

            # --- Handle Gallery Image Deletions ---
            images_to_delete_ids = [int(x) for x in request.POST.getlist('images_to_delete') if x.isdigit()]
            if images_to_delete_ids:
                images_to_delete = ProfileImage.objects.filter(id__in=images_to_delete_ids, user_profile=user_profile)
                for img in images_to_delete:
                    delete_file_safely('gallery image', img.image)
                images_to_delete.delete()

            # --- Handle New Gallery Image Uploads ---
            MAX_GALLERY_IMAGES = 20
            # Re-fetch user_profile to get the latest count after deletions, etc.
            user_profile.refresh_from_db()
            # Use direct query to get accurate count after database changes
            current_gallery_images_count = ProfileImage.objects.filter(user_profile=user_profile).count()
            next_order = current_gallery_images_count

            for key in request.FILES:
                if key.startswith('gallery_image_'):
                    # Check current count *again* right before adding to prevent exceeding limit
                    if ProfileImage.objects.filter(user_profile=user_profile).count() < MAX_GALLERY_IMAGES:
                        image_file = request.FILES[key]
                        try:
                            ProfileImage.objects.create(
                                user_profile=user_profile,
                                image=image_file,
                                order=next_order
                            )
                            next_order += 1
                        except Exception as e:
                            print(f"Error saving new gallery image {key}: {e}")
                    else:
                        print(f"Skipping upload for {key}: Max gallery images reached.")

            # IMPORTANT: Refresh user_profile one last time to get the absolute latest state of
            # main_additional_image and all related images before preparing the response.
            user_profile.refresh_from_db()

            # --- Start Revised Logic for Image Data Preparation (for AJAX response) ---
            updated_all_images_for_frontend = []

            current_main_profile_image_id_final = None
            if user_profile.main_additional_image:
                current_main_profile_image_id_final = user_profile.main_additional_image.id

            # Add the current main profile picture (whether direct upload or gallery-promoted)
            # This is specifically for the main display, NOT the gallery list, but keeping for completeness
            # This will be used by the frontend to update the main profile pic area
            if user_profile.profile_picture:
                updated_all_images_for_frontend.append({
                    'id': current_main_profile_image_id_final if current_main_profile_image_id_final else 'main_direct_upload',
                    'image__url': user_profile.profile_picture.url,
                    'is_main': True,
                    'is_new_file': False, # This flag is primarily for client-side tracking of new unsaved files
                    'order': -1,
                })

            # Add all additional images (from the gallery model)
            all_profile_images_for_response = ProfileImage.objects.filter(user_profile=user_profile).order_by('order', 'pk')
            for img in all_profile_images_for_response: # Do NOT filter out the main image here
                is_this_img_main_for_response = (current_main_profile_image_id_final == img.id)
                updated_all_images_for_frontend.append({
                    'id': img.id,
                    'image__url': img.image.url,
                    'is_main': is_this_img_main_for_response, # Correctly flag if it's the main one
                    'is_new_file': False,
                    'order': img.order,
                })
            # --- End Revised Logic for Image Data Preparation ---

            return JsonResponse({
                'success': True,
                'message': 'Profile saved successfully!',
                'profile_picture_url': user_profile.profile_picture.url if user_profile.profile_picture else '', # Ensure this is always returned
                'updated_gallery_data': updated_all_images_for_frontend,
                'redirect_url': str(reverse_lazy('accounts:profile'))
            })
        else:
            errors = {field: [str(error) for error in errors] for field, errors in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors}, status=400)
    except Exception as e:
        print(f"CRITICAL SERVER ERROR during ajax_profile_save: {e}")
        return JsonResponse({'success': False, 'message': f"An unexpected server error occurred: {e}", 'errors': {'server': [str(e)]}}, status=500)


# Homepage view function
def homepage_view(request):
    """The main landing page for the LOVENY app."""
    return render(request, 'accounts/homepage.html')


@login_required
def browse_profiles_view(request):
    """
    Allows the current user to browse other user profiles.
    Profiles are now categorized by their 'looking_for' type,
    filtered by current user's preferences, age range, and location.
    """
    current_user = request.user

    # Start with base queryset: exclude self, no empty usernames
    base_queryset = UserProfile.objects.exclude(id=current_user.id).exclude(Q(username__exact='') | Q(username__isnull=True))

    # Apply 'looking_for' and 'seeking' preferences based on the strict rules
    current_user_looking_for = current_user.looking_for
    current_user_seeking_gender = current_user.seeking

    # Filter by `looking_for` preference (strict matching)
    if current_user_looking_for == 'DATING':
        base_queryset = base_queryset.filter(looking_for='DATING')
    elif current_user_looking_for == 'HOOKUP':
        base_queryset = base_queryset.filter(looking_for='HOOKUP')
    elif current_user_looking_for == 'SEXCALL':
        base_queryset = base_queryset.filter(looking_for='SEXCALL')
    elif current_user_looking_for == 'SUGAR_DADDY':
        base_queryset = base_queryset.filter(looking_for='SUGAR_MUMMY')
    elif current_user_looking_for == 'SUGAR_MUMMY':
        base_queryset = base_queryset.filter(looking_for='SUGAR_DADDY')
    else:
        # Default fallback if user's 'looking_for' is not set or invalid
        # Show all relevant `looking_for` types but without specific gender filtering yet
        base_queryset = base_queryset.filter(looking_for__in=[choice[0] for choice in LOOKING_FOR_CHOICES])


    # Apply gender filtering based on current user's 'seeking' preference,
    # but only for DATING, HOOKUP, SEXCALL where direct gender seeking applies.
    if current_user_seeking_gender in ['M', 'F', 'O']:
        if current_user_looking_for in ['DATING', 'HOOKUP', 'SEXCALL']:
            base_queryset = base_queryset.filter(gender=current_user_seeking_gender)
        # Gender filtering for Sugar Daddy/Mummy is handled implicitly by the 'looking_for' filter.


    # Apply age filters
    min_age = request.GET.get('min_age')
    max_age = request.GET.get('max_age')
    location_filter = request.GET.get('location')

    today = timezone.now().date()

    if min_age:
        try:
            min_birth_date = today - timedelta(days=int(min_age) * 365.25)
            base_queryset = base_queryset.filter(date_of_birth__lte=min_birth_date)
        except ValueError:
            pass

    if max_age:
        try:
            max_birth_date = today - timedelta(days=(int(max_age) + 1) * 365.25)
            base_queryset = base_queryset.filter(date_of_birth__gte=max_birth_date)
        except ValueError:
            pass

    if location_filter:
        base_queryset = base_queryset.filter(location__iexact=location_filter)

    # Prepare categorized data
    categorized_profiles_data = {}

    # Define which categories to display headings for, based on current user's looking_for
    display_categories = []
    if current_user_looking_for == 'DATING':
        display_categories = [('DATING', 'Dating')]
    elif current_user_looking_for == 'HOOKUP':
        display_categories = [('HOOKUP', 'Hookup')]
    elif current_user_looking_for == 'SEXCALL':
        display_categories = [('SEXCALL', 'Sex Call')]
    elif current_user_looking_for == 'SUGAR_DADDY':
        display_categories = [('SUGAR_MUMMY', 'Sugar Mummy')] # Display "Sugar Mummy" category for a Sugar Daddy
    elif current_user_looking_for == 'SUGAR_MUMMY':
        display_categories = [('SUGAR_DADDY', 'Sugar Daddy')] # Display "Sugar Daddy" category for a Sugar Mummy
    else:
        # Fallback: if user's looking_for is not set, show all original categories for general Browse
        display_categories = LOOKING_FOR_CHOICES

    for choice_value, choice_display in display_categories:
        # Filter the already filtered base_queryset by the current looking_for type from the loop
        profiles_in_category = base_queryset.filter(looking_for=choice_value).order_by('-last_login')

        profiles_list = []
        for profile in profiles_in_category:
            if not profile.username:
                continue

            has_liked = Like.objects.filter(liker=current_user, liked_user=profile).exists()
            is_matched = Like.objects.filter(
                Q(liker=current_user, liked_user=profile) & Q(liker=profile, liked_user=current_user)
            ).exists()

            # Get all profile images for this user
            all_profile_images_urls = []
            if profile.profile_picture and profile.profile_picture.name != settings.DEFAULT_PROFILE_PICTURE_PATH:
                all_profile_images_urls.append(profile.profile_picture.url)

            # Add additional gallery images
            for img in ProfileImage.objects.filter(user_profile=profile).order_by('order', 'pk'):
                if img.image:
                    all_profile_images_urls.append(img.image.url)

            # If no images, ensure default avatar is explicitly added
            if not all_profile_images_urls:
                all_profile_images_urls.append(settings.STATIC_URL + settings.DEFAULT_PROFILE_PICTURE_PATH)

            # Generate WhatsApp link for this profile if matched and premium
            whatsapp_link_for_profile = None
            if is_matched and current_user.is_premium and profile.phone_number:
                user_profile_url = request.build_absolute_uri(reverse_lazy('accounts:view_user_profile', kwargs={'username': current_user.username}))
                clean_phone_number = profile.phone_number.replace(' ', '').replace('-', '')
                pre_filled_message = f"Hi {profile.first_name}! I found your profile on LOVENY. Here's my profile: {user_profile_url}"
                whatsapp_link_for_profile = f"https://wa.me/{clean_phone_number}?text={requests.utils.quote(pre_filled_message)}"

            profiles_list.append({
                'username': profile.username,
                'first_name': profile.first_name,
                'bio': profile.bio,
                'gender': profile.gender,
                'gender_display': profile.get_gender_display(),
                'seeking': profile.seeking,
                'seeking_display': profile.get_seeking_display(),
                'location': profile.location,
                'full_name': profile.get_full_name,
                'age': profile.get_age,
                'main_profile_picture': profile.profile_picture.url if profile.profile_picture else settings.STATIC_URL + settings.DEFAULT_PROFILE_PICTURE_PATH,
                'profile_pictures': all_profile_images_urls, # Pass all image URLs for cycler
                'is_premium': profile.is_premium,
                'last_login': profile.last_login.isoformat() if profile.last_login else None,
                'has_liked': has_liked,
                'is_matched': is_matched,
                'whatsapp_link': whatsapp_link_for_profile, # Pass WhatsApp link
                'profile_picture_name': profile.profile_picture.name if profile.profile_picture else '',
                'looking_for_display': profile.get_looking_for_display(),
            })

        # Only add the category to context if it has profiles
        if profiles_list:
            categorized_profiles_data[choice_display] = profiles_list

    context = {
        'categorized_profiles_data': categorized_profiles_data, # New context variable
        'user_profile': current_user,
        'min_age': min_age,
        'max_age': max_age,
        'location_filter': location_filter,
        'LOOKING_FOR_CHOICES': LOOKING_FOR_CHOICES, # Pass choices for filter dropdowns
    }
    return render(request, 'accounts/browse_profiles.html', context)


@login_required
def view_other_profile(request, username):
    """
    Displays a specific user's profile detail.
    Includes logic to generate a WhatsApp chat link ONLY if current_user is premium.
    Now also passes all profile images for the gallery, excluding the main one.
    """
    current_user = request.user
    profile = get_object_or_404(UserProfile, username=username)

    if profile == current_user:
        return redirect('accounts:profile')

    has_liked = Like.objects.filter(liker=current_user, liked_user=profile).exists()
    is_matched = Like.objects.filter(
        Q(liker=current_user, liked_user=profile) & Q(liker=profile, liked_user=current_user)
    ).exists()

    whatsapp_link = None
    if current_user.is_premium and profile.phone_number:
        user_profile_url = request.build_absolute_uri(reverse_lazy('accounts:view_user_profile', kwargs={'username': current_user.username}))
        clean_phone_number = profile.phone_number.replace(' ', '').replace('-', '')
        pre_filled_message = f"Hi {profile.first_name}! I found your profile on LOVENY. Here's my profile: {user_profile_url}"
        whatsapp_link = f"https://wa.me/{clean_phone_number}?text={requests.utils.quote(pre_filled_message)}"
    elif not current_user.is_premium:
        pass

    # --- Start Revised Logic for Gallery Images ---
    gallery_images = []
    main_profile_image_id = None
    if profile.main_additional_image:
        main_profile_image_id = profile.main_additional_image.id

    # Iterate through all ProfileImage objects.
    # Add them to gallery_images ONLY if they are not the currently set main_additional_image.
    # This avoids duplicating the main profile picture within the gallery if it's from the gallery.
    for img_obj in ProfileImage.objects.filter(user_profile=profile).order_by('order', 'pk'):
        # Ensure the image file actually exists and it's not the one explicitly set as the main display image.
        if img_obj.image and (main_profile_image_id is None or img_obj.id != main_profile_image_id):
              gallery_images.append(img_obj.image) # Append the actual ImageField file

    # --- End Revised Logic ---

    context = {
        'profile': profile, # Keep the full profile object for detailed views
        'has_liked': has_liked,
        'is_matched': is_matched,
        'whatsapp_link': whatsapp_link,
        'all_profile_images': gallery_images, # Passed to template
    }
    return render(request, 'accounts/other_profile_detail.html', context)


@login_required
def like_view(request, username):
    """Handles the 'like' and 'unlike' actions."""
    if request.method == 'POST':
        liker = request.user
        liked_user = get_object_or_404(UserProfile, username=username)

        if liker == liked_user:
            return JsonResponse({'status': 'error', 'message': 'Cannot like your own profile.'})

        like_instance_query = Like.objects.filter(liker=liker, liked_user=liked_user)
        
        action_performed = 'none' # Track if like/unlike happened

        # Use a transaction to ensure atomicity for like creation/deletion and notification creation
        with transaction.atomic():
            if like_instance_query.exists():
                like_instance_query.delete()
                action_performed = 'unliked'
                # Optional: Delete corresponding 'LIKE' notification if unliked
                # Notification.objects.filter(
                #    recipient=liked_user,
                #    sender=liker,
                #    notification_type='like', # Changed from NotificationType.LIKE
                #    is_read=False # Only delete if not already read
                # ).delete()
            else:
                Like.objects.create(liker=liker, liked_user=liked_user)
                action_performed = 'liked'

                # Create a notification for the liked user
                Notification.objects.create(
                    recipient=liked_user,
                    sender=liker,
                    notification_type='like', # Changed from NotificationType.LIKE
                    message=f"{liker.username} liked your profile!"
                )
                print(f"Notification created: {liker.username} liked {liked_user.username}")


                # Check for mutual like (match) *after* the new like is created
                if Like.objects.filter(liker=liked_user, liked_user=liker).exists():
                    # A match occurred!
                    print(f"MATCH! {liker.username} and {liked_user.username}")
                    # Create a notification for the current user (liker) about the match
                    Notification.objects.create(
                        recipient=liker,
                        sender=liked_user,
                        notification_type='match', # Changed from NotificationType.MATCH
                        message=f"You have a new match with {liked_user.username}!"
                    )
                    # Create a notification for the liked user about the match
                    Notification.objects.create(
                        recipient=liked_user,
                        sender=liker,
                        notification_type='match', # Changed from NotificationType.MATCH
                        message=f"You have a new match with {liker.username}!"
                    )


        # Recalculate has_liked and is_matched based on current state
        has_liked_after_action = Like.objects.filter(liker=liker, liked_user=liked_user).exists()
        is_matched_after_action = (
            Like.objects.filter(liker=liker, liked_user=liked_user).exists() and
            Like.objects.filter(liker=liked_user, liked_user=liker).exists()
        )

        # Prepare WhatsApp link (only if matched and target has phone number)
        whatsapp_link = None
        # Only generate whatsapp_link if the current user (liker) is premium AND a match occurred
        if is_matched_after_action and liker.is_premium and liked_user.phone_number:
            # Construct a URL for the current user's profile to send in WhatsApp message
            current_user_profile_url = request.build_absolute_uri(reverse_lazy('accounts:view_user_profile', kwargs={'username': liker.username}))
            clean_phone_number = liked_user.phone_number.replace(' ', '').replace('-', '')
            pre_filled_message = f"Hi {liked_user.first_name}! I found your profile on LOVENY. Here's my profile: {current_user_profile_url}"
            whatsapp_link = f"https://wa.me/{clean_phone_number}?text={requests.utils.quote(pre_filled_message)}"


        # Always return JSON response for AJAX requests
        return JsonResponse({
            'status': 'ok',
            'message': 'Like status updated',
            'action': action_performed, # 'liked' or 'unliked'
            'has_liked': has_liked_after_action,
            'is_matched': is_matched_after_action,
            'whatsapp_link': whatsapp_link, # Will be null if not matched or not premium
        })