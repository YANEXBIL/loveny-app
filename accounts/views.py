# accounts/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login # Import login function (logout is a class-based view)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import CreateView
from django.urls import reverse_lazy # For redirecting to a URL by name
from django.http import JsonResponse, HttpResponse # For AJAX responses and general HTTP responses
from django.db.models import Q # For complex queries
from django.conf import settings # Import settings to access API keys
import requests # For making HTTP requests to generate WhatsApp link
import json
import os
from django.contrib import messages
from datetime import timedelta

# Import all models and forms
from .forms import CustomUserCreationForm, UserProfileForm
from .models import UserProfile, Like, SubscriptionPlan, UserSubscription, PaymentTransaction


class CustomLoginView(LoginView):
    """Custom login view."""
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

class CustomLogoutView(LogoutView):
    """Custom logout view."""
    next_page = reverse_lazy('login')

class SignUpView(CreateView):
    """View for user registration."""
    form_class = CustomUserCreationForm
    template_name = 'accounts/registration_form.html'
    success_url = reverse_lazy('profile_edit')

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
    """Allows the current logged-in user to edit their profile."""
    user_profile = request.user
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated!")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserProfileForm(instance=user_profile)
    return render(request, 'accounts/profile_edit.html', {'form': form})

def homepage_view(request):
    """The main landing page for the LOVENY app."""
    return render(request, 'accounts/homepage.html')

@login_required
def browse_profiles_view(request):
    """Allows the current user to browse other user profiles."""
    current_user = request.user
    other_profiles = UserProfile.objects.exclude(id=current_user.id)
    current_user_seeking = current_user.user_type

    if current_user_seeking == 'DATING':
        other_profiles = other_profiles.filter(user_type='DATING')
    elif current_user_seeking == 'HOOKUP':
        other_profiles = other_profiles.filter(user_type='HOOKUP')
    elif current_user_seeking == 'SUGAR_DADDY':
        other_profiles = other_profiles.filter(Q(user_type='SUGAR_MUMMY') | Q(user_type='DATING'))
    elif current_user_seeking == 'SUGAR_MUMMY':
        other_profiles = other_profiles.filter(Q(user_type='SUGAR_DADDY') | Q(user_type='DATING'))

    profiles_data = []
    for profile in other_profiles:
        has_liked = Like.objects.filter(liker=current_user, liked_user=profile).exists()
        is_matched = Like.objects.filter(
            Q(liker=current_user, liked_user=profile) & Q(liker=profile, liked_user=current_user)
        ).exists()

        profiles_data.append({
            'profile': profile,
            'has_liked': has_liked,
            'is_matched': is_matched,
        })

    context = {
        'profiles_data': profiles_data,
        'current_user_type': current_user.get_user_type_display(),
    }
    return render(request, 'accounts/browse_profiles.html', context)


@login_required
def view_other_profile(request, username):
    """
    Displays a specific user's profile detail.
    Includes logic to generate a WhatsApp chat link ONLY if current_user is premium.
    """
    current_user = request.user
    profile = get_object_or_404(UserProfile, username=username)

    if profile == current_user:
        return redirect('profile')

    has_liked = Like.objects.filter(liker=current_user, liked_user=profile).exists()
    is_matched = Like.objects.filter(
        Q(liker=current_user, liked_user=profile) & Q(liker=profile, liked_user=current_user)
    ).exists()

    whatsapp_link = None
    # Only generate WhatsApp link if current user is premium AND the other user has a phone number
    if current_user.is_premium and profile.phone_number:
        user_profile_url = request.build_absolute_uri(reverse_lazy('view_other_profile', kwargs={'username': current_user.username}))
        clean_phone_number = profile.phone_number.replace(' ', '').replace('-', '')
        pre_filled_message = f"Hi {profile.username}! I found your profile on LOVENY. Here's my profile: {user_profile_url}"
        whatsapp_link = f"https://wa.me/{clean_phone_number}?text={requests.utils.quote(pre_filled_message)}"
    elif not current_user.is_premium:
        messages.info(request, "Upgrade to premium to message other users on WhatsApp!")


    context = {
        'profile': profile,
        'has_liked': has_liked,
        'is_matched': is_matched,
        'whatsapp_link': whatsapp_link, # Will be None if not premium or no phone number
    }
    return render(request, 'accounts/other_profile_detail.html', context)


