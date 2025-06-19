# accounts/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.homepage_view, name='homepage'),
    path('register/', views.SignUpView.as_view(), name='register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('browse/', views.browse_profiles_view, name='browse_profiles'),
    # REMOVED: path('swipe/', views.swipe_profiles_view, name='swipe_profiles'),
    path('profile/<str:username>/', views.view_other_profile, name='view_other_profile'),
    path('like/<str:username>/', views.like_view, name='like_user'),
    path('matches/', views.matches_view, name='matches'),
    path('plans/', views.subscription_plans_view, name='subscription_plans'),
    path('plan/pay/<int:plan_id>/', views.initiate_payment_view, name='initiate_payment'),
    path('paystack_callback/', views.paystack_callback_view, name='paystack_callback'),
]
