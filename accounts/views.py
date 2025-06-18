# accounts/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout # Import login/logout functions
from django.contrib.auth.decorators import login_required # Decorator for requiring login
from django.contrib.auth.views import LoginView, LogoutView # Class-based login/logout views
from django.views.generic import CreateView, UpdateView, DetailView # Generic views for common tasks
from django.urls import reverse_lazy # For redirecting to a URL by name
from django.http import JsonResponse, HttpResponse # For AJAX responses and general HTTP responses
from django.db.models import Q # For complex queries
from django.conf import settings # Import settings to access API keys
import requests # For making HTTP requests to Paystack API
import json # For handling JSON responses
import os # Import os for os.urandom
from django.contrib import messages # Import messages framework
from datetime import timedelta # Import timedelta for date calculations

# Import all models and forms
from .forms import CustomUserCreationForm, UserProfileForm
from .models import UserProfile, Like, Conversation, Message, SubscriptionPlan, UserSubscription, PaymentTransaction


class CustomLoginView(LoginView):
    """
    Custom login view using Django's built-in LoginView.
    """
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True # Redirect logged-in users away from the login page


class CustomLogoutView(LogoutView):
    """
    Custom logout view using Django's built-in LogoutView.
    This class handles the logout process. By default, Django's LogoutView
    expects a POST request to log out for security reasons (CSRF protection).
    The `next_page` attribute specifies where to redirect after a successful logout.
    """
    next_page = reverse_lazy('login') # Redirect to login page after logout


class SignUpView(CreateView):
    """
    View for user registration (sign up).
    Uses CustomUserCreationForm to handle user creation.
    """
    form_class = CustomUserCreationForm
    template_name = 'accounts/registration_form.html'
    success_url = reverse_lazy('profile_edit') # Changed: Redirect to user's profile edit page after successful registration

    def form_valid(self, form):
        """
        Logs in the user after successful registration.
        """
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

@login_required # Ensures only logged-in users can access this view
def profile_view(request):
    """
    Displays the current logged-in user's profile.
    """
    user_profile = request.user # The UserProfile object is directly available via request.user
    return render(request, 'accounts/profile.html', {'user_profile': user_profile})


@login_required # Ensures only logged-in users can access this view
def profile_edit_view(request):
    """
    Allows the current logged-in user to edit their profile.
    Handles both GET (display form) and POST (process form submission) requests.
    """
    user_profile = request.user
    if request.method == 'POST':
        # request.FILES is needed for handling profile picture uploads
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            return redirect('profile') # Redirect to profile view after successful update
    else:
        form = UserProfileForm(instance=user_profile) # Pre-fill form with existing data
    return render(request, 'accounts/profile_edit.html', {'form': form})


def homepage_view(request):
    """
    The main landing page for the LOVENY app.
    Can show a general welcome or direct to login/signup.
    """
    return render(request, 'accounts/homepage.html')


@login_required
def browse_profiles_view(request):
    """
    Allows the current user to browse other user profiles.
    This view also calculates if the current user has liked a profile
    and if there's a mutual match for each browsable profile.
    Profiles are filtered based on the current user's 'user_type'.
    """
    current_user = request.user

    # Start with all profiles except the current user's
    other_profiles = UserProfile.objects.exclude(id=current_user.id)

    # Filter profiles based on the current user's user_type
    current_user_seeking = current_user.user_type

    if current_user_seeking == 'DATING':
        # Dating users see other dating users
        other_profiles = other_profiles.filter(user_type='DATING')
    elif current_user_seeking == 'HOOKUP':
        # Hookup users see other hookup users
        other_profiles = other_profiles.filter(user_type='HOOKUP')
    elif current_user_seeking == 'SUGAR_DADDY':
        # Sugar Daddies see Sugar Mummies or potentially Dating profiles
        other_profiles = other_profiles.filter(Q(user_type='SUGAR_MUMMY') | Q(user_type='DATING'))
    elif current_user_seeking == 'SUGAR_MUMMY':
        # Sugar Mummies see Sugar Daddies or potentially Dating profiles
        other_profiles = other_profiles.filter(Q(user_type='SUGAR_DADDY') | Q(user_type='DATING'))

    # Prepare data for each profile to indicate like status and match status
    profiles_data = []
    for profile in other_profiles:
        # Check if the current user has liked this profile
        has_liked = Like.objects.filter(liker=current_user, liked_user=profile).exists()

        # Check if there is a mutual match
        is_matched = Like.objects.filter(
            Q(liker=current_user, liked_user=profile) & Q(liker=profile, liked_user=current_user)
        ).exists()

        profiles_data.append({
            'profile': profile,
            'has_liked': has_liked,
            'is_matched': is_matched,
        })

    context = {
        'profiles_data': profiles_data, # Pass the list of dictionaries
        'current_user_type': current_user.get_user_type_display(),
    }
    return render(request, 'accounts/browse_profiles.html', context)


