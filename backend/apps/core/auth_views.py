"""
Session-based auth endpoints for the PyQt client.

These set/clear Django session cookies:
- POST /api/auth/login/
- POST /api/auth/logout/
- POST /api/auth/register/

Для десктоп-клиента без CSRF-токена views помечены csrf_exempt (только эти URL).
"""

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView


User = get_user_model()


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials"}, status=400)

        login(request, user)
        return Response({"detail": "ok"})


@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "ok"})


@method_decorator(csrf_exempt, name="dispatch")
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        if not email or "@" not in email:
            return Response({"detail": "Invalid email"}, status=400)
        if len(password) < 6:
            return Response({"detail": "Password too short"}, status=400)
        if User.objects.filter(username=email).exists():
            return Response({"detail": "User already exists"}, status=400)

        user = User.objects.create_user(username=email, email=email, password=password)
        login(request, user)
        return Response({"detail": "ok"}, status=201)