@login_required
def like_view(request, username):
    """Handles the 'like' and 'unlike' actions."""
    if request.method == 'POST':
        liker = request.user
        liked_user = get_object_or_404(UserProfile, username=username)

        if liker == liked_user:
            messages.error(request, "You cannot like your own profile!")
            return redirect('browse_profiles')

        like_instance_query = Like.objects.filter(liker=liker, liked_user=liked_user)

        if like_instance_query.exists():
            like_instance_query.delete()
            messages.info(request, f'You unliked {liked_user.username}.')
        else:
            Like.objects.create(liker=liker, liked_user=liked_user)
            messages.success(request, f'You liked {liked_user.username}.')
            if Like.objects.filter(liker=liked_user, liked_user=liker).exists():
                messages.success(request, f'It\'s a MATCH with {liked_user.username}!')
        
        return redirect('browse_profiles')
    return redirect('browse_profiles')


@login_required
def matches_view(request):
    """Displays a list of mutual matches for the current user."""
    current_user = request.user
    likes_given = current_user.likes_given.all()
    likes_received = current_user.likes_received.all()

    mutual_match_ids = set()
    for like_g in likes_given:
        if likes_received.filter(liker=like_g.liked_user).exists():
            mutual_match_ids.add(like_g.liked_user.id)

    matches = UserProfile.objects.filter(id__in=list(mutual_match_ids)).order_by('username')

    # The categorized matches are still prepared in context for potential future use,
    # but the template now renders the combined 'matches' list only.
    categorized_matches = {
        'DATING': [], 'HOOKUP': [], 'SUGAR_DADDY': [], 'SUGAR_MUMMY': [],
    }
    for match_profile in matches:
        if match_profile.user_type in categorized_matches:
            categorized_matches[match_profile.user_type].append(match_profile)

    context = {
        'dating_matches': categorized_matches['DATING'],
        'hookup_matches': categorized_matches['HOOKUP'],
        'sugar_daddy_matches': categorized_matches['SUGAR_DADDY'],
        'sugar_mummy_matches': categorized_matches['SUGAR_MUMMY'],
        'has_any_matches': bool(matches.exists()),
        'matches': matches, # Pass the combined list for simpler rendering in the updated matches.html
    }
    return render(request, 'accounts/matches.html', context)


# Removed: chat_room_view and message_gate_view
# REMOVED: swipe_profiles_view


# --- Payment Views (Remain the same) ---

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
    """Initiates a payment process with Paystack for a selected subscription plan."""
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    user = request.user

    amount_kobo = int(plan.price * 100)

    print(f"DEBUG: Initializing Paystack payment for user: {user.email}, amount: {plan.price} NGN ({amount_kobo} kobo)")

    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    reference = f"loveny_{user.id}_{plan.id}_{os.urandom(4).hex()}"

    payload = {
        "email": user.email,
        "amount": amount_kobo,
        "reference": reference,
        "callback_url": request.build_absolute_uri(reverse_lazy('paystack_callback')),
        "currency": "NGN",
        "metadata": {
            "user_id": user.id,
            "plan_id": plan.id,
            "plan_name": plan.name
        }
    }

    print(f"DEBUG: Paystack request payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        response_data = response.json()

        if response_data['status']:
            PaymentTransaction.objects.create(
                user=user,
                plan=plan,
                amount=plan.price,
                reference=reference,
                status='pending',
                gateway_response=json.dumps(response_data)
            )
            return redirect(response_data['data']['authorization_url'])
        else:
            error_message = response_data.get('message', 'Unknown error from Paystack')
            messages.error(request, f"Payment initiation failed: {error_message}")
            print(f"DEBUG: Paystack API error response: {response_data}")
            return redirect('subscription_plans')
    except requests.exceptions.RequestException as e:
        messages.error(request, f"Error communicating with Paystack: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"DEBUG: Full Paystack error response text: {e.response.text}")
        return redirect('subscription_plans')
    except Exception as e:
        messages.error(request, f"An unexpected error occurred during payment initiation: {e}")
        print(f"DEBUG: Unexpected error: {e}")
        return redirect('subscription_plans')


def paystack_callback_view(request):
    """Handles the callback from Paystack after a payment attempt."""
    reference = request.GET.get('trxref') or request.GET.get('reference')
    if not reference:
        messages.error(request, "Payment reference not found.")
        return redirect('subscription_plans')

    try:
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