@login_required
def view_other_profile(request, username):
    """
    Displays a specific user's profile detail.
    Also calculates if the current user has liked this profile and if it's a match.
    """
    current_user = request.user
    profile = get_object_or_404(UserProfile, username=username)

    # Prevent users from viewing their own profile via this URL
    if profile == current_user:
        return redirect('profile')

    # Check like and match status
    has_liked = Like.objects.filter(liker=current_user, liked_user=profile).exists()
    is_matched = Like.objects.filter(
        Q(liker=current_user, liked_user=profile) & Q(liker=profile, liked_user=current_user)
    ).exists()

    context = {
        'profile': profile,
        'has_liked': has_liked,
        'is_matched': is_matched,
    }
    return render(request, 'accounts/other_profile_detail.html', context)


@login_required
def like_view(request, username):
    """
    Handles the 'like' and 'unlike' actions via POST request.
    If the current user likes another user, a Like object is created.
    If they click 'Like' again (i.e., they already liked), it 'unlikes' (deletes the Like object).
    Returns a JSON response indicating the status (liked, unliked, matched).
    """
    if request.method == 'POST':
        liker = request.user
        liked_user = get_object_or_404(UserProfile, username=username)

        # Prevent a user from liking themselves
        if liker == liked_user:
            messages.error(request, "You cannot like your own profile!")
            return redirect('browse_profiles')

        # Check if a like already exists from liker to liked_user
        like_instance_query = Like.objects.filter(liker=liker, liked_user=liked_user)

        if like_instance_query.exists():
            # If like exists, it means the user is 'unliking'
            like_instance_query.delete()
            status = 'unliked'
            messages.info(request, f'You unliked {liked_user.username}.')
            # No longer matched if a like is removed
            is_currently_matched = False
        else:
            # If no like exists, create one
            Like.objects.create(liker=liker, liked_user=liked_user)
            status = 'liked'
            messages.success(request, f'You liked {liked_user.username}.')

            # After creating a like, check if the liked_user has also liked the liker
            is_currently_matched = Like.objects.filter(liker=liked_user, liked_user=liker).exists()
            if is_currently_matched:
                status = 'matched'
                messages.success(request, f'It\'s a MATCH with {liked_user.username}!')

        # For simplicity, we are redirecting back to the browse page.
        # In a real app, you might use JavaScript to update the UI without a full page reload.
        return redirect('browse_profiles') # Redirect back to the browse page

    # If the request is not a POST (e.g., direct access), redirect to browse
    return redirect('browse_profiles')


@login_required
def matches_view(request):
    """
    Displays a list of mutual matches for the current user.
    A mutual match exists when user A likes user B AND user B likes user A.
    """
    current_user = request.user

    # Find all 'Like' objects where current_user is the liker
    likes_given = current_user.likes_given.all() # Use .all() to get queryset

    # Find all 'Like' objects where current_user is the liked_user
    likes_received = current_user.likes_received.all() # Use .all() to get queryset

    # Get the IDs of users who liked the current user AND were liked by the current user
    mutual_match_ids = set()
    for like_g in likes_given:
        # Check if the user we liked has also liked us
        if likes_received.filter(liker=like_g.liked_user).exists(): # Simplified check
            mutual_match_ids.add(like_g.liked_user.id) # Add the ID of the matched user

    # Retrieve the UserProfile objects for these mutual matches
    matches = UserProfile.objects.filter(id__in=list(mutual_match_ids)).order_by('username')

    # Categorize matches (if needed, otherwise just pass 'matches')
    categorized_matches = {
        'DATING': [],
        'HOOKUP': [],
        'SUGAR_DADDY': [],
        'SUGAR_MUMMY': [],
    }

    for match_profile in matches:
        if match_profile.user_type in categorized_matches:
            categorized_matches[match_profile.user_type].append(match_profile)

    context = {
        'dating_matches': categorized_matches['DATING'],
        'hookup_matches': categorized_matches['HOOKUP'],
        'sugar_daddy_matches': categorized_matches['SUGAR_DADDY'],
        'sugar_mummy_matches': categorized_matches['SUGAR_MUMMY'],
        'has_any_matches': bool(matches.exists()), # Check if any matches exist
        'matches': matches, # Also pass the combined list for simpler rendering if needed
    }
    return render(request, 'accounts/matches.html', context)


