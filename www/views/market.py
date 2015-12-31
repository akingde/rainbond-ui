# -*- coding: utf8 -*-
import json
#from django.template.response import TemplateResponse
from django.http.response import JsonResponse, HttpResponse

from www.views import BaseView
#from www.decorator import perm_required
from django.views.decorators.cache import never_cache
from www.models import Category, App, OneLiner, Vote, ServiceInfo, AnonymousUser

import logging
logger = logging.getLogger('default')


def get_app_advantages(app, limit=10):
    result = []
    one_liners = OneLiner.objects.filter(app_id=app.pk).order_by('-agree')[:limit]
    for liner in one_liners:
        item = {"id": liner.pk, "line": liner.line, "agree": liner.agree}
        result.append(item)

    return result


def get_app_using(app):
    if app.service_key is None:
        return app.using
    else:
        return app.using


class AppList(BaseView):

    def get_end_category_ids(self, category_id):
        def create_map(*args):
            category_dict = {}
            for arg in args:
                if isinstance(arg, Category):
                    category_dict[arg.pk] = arg
                elif isinstance(arg, list):
                    for item in arg:
                        category_dict[item.pk] = item
            return category_dict

        category = Category.objects.get(pk=category_id)
        if category.level == 'root':
            root = category
            secondaries = Category.objects.filter(parent=category_id)
            second_ids = [e.pk for e in secondaries]
            ends = Category.objects.filter(parent__in=second_ids)
            category_dict = create_map(root, secondaries, ends)
            end_ids = [e.pk for e in ends]
            categories = [{"id": root.pk, "display_name": root.name}]
        elif category.level == 'secondary':
            root = Category.objects.get(pk=category.root)
            secondary = category
            ends = Category.objects.filter(parent=category_id)
            category_dict = create_map(root, secondary, ends)
            end_ids = [e.pk for e in ends]
            categories = [
                {"id": root.pk, "display_name": root.name},
                {"id": secondary.pk, "display_name": secondary.name},
            ]
        elif category.level == 'end':
            end = category
            secondary = Category.objects.get(pk=end.parent)
            root = Category.objects.get(pk=end.root)
            category_dict = create_map(root, secondary, end)
            end_ids = [end.pk]
            categories = [
                {"id": root.pk, "display_name": root.name},
                {"id": secondary.pk, "display_name": secondary.name},
                {"id": end.pk, "display_name": end.name},
            ]

        return end_ids, category_dict, categories

    def find_category(self, app, category_dict):
        end_category_id = app.category_id
        end_category = category_dict.get(end_category_id, None)

        if end_category is None:
            end_category = Category.objects.get(pk=end_category_id)
            category_dict[end_category.pk] = end_category

        root_category_id = end_category.root
        root_category = category_dict.get(root_category_id, None)

        if root_category is None:
            root_category = Category.objects.get(pk=root_category_id)
            category_dict[root_category.pk] = root_category

        return {"id": root_category.pk, "display_name": root_category.name}

    def get_app_list(self, category_id=None, sort='recent', page=0, limit=20, *args, **kwargs):
        appinfo = []
        orders = {
            'recent': '-update_time'
        }
        order = orders.get(sort)

        if category_id is not None:
            end_ids, category_dict, categories = self.get_end_category_ids(category_id)
            applist = App.objects.filter(category_id__in=end_ids).order_by(order)[page:limit]
        else:
            category_dict = {}
            categories = []
            applist = App.objects.all().order_by(order)[page:limit]

        for app in applist:
            app_category = self.find_category(app, category_dict)
            data = {
                "id": app.pk, "name": app.name, "description": app.description, "logo": app.logo, "pay_type": app.pay_type,
                "category": app_category, "advantages": get_app_advantages(app),
                "using": get_app_using(app)
            }
            appinfo.append(data)

        result = {
            "sort": sort, "categories": categories, "appinfo": appinfo
        }

        return result

    def get(self, request, category_id=None, *args, **kwargs):
        queries = request.GET.dict()
        data = self.get_app_list(category_id, **queries)
        flag = queries.get('flag', None)
        if flag == 'cross':
            callback = queries.get('callback')
            body = callback + '(' + json.dumps(data) + ')'
            return HttpResponse(body)
        return JsonResponse(data)


