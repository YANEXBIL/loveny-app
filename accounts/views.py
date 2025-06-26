from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
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


# Import all models and forms
from .forms import CustomUserCreationForm, UserProfileForm
from .models import UserProfile, Like, SubscriptionPlan, UserSubscription, ProfileImage, PaymentTransaction, LOOKING_FOR_CHOICES # Import LOOKING_FOR_CHOICES


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


@login_required
def profile_view(request):
    """Displays the current logged-in user's profile."""
    user_profile = request.user
    return render(request, 'accounts/profile.html', {'user_profile': user_profile})


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
        # This prevents duplicating a gallery image that's also the main one in the initial load list
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
    # For Sugar Daddy/Mummy, gender is implicitly defined by the 'looking_for' target.
    if current_user_seeking_gender in ['M', 'F', 'O']:
        if current_user_looking_for in ['DATING', 'HOOKUP', 'SEXCALL']:
            base_queryset = base_queryset.filter(gender=current_user_seeking_gender)
        # Note: For Sugar Daddy/Mummy, the gender filter is implicitly handled by the
        # `looking_for` filter above. E.g., if you're a Sugar Daddy (seeking Mummies),
        # you'll only see F profiles. If you're a Sugar Mummy (seeking Daddies),
        # you'll only see M profiles.


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
        # Fallback: if user's looking_for is not set, show all original categories for general browsing
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
                'profile_picture_name': profile.profile_picture.name if profile.profile_picture else '',
                'looking_for_display': profile.get_looking_for_display, 
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
            return redirect('accounts:browse_profiles') 

        like_instance_query = Like.objects.filter(liker=liker, liked_user=liked_user)

        if like_instance_query.exists():
            like_instance_query.delete()
        else:
            Like.objects.create(liker=liker, liked_user=liked_user)
            if Like.objects.filter(liker=liked_user, liked_user=liker).exists():
                pass 

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # After a like/unlike, we need to refresh the state for the profile
            # to be reflected on the front end without a full page reload.
            # This logic will be handled by the AJAX response, which then
            # updates the specific card.
            has_liked_after_action = Like.objects.filter(liker=liker, liked_user=liked_user).exists()
            is_matched_after_action = Like.objects.filter(
                Q(liker=liker, liked_user=liked_user) & Q(liker=liked_user, liked_user=liker)
            ).exists()
            return JsonResponse({
                'status': 'ok',
                'message': 'Like status updated',
                'username': username, # Return username to identify the card to update
                'has_liked': has_liked_after_action,
                'is_matched': is_matched_after_action,
            })
        return redirect('accounts:browse_profiles')
    return redirect('accounts:browse_profiles')


@login_required
def matches_view(request):
    """Displays matches for the current user."""
    current_user = request.user
    matches_as_liker = Like.objects.filter(
        liker=current_user, liked_user__in=Like.objects.filter(liked_user=current_user).values('liker')
    ).select_related('liked_user')

    matched_profiles = []
    for profile in [match.liked_user for match in matches_as_liker]:
        if not profile.username: # Ensure username exists before adding
            print(f"Skipping matched profile with empty username (ID: {profile.id}) in matches_view.")
            continue
        matched_profiles.append({
            'profile_obj': profile, # Still keep obj for matches template direct access
            'username': profile.username,
            'first_name': profile.first_name, # Added first_name
            'profile_picture_url': profile.profile_picture.url if profile.profile_picture else settings.STATIC_URL + settings.DEFAULT_PROFILE_PICTURE_PATH,
            'get_age': profile.get_age, # Access as property
            'bio': profile.bio,
            'is_premium': profile.is_premium,
            'last_login': profile.last_login.isoformat() if profile.last_login else None,
        })


    context = {
        'matched_profiles': matched_profiles,
    }
    return render(request, 'accounts/matches.html', context)