@login_required
def chat_room_view(request, username):
    """
    Renders the chat room for a conversation between the current user and 'username'.
    Ensures a conversation exists and fetches its messages.
    """
    current_user = request.user
    other_user = get_object_or_404(UserProfile, username=username)

    # Prevent current user from chatting with themselves via this page
    if current_user == other_user:
        return redirect('profile')

    # Get or create the conversation. The Conversation model's class method
    # handles ordering users to ensure uniqueness.
    conversation, created = Conversation.get_or_create_conversation(current_user, other_user)

    # Fetch all messages for this conversation, ordered by timestamp
    messages = Message.objects.filter(conversation=conversation).order_by('timestamp')

    context = {
        'other_user': other_user,
        'conversation_id': conversation.id,
        'messages': messages,
    }
    return render(request, 'accounts/chat_room.html', context)


@login_required
def message_gate_view(request, username):
    """
    Acts as a gate for initiating chat. If the current user is not premium,
    it redirects to the subscription page with a message. Otherwise, it
    redirects to the actual chat room.
    """
    other_user = get_object_or_404(UserProfile, username=username)
    current_user = request.user

    if current_user == other_user:
        # User trying to message themselves, redirect to their profile
        return redirect('profile')

    if not current_user.is_premium:
        messages.info(request, "Please upgrade to a premium plan to message other users!")
        return redirect('subscription_plans')
    else:
        # If premium, redirect to the actual chat room
        return redirect('chat_room', username=username)

@login_required
def swipe_profiles_view(request):
    """
    Displays a single profile for the user to swipe left (dislike) or right (like).
    Fetches the next available profile that the current user hasn't already interacted with.
    Renders a full page on initial load, but only a partial profile card via AJAX.
    """
    current_user = request.user

    # Get IDs of profiles the current user has already interacted with (liked or received likes from that resulted in a match)
    interacted_profile_ids = set(
        Like.objects.filter(liker=current_user).values_list('liked_user__id', flat=True)
    )
    interacted_profile_ids.update(
        Like.objects.filter(liked_user=current_user).values_list('liker__id', flat=True)
    )

    # Filter profiles:
    # 1. Exclude the current user
    # 2. Exclude profiles the current user has already interacted with
    candidate_profiles = UserProfile.objects.exclude(id=current_user.id).exclude(id__in=list(interacted_profile_ids))

    # Apply user_type filtering for swipe (similar to browse_profiles_view)
    current_user_seeking = current_user.user_type
    if current_user_seeking == 'DATING':
        candidate_profiles = candidate_profiles.filter(user_type='DATING')
    elif current_user_seeking == 'HOOKUP':
        candidate_profiles = candidate_profiles.filter(user_type='HOOKUP')
    elif current_user_seeking == 'SUGAR_DADDY':
        candidate_profiles = candidate_profiles.filter(Q(user_type='SUGAR_MUMMY') | Q(user_type='DATING'))
    elif current_user_seeking == 'SUGAR_MUMMY':
        candidate_profiles = candidate_profiles.filter(Q(user_type='SUGAR_DADDY') | Q(user_type='DATING'))

    next_profile = candidate_profiles.order_by('?').first() # Get a random profile from the filtered set

    context = {
        'profile': next_profile,
        'current_user': current_user # Pass current user for template logic (e.g., VIP badge)
    }

    # Check if the request is an AJAX request
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # If AJAX, render only the partial template for the profile card
        return render(request, 'accounts/includes/profile_card_partial.html', context)
    else:
        # If not AJAX (initial page load), render the full swipe_profiles.html
        return render(request, 'accounts/swipe_profiles.html', context)


# --- Payment Views ---

@login_required
def subscription_plans_view(request):
    """
    Displays available subscription plans.
    """
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    context = {
        'plans': plans
    }
    return render(request, 'accounts/subscription_plans.html', context)


