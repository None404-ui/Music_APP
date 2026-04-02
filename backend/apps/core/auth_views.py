"""
Session-based auth endpoints for the PyQt client.

These set/clear Django session cookies:
- POST /api/auth/login/
- POST /api/auth/logout/
"""

from django.contrib.auth import authenticate, login, logout
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView


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


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "ok"})