class AppInfo(BaseView):

    def find_category(self, app):
        end_id = app.category_id
        end = Category.objects.get(pk=end_id)

        secondary_id = end.parent
        root_id = end.root

        secondary = Category.objects.get(pk=secondary_id)
        root = Category.objects.get(pk=root_id)

        result = [
            {"id": root.pk, "display_name": root.name},
            {"id": secondary.pk, "display_name": secondary.name},
            {"id": end.pk, "display_name": end.name},
        ]

        return result

    def get(self, request, app_id, *args, **kwargs):
        app = App.objects.get(pk=app_id)
        app_category = self.find_category(app)
        data = {
            "id": app.pk, "name": app.name, "description": app.description, "logo": app.logo, "pay_type": app.pay_type,
            "website": app.website,
            "categories": app_category, "advantages": get_app_advantages(app),
            "using": get_app_using(app)
        }

        if app.service_key is not None:
            publish_app = ServiceInfo.objects.get(service_key=app.service_key)
            data.update({
                "version": publish_app.version, "install": publish_app.install_link
            })

        queries = request.GET.dict()
        flag = queries.get('flag', None)
        if flag == 'cross':
            callback = queries.get('callback')
            body = callback + '(' + json.dumps(data) + ')'
            return HttpResponse(body)

        return JsonResponse(data)


class AppAdvantage(BaseView):

    @never_cache
    def get(self, *args, **kwargs):
        return self.post(*args, **kwargs)

    def post(self, request, app_id, *args, **kwargs):
        logger.debug('debug', request)
        if request.method == "POST":
            queries = request.POST.dict()
        else:
            queries = request.GET.dict()
        flag = queries.get('flag', None)
        if isinstance(self.user, AnonymousUser):
            data = {"success": False, "info": "login required", "code": 403}
            if flag == 'cross':
                callback = queries.get('callback')
                body = callback + '(' + json.dumps(data) + ')'
                return HttpResponse(body, status=200)
            else:
                return JsonResponse(data, status=200)

        #data = json.loads(request.body)
        line = queries.get("line")
        user_id = self.user.pk
        app = App.objects.get(pk=app_id)
        liner = OneLiner.objects.create(app_id=app_id, line=line, agree=0, creater=user_id)
        app.using = app.using + 1
        app.save(update_fields=['using'])

        data = {"success": True, "info": u"评论成功", "code": 200, "id": liner.pk}
        if flag == 'cross':
            callback = queries.get('callback')
            body = callback + '(' + json.dumps(data) + ')'
            return HttpResponse(body)

        return JsonResponse(data, status=200)


class AdvantageVote(BaseView):

    @never_cache
    def get(self, *args, **kwargs):
        return self.post(*args, **kwargs)

    def post(self, request, app_id, liner_id, *args, **kwargs):
        logger.debug('debug', request)
        if request.method == "POST":
            queries = request.POST.dict()
        else:
            queries = request.GET.dict()

        flag = queries.get('flag', None)
        if isinstance(self.user, AnonymousUser):
            data = {"success": False, "info": "login required", "code": 403}
            if flag == 'cross':
                callback = queries.get('callback')
                body = callback + '(' + json.dumps(data) + ')'
                return HttpResponse(body, status=200)
            else:
                return JsonResponse(data, status=200)

        user_id = self.user.pk
        app = App.objects.get(pk=app_id)
        liner = OneLiner.objects.get(pk=liner_id)
        v, created = Vote.objects.get_or_create(user_id=user_id, liner_id=liner_id)
        if created:
            liner.agree = liner.agree + 1
            app.using = app.using + 1
            action = "argee"
        else:
            v.delete()
            liner.agree = liner.agree - 1
            app.using = app.using - 1
            action = "cancel"
        liner.save(update_fields=['agree'])
        app.save(update_fields=['using'])

        data = {"success": True, "info": action, "code": 200}

        if flag == 'cross':
            callback = queries.get('callback')
            body = callback + '(' + json.dumps(data) + ')'
            return HttpResponse(body)

        return JsonResponse(data, status=200)

    def put(self, *args, **kwargs):
        return self.post(*args, **kwargs)