@login_required
def initiate_payment_view(request, plan_id):
    """
    Initiates a payment process with Paystack for a selected subscription plan.
    """
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    user = request.user

    # Paystack requires amount in kobo (NGN * 100)
    amount_kobo = int(plan.price * 100)

    # --- DEBUGGING: Print the calculated amount and user email ---
    print(f"DEBUG: Initializing Paystack payment for user: {user.email}, amount: {plan.price} NGN ({amount_kobo} kobo)")
    # --- END DEBUGGING ---

    # Prepare Paystack API request for transaction initialization
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    # Generate a unique reference for the transaction
    reference = f"loveny_{user.id}_{plan.id}_{os.urandom(4).hex()}"

    payload = {
        "email": user.email,
        "amount": amount_kobo,
        "reference": reference,
        "callback_url": request.build_absolute_uri(reverse_lazy('paystack_callback')),
        # --- ADD CURRENCY EXPLICITLY ---
        "currency": "NGN", # Assuming NGN (Nigerian Naira) based on your timezone
        # --- END ADDITION ---
        "metadata": {
            "user_id": user.id,
            "plan_id": plan.id,
            "plan_name": plan.name
        }
    }

    # --- DEBUGGING: Print the full payload being sent ---
    print(f"DEBUG: Paystack request payload: {json.dumps(payload, indent=2)}")
    # --- END DEBUGGING ---

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        response_data = response.json()

        if response_data['status']:
            # Save pending transaction to your database
            PaymentTransaction.objects.create(
                user=user,
                plan=plan,
                amount=plan.price,
                reference=reference,
                status='pending',
                gateway_response=json.dumps(response_data)
            )
            # Redirect user to Paystack's authorization URL
            return redirect(response_data['data']['authorization_url'])
        else:
            # Handle Paystack API error
            error_message = response_data.get('message', 'Unknown error from Paystack')
            messages.error(request, f"Payment initiation failed: {error_message}")
            # --- DEBUGGING: Log Paystack's specific error message ---
            print(f"DEBUG: Paystack API error response: {response_data}")
            # --- END DEBUGGING ---
            return redirect('subscription_plans')
    except requests.exceptions.RequestException as e:
        messages.error(request, f"Error communicating with Paystack: {e}")
        # --- DEBUGGING: Log the full response text if available ---
        if hasattr(e, 'response') and e.response is not None:
            print(f"DEBUG: Full Paystack error response text: {e.response.text}")
        # --- END DEBUGGING ---
        return redirect('subscription_plans')
    except Exception as e:
        messages.error(request, f"An unexpected error occurred during payment initiation: {e}")
        print(f"DEBUG: Unexpected error: {e}") # Further debug
        return redirect('subscription_plans')


def paystack_callback_view(request):
    """
    Handles the callback from Paystack after a payment attempt.
    Verifies the transaction and updates user's subscription status.
    """
    reference = request.GET.get('trxref') or request.GET.get('reference')
    if not reference:
        messages.error(request, "Payment reference not found.")
        return redirect('subscription_plans')

    try:
        # Verify transaction with Paystack
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response_data = response.json()

        if response_data['status'] and response_data['data']['status'] == 'success':
            transaction = get_object_or_404(PaymentTransaction, reference=reference)
            transaction.status = 'success'
            transaction.gateway_response = json.dumps(response_data)
            transaction.save()

            # Update user's subscription
            user = transaction.user
            plan = transaction.plan

            try:
                user_subscription = UserSubscription.objects.get(user=user)
                user_subscription.plan = plan
                user_subscription.start_date = transaction.created_at
                user_subscription.end_date = transaction.created_at + timedelta(days=plan.duration_days)
                user_subscription.is_active = True
                user_subscription.save()
                messages.info(request, f"Existing subscription updated to {plan.name}.")

            except UserSubscription.DoesNotExist:
                UserSubscription.objects.create(
                    user=user,
                    plan=plan,
                    start_date=transaction.created_at,
                    is_active=True
                )
                messages.info(request, f"New subscription created for {plan.name}.")

            user.is_premium = True
            user.save()

            messages.success(request, "Payment successful! Your subscription is now active.")
            return redirect('profile')
        else:
            transaction = get_object_or_404(PaymentTransaction, reference=reference)
            transaction.status = 'failed'
            transaction.gateway_response = json.dumps(response_data)
            transaction.save()
            messages.error(request, "Payment failed or was not successful. Please try again.")
            return redirect('subscription_plans')

    except requests.exceptions.RequestException as e:
        messages.error(request, f"Error verifying payment with Paystack: {e}")
        return redirect('subscription_plans')
    except PaymentTransaction.DoesNotExist:
        messages.error(request, "Invalid payment reference or transaction not found in our records.")
        return redirect('subscription_plans')
    except Exception as e:
        messages.error(request, f"An unexpected error occurred during payment verification: {e}")
        return redirect('subscription_plans')