@login_required
def swipe_profiles_view(request):
    """
    Provides a Tinder-like swiping interface for profiles.
    Only shows profiles the user hasn't already liked or disliked.
    Filters profiles based on the current user's 'looking_for' preference, gender preferences,
    and new filters: age range and location.
    """
    current_user = request.user

    # Get IDs of profiles the current user has already liked
    liked_profile_ids = Like.objects.filter(liker=current_user).values_list('liked_user__id', flat=True)

    # Start with all other profiles, excluding self, already liked, and those with empty usernames
    queryset = UserProfile.objects.exclude(id=current_user.id).exclude(id__in=liked_profile_ids).exclude(Q(username__exact='') | Q(username__isnull=True))

    # Apply 'looking_for' and 'seeking' preferences based on the strict rules
    current_user_looking_for = current_user.looking_for 
    current_user_seeking_gender = current_user.seeking

    # Filter by `looking_for` preference (strict matching)
    if current_user_looking_for == 'DATING':
        queryset = queryset.filter(looking_for='DATING')
    elif current_user_looking_for == 'HOOKUP':
        queryset = queryset.filter(looking_for='HOOKUP')
    elif current_user_looking_for == 'SEXCALL':
        queryset = queryset.filter(looking_for='SEXCALL')
    elif current_user_looking_for == 'SUGAR_DADDY':
        queryset = queryset.filter(looking_for='SUGAR_MUMMY')
    elif current_user_looking_for == 'SUGAR_MUMMY':
        queryset = queryset.filter(looking_for='SUGAR_DADDY')
    else:
        # Default fallback if user's 'looking_for' is not set or invalid
        queryset = queryset.filter(looking_for__in=[choice[0] for choice in LOOKING_FOR_CHOICES])


    # Apply gender filtering based on current user's 'seeking' preference,
    # but only for DATING, HOOKUP, SEXCALL where direct gender seeking applies.
    if current_user_seeking_gender in ['M', 'F', 'O']:
        if current_user_looking_for in ['DATING', 'HOOKUP', 'SEXCALL']:
            queryset = queryset.filter(gender=current_user_seeking_gender)


    # --- Apply new filters (Age, Location) ---
    min_age = request.GET.get('min_age')
    max_age = request.GET.get('max_age')
    location_filter = request.GET.get('location')

    today = timezone.now().date()

    if min_age:
        try:
            min_birth_date = today - timedelta(days=int(min_age) * 365.25) # Approximate days per year
            queryset = queryset.filter(date_of_birth__lte=min_birth_date)
        except ValueError:
            pass # Invalid age, ignore filter

    if max_age:
        try:
            max_birth_date = today - timedelta(days=(int(max_age) + 1) * 365.25) # +1 to make it inclusive
            queryset = queryset.filter(date_of_birth__gte=max_birth_date)
        except ValueError:
            pass # Invalid age, ignore filter

    if location_filter:
        queryset = queryset.filter(location__iexact=location_filter)

    profiles_to_swipe = queryset.order_by('?')[:10] # Limit to 10 random profiles for swiping

    profiles_data = []
    for profile in profiles_to_swipe:
        # Explicitly check for non-empty username before adding to data for template
        if not profile.username:
            print(f"Skipping profile with empty username (ID: {profile.id}) in swipe_profiles_view.")
            continue

        all_profile_images_urls = []
        # Ensure profile.profile_picture is always included if it exists and is not the default
        if profile.profile_picture and profile.profile_picture.name != settings.DEFAULT_PROFILE_PICTURE_PATH:
            all_profile_images_urls.append(profile.profile_picture.url)
        
        # Add all additional images (from the gallery model)
        for img in ProfileImage.objects.filter(user_profile=profile).order_by('order', 'pk'):
            if img.image: # Only add if image file exists
                all_profile_images_urls.append(img.image.url)

        # If no images found (or only default), ensure default avatar is explicitly added to the list
        if not all_profile_images_urls:
            all_profile_images_urls.append(settings.STATIC_URL + settings.DEFAULT_PROFILE_PICTURE_PATH)


        # IMPORTANT: Prepare a flat dictionary for the template to directly consume
        profiles_data.append({
            'username': profile.username,
            'first_name': profile.first_name, 
            'bio': profile.bio, 
            'gender': profile.gender,
            'gender_display': profile.get_gender_display(), 
            'seeking': profile.seeking, 
            'seeking_display': profile.get_seeking_display(), 
            'location': profile.location, 
            'full_name': profile.get_full_name, 
            'interests': profile.interests if hasattr(profile, 'interests') else [],
            'age': profile.get_age, 
            'main_profile_picture': profile.profile_picture.url if profile.profile_picture else settings.STATIC_URL + settings.DEFAULT_PROFILE_PICTURE_PATH,
            'profile_pictures': all_profile_images_urls, # Passed as a list for image cycler
            'is_premium': profile.is_premium, 
            'last_login': profile.last_login.isoformat() if profile.last_login else None,
            'profile_picture_name': profile.profile_picture.name if profile.profile_picture else ''
        })

    context = {
        'profiles_json': json.dumps(profiles_data)
    }
    return render(request, 'accounts/swipe_profiles.html', context)


