"""
Аутентификация для десктоп-клиента (PyQt): session cookie без CSRF.

Django @csrf_exempt на ViewSet не отключает проверку CSRF внутри
rest_framework.authentication.SessionAuthentication.enforce_csrf — из‑за этого
POST /api/favorites/ и др. давали 403.
"""

from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Сессия как обычно, но без enforce_csrf (клиент не браузер)."""

    def enforce_csrf(self, request):
        return
