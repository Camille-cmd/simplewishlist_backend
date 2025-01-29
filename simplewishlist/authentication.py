from django.contrib import messages
from django.shortcuts import redirect
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import User, Group
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView


class SimplewishlistOIDCBackend(OIDCAuthenticationBackend):
    """
    Custom OIDC backend to manage the user creation and filtering.
    """

    def create_user(self, claims):
        """
        Create a user with the given claims.
        """
        print(claims)
        email = claims.get("email")
        if not email:
            return None  # Refuse user creation if no email is provided

        # User is inactive by default
        username = claims.get("preferred_username", email)
        name = claims.get("name", "")
        given_name = claims.get("given_name", "")
        user = User.objects.create_user(
            username=username, first_name=given_name, last_name=name, email=email, is_active=False
        )

        # Add user to Users groups
        user.groups.add(Group.objects.get(name="Users"))

        return user

    def filter_users_by_claims(self, claims):
        """
        Return all users matching the given claims.
        """
        email = claims.get("email")
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email=email)


class SimplewishlistOIDCCallbackView(OIDCAuthenticationCallbackView):
    """
    Custom OIDC callback view to manage the user login failure and redirection to the login page.

    We do not authenticate the user right away, we let the admin validate the account first.
    As the user is not active by default, the authentication will fail and the user
    will be redirected to the login page.

    """

    def login_failure(self):
        """
        Override the default login_failure method to ovoid the unsafe redirect admin page error
        """
        return redirect(self.failure_url)

    def get(self, request):
        """ """
        response = super().get(request)

        # The user account needs to be validated by an admin before he/she can log in
        if self.user and not self.user.is_active:
            messages.warning(
                request,
                "Your account has been created and is pending validation. "
                "Please wait for an administrator to validate your account.",
            )

        return response
