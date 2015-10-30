# -*- coding: utf8 -*-
import urllib
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.http import HttpResponse

from www.auth.discourse import SSO_AuthHandle
from www.models import AnonymousUser
from www.views.base import BaseView

import logging
logger = logging.getLogger('default')


class DiscourseAuthView(BaseView):

    @never_cache
    def get(self, request, *args, **kwargs):
        sso = request.GET.get('sso')
        sig = request.GET.get('sig')
        s = SSO_AuthHandle(settings.DISCOURSE_SECRET_KEY)
        payload = s.extra_payload(sso, sig)
        logger.debug("auth.discourse", "receive auth info: sso: {0}, sig: {1}, payload: {2}".format(sso, sig, payload))
        if payload is None:
            logger.info("auth.discourse", "sig %s is uncorrect" % sig)
            return HttpResponse("sig is uncorrect", status=403)

        user = self.user
        if isinstance(user, AnonymousUser):
            logger.info("auth.discourse", "AnonymousUser, redirect to login")
            return self.redirect_to('/login?next={0}'.format(urllib.quote(request.get_full_path())))
        else:
            logger.info("auth.discourse", "user %s authed for discourse login" % user.nick_name)
            user_info = {
                "name": user.nick_name, "external_id": user.nick_name,
                "username": user.nick_name, "email": user.email,
                "nonce": payload['nonce']
            }
            url_encoded_sso, sig = s.create_auth(user_info)
            redirect_url = '{0}?sso={1}&sig={2}'.format(payload['return_sso_url'], urllib.quote(url_encoded_sso), urllib.quote(sig))
            return self.redirect_to(redirect_url)