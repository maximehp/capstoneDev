import os
import logging
from ldap3 import Server, Connection, SIMPLE
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


class ActiveDirectoryBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        if not username or not password:
            return None

        dc_host = os.environ.get("AD_LDAP_HOST", "").strip()
        upn_suffix = os.environ.get("AD_UPN_SUFFIX", "").strip()

        if not dc_host or not upn_suffix:
            logger.error("AD_LDAP_HOST or AD_UPN_SUFFIX not set")
            return None

        bind_user = f"{username}@{upn_suffix}"
        server = Server(dc_host)

        try:
            Connection(
                server,
                user=bind_user,
                password=password,
                authentication=SIMPLE,
                auto_bind=True,
            )
        except Exception as exc:
            logger.warning("AD SIMPLE bind failed for %s: %s", bind_user, exc)
            return None

        User = get_user_model()
        user, _ = User.objects.get_or_create(username=username)
        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