@login_required
def subscription_plans_view(request):
    """Displays available subscription plans."""
    plans = SubscriptionPlan.objects.all().order_by('price')
    context = {
        'plans': plans
    }
    return render(request, 'accounts/subscription_plans.html', context)


@login_required
def initiate_payment_view(request, plan_id): # This view now expects plan_id in the URL
    """Initiates payment with Paystack for a selected subscription plan."""
    print(f"--- initiate_payment_view called for plan_id: {plan_id} ---") # DEBUG
    plan = get_object_or_404(SubscriptionPlan, id=plan_id)
    user = request.user

    # Generate a unique reference for the transaction
    # It's good practice to ensure this is truly unique, e.g., using UUID
    ref = f'LOVENY-{user.id}-{plan.id}-{timezone.now().timestamp()}'

    # Create a pending payment transaction record in your database
    transaction_obj = PaymentTransaction.objects.create(
        user=user,
        plan=plan,
        amount=plan.price,
        reference=ref,
        status='pending'
    )
    print(f"DEBUG: Created pending transaction: {transaction_obj.reference}")

    # Prepare Paystack API request
    # Paystack amount is in kobo (smallest currency unit), so multiply by 100
    amount_kobo = int(plan.price * 100) 
    callback_url = request.build_absolute_uri(reverse_lazy('accounts:paystack_callback'))
    
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'email': user.email,
        'amount': amount_kobo,
        'reference': ref,
        'callback_url': callback_url,
        'metadata': {
            'plan_id': plan.id,
            'user_id': user.id,
            'custom_fields': [
                {'display_name': "Plan Name", "variable_name": "plan_name", "value": plan.name},
                {'display_name': "User Username", "variable_name": "user_username", "value": user.username},
            ]
        }
    }
    
    PAYSTACK_INITIATE_URL = "https://api.paystack.co/transaction/initialize"
    
    print(f"DEBUG: Sending initiation request to Paystack for ref: {ref}")
    try:
        response = requests.post(PAYSTACK_INITIATE_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        paystack_data = response.json()
        print(f"DEBUG: Paystack initiation response: {paystack_data}")

        if paystack_data['status'] and paystack_data['data']['authorization_url']:
            # Update transaction with gateway response (optional, but good for debugging)
            transaction_obj.gateway_response = paystack_data
            transaction_obj.save(update_fields=['gateway_response'])
            return redirect(paystack_data['data']['authorization_url'])
        else:
            print(f"ERROR: Paystack initiation failed: {paystack_data.get('message', 'No message from Paystack')}")
            messages.error(request, f"Payment initiation failed: {paystack_data.get('message', 'Please try again.')}")
            transaction_obj.status = 'failed'
            transaction_obj.gateway_response = paystack_data
            transaction_obj.save(update_fields=['status', 'gateway_response'])
            return redirect('accounts:subscription_plans')

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network or Paystack API error during initiation: {e}")
        messages.error(request, f"Payment initiation failed due to a network error: {e}")
        transaction_obj.status = 'failed'
        transaction_obj.gateway_response = {'error': str(e)}
        transaction_obj.save(update_fields=['status', 'gateway_response'])
        return redirect('accounts:subscription_plans')
    except Exception as e:
        print(f"CRITICAL ERROR: Unexpected error in initiate_payment_view: {e}")
        messages.error(request, f"An unexpected error occurred during payment initiation: {e}")
        transaction_obj.status = 'failed'
        transaction_obj.gateway_response = {'error': str(e)}
        transaction_obj.save(update_fields=['status', 'gateway_response'])
        return redirect('accounts:subscription_plans')

@transaction.atomic
def paystack_callback_view(request):
    """Handles the callback from Paystack after a transaction."""
    print("--- paystack_callback_view called ---") # DEBUG
    reference = request.GET.get('reference')
    if not reference:
        messages.error(request, "Payment verification failed: No transaction reference provided.")
        return redirect('accounts:subscription_plans')

    try:
        # Verify the transaction with Paystack
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        }
        PAYSTACK_VERIFY_URL = f"https://api.paystack.co/transaction/verify/{reference}"
        print(f"DEBUG: Verifying transaction with Paystack for ref: {reference}")
        response = requests.get(PAYSTACK_VERIFY_URL, headers=headers)
        response.raise_for_status()
        paystack_data = response.json()
        print(f"DEBUG: Paystack verification response: {paystack_data}")

        if paystack_data['status'] and paystack_data['data']['status'] == 'success':
            # Find the local transaction record
            transaction_obj = get_object_or_404(PaymentTransaction, reference=reference)
            
            if transaction_obj.status == 'success':
                messages.info(request, "This payment has already been processed.")
                return redirect('accounts:profile')

            # Mark transaction as successful
            transaction_obj.status = 'success'
            transaction_obj.gateway_response = paystack_data
            transaction_obj.save(update_fields=['status', 'gateway_response'])
            print(f"DEBUG: Transaction {reference} marked as success locally.")

            # Activate or update user's subscription
            user = transaction_obj.user
            plan = transaction_obj.plan
            
            user_subscription, created = UserSubscription.objects.get_or_create(user=user)
            
            # If the user already has an active subscription, extend it
            if user_subscription.is_active and user_subscription.end_date and user_subscription.end_date > timezone.now():
                user_subscription.end_date += timedelta(days=plan.duration_days)
                messages.success(request, f"Your {plan.name} subscription has been extended! Expires: {user_subscription.end_date.strftime('%Y-%m-%d')}")
                print(f"DEBUG: User {user.username} subscription extended.")
            else:
                # New subscription or old one expired/inactive
                user_subscription.plan = plan
                user_subscription.start_date = timezone.now()
                user_subscription.end_date = timezone.now() + timedelta(days=plan.duration_days)
                user_subscription.is_active = True
                messages.success(request, f"Congratulations! Your {plan.name} subscription is now active! Expires: {user_subscription.end_date.strftime('%Y-%m-%d')}")
                print(f"DEBUG: User {user.username} new subscription activated.")
            
            user_subscription.save()

            # Set user to premium
            user.is_premium = True
            user.premium_expiry_date = user_subscription.end_date
            user.save(update_fields=['is_premium', 'premium_expiry_date'])
            print(f"DEBUG: User {user.username} set to premium until {user.premium_expiry_date}.")

            return redirect('accounts:profile') # Redirect to profile page on success

        else:
            # Payment not successful or verification failed
            print(f"ERROR: Paystack verification failed or status not 'success' for ref {reference}. Details: {paystack_data}")
            transaction_obj = get_object_or_404(PaymentTransaction, reference=reference)
            transaction_obj.status = 'failed'
            transaction_obj.gateway_response = paystack_data
            transaction_obj.save(update_fields=['status', 'gateway_response'])
            messages.error(request, f"Payment verification failed: {paystack_data['data'].get('gateway_response', 'Unknown error.')}")
            return redirect('accounts:subscription_plans')

    except PaymentTransaction.DoesNotExist:
        messages.error(request, "Payment verification failed: Transaction record not found.")
        print(f"ERROR: Local transaction record not found for reference: {reference}")
        return redirect('accounts:subscription_plans')
    except requests.exceptions.RequestException as e:
        messages.error(request, f"Payment verification failed due to a network error: {e}")
        print(f"ERROR: Network or Paystack API error during verification: {e}")
        return redirect('accounts:subscription_plans')
    except Exception as e:
        messages.error(request, f"An unexpected error occurred during payment verification: {e}")
        print(f"CRITICAL ERROR: Unexpected error in paystack_callback_view: {e}")
        return redirect('accounts:subscription_plans')

