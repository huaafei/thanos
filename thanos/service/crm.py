import json
import math

from django.shortcuts import render, redirect, reverse, HttpResponse
from django.utils.safestring import mark_safe
from django.conf.urls import url, include
from django.forms import ModelForm
from django.http import JsonResponse, QueryDict

from .paginator import Paginator


class CrmConfig:
    """对传入的Model表名，分配‘增删改查’等的URL"""

    ###### 基本配置 ######
    list_display = []  # 要在列表页面显示的列
    show_add_btn = False  # 默认不显示添加按钮
    model_form_class = None  # 在派生类里指定ModelForm
    list_per_page = 10

    def get_show_add_btn(self):
        # 根据权限，设置是否显示“添加”按钮
        return self.show_add_btn

    # 反向解析URL #

    def get_changelist_url(self):
        info = self.app_label, self.model_name
        url_verbose_name = '%s_%s_changelist' % info
        changelist_url = reverse(url_verbose_name)
        return changelist_url

    def get_add_url(self):
        info = self.app_label, self.model_name
        url_verbose_name = '%s_%s_add' % info
        add_url = reverse(url_verbose_name)
        return add_url

    def get_change_url(self, nid):
        info = self.app_label, self.model_name
        url_verbose_name = '%s_%s_change' % info
        change_url = reverse(url_verbose_name, args=(nid,))
        return change_url

    def get_delete_url(self, nid):
        info = self.app_label, self.model_name
        url_verbose_name = '%s_%s_delete' % info
        delete_url = reverse(url_verbose_name, args=(nid,))
        return delete_url

    # 列表页面的多选框、编辑、删除，动态填充<a>标签的href属性 #
    def checkbox(self, obj=None, is_header=False):
        if is_header:
            return mark_safe('<input type="checkbox" name="obj_list" value="###">')
        return mark_safe('<input type="checkbox" name="obj" value="%s">' % obj.id)

    def ele_change(self, params, obj=None, is_header=False):
        if is_header:
            return '修改'
        return mark_safe('<a href="%s?%s">修改</a>' % (self.get_change_url(obj.id), params))

    def ele_delete(self, params, obj=None, is_header=False):
        if is_header:
            return '删除'
        return mark_safe('<a href="%s?%s">删除</a>' % (self.get_delete_url(obj.id), params))

    # 在默认的list_display中添加checkbox、change、delete方法 #
    def get_list_display(self):
        data = []
        if self.list_display:
            data.extend(self.list_display)

            data.insert(0, self.checkbox)
            data.append(self.ele_change)
            data.append(self.ele_delete)
        return data

    ###### 初始化 ######
    def __init__(self, model_class, site_obj):
        self.model_class = model_class
        self.site_obj = site_obj
        self.app_label = self.model_class._meta.app_label
        self.model_name = self.model_class._meta.model_name

    ###### 增删改查URL分发 ######
    def get_urls(self):
        info = self.app_label, self.model_name

        urlpatterns = [
            url(r'^$', self.changelist_view, name='%s_%s_changelist' % info),
            url(r'^add/$', self.add_view, name='%s_%s_add' % info),
            url(r'^(\d+)/delete$', self.delete_view, name='%s_%s_delete' % info),
            url(r'^(\d+)/change$', self.change_view, name='%s_%s_change' % info),
        ]
        urlpatterns.extend(self.extra_urls())

        return urlpatterns

    ### 在get_urls()的基础上自定义其他URL，在派生类中重写 ###
    def extra_urls(self):
        return []

    @property
    def urls(self):
        return self.get_urls()

    def get_model_form_class(self):
        """动态生成ModelForm"""
        if self.model_form_class:
            return self.model_form_class

        class PrototypeModelForm(ModelForm):
            class Meta:
                model = self.model_class
                fields = '__all__'

        return PrototypeModelForm

    ###### 增删改查URL对应的视图函数 ######
    def changelist_view(self, request, *args, **kwargs):
        params_dict = QueryDict(mutable=True)
        params_dict['_list_filter'] = request.GET.urlencode()
        params = params_dict.urlencode()
        add_url = '%s?%s' % (self.get_add_url(), params)

        ### 表头 ###
        def header(self):
            if not self.list_display:  # 如果没有自定义list_display
                yield '记录'
            for field_name in self.get_list_display():
                if isinstance(field_name, str):
                    verbose_name = self.model_class._meta.get_field(field_name).verbose_name
                else:
                    verbose_name = field_name(params, is_header=True)
                yield verbose_name

        ### 分页操作 ###
        condition_dict = {}
        params_ele = QueryDict(mutable=True)

        for k, v in request.GET.items():
            if k == 'page':
                continue
            else:
                condition_dict[k] = v
                params_ele[k] = v

        obj_list = self.model_class.objects.filter(**condition_dict)
        try:
            current_page_num = int(request.GET.get('page', 1))
        except TypeError:
            current_page_num = 1

        paginator = Paginator(params_ele, obj_list, current_page_num, request.path, self.list_per_page)
        show_obj_list = paginator.show_obj_list()
        pager_html = paginator.pager_html()

        ### 表格主体 ###
        def data(self):
            for obj in show_obj_list:
                if not self.list_display:  # 如果没有自定义list_display
                    yield [obj]

                def inner(self, obj):
                    for field_name in self.get_list_display():
                        if isinstance(field_name, str):
                            val = getattr(obj, field_name)
                        else:
                            val = field_name(params, obj)
                        yield val

                yield inner(self, obj)

        return render(request, 'thanos/changelist_view.html',
                      {"model_name": self.model_name,
                       "show_add_btn": self.get_show_add_btn(), "add_url": add_url,
                       "head_list": header(self), "data_list": data(self), "pager_html": pager_html})

    def add_view(self, request, *args, **kwargs):
        model_form = self.get_model_form_class()
        if request.method == 'GET':
            add_edit_form = model_form()
            return render(request, 'thanos/add_view.html',
                          {"model_name": self.model_name, "add_edit_form": add_edit_form})
        else:
            add_edit_form = model_form(data=request.POST)
            if not add_edit_form.is_valid():
                return render(request, 'thanos/add_view.html',
                              {"model_name": self.model_name, "add_edit_form": add_edit_form})
            else:
                add_edit_form.save()
            return redirect('%s?%s' % (self.get_changelist_url(), request.GET.get('_list_filter')))

    def delete_view(self, request, nid, *args, **kwargs):
        if request.method == 'GET':
            return render(request, 'thanos/delete_view.html')
        else:
            opt = json.loads(request.body.decode()).get('opt')
            res_dict = {"status": True, "error_msg": None, "rtn_url": None}
            try:
                if opt == '确定':
                    self.model_class.objects.filter(pk=nid).delete()
                res_dict['rtn_url'] = '%s?%s' % (self.get_changelist_url(), request.GET.get('_list_filter'))

            except Exception as e:
                res_dict['status'] = False
                res_dict['error_msg'] = str(e)

            return JsonResponse(res_dict)

    def change_view(self, request, nid, *args, **kwargs):
        model_form = self.get_model_form_class()
        current_obj = self.model_class.objects.filter(pk=nid).first()
        if not current_obj:
            return redirect(self.get_changelist_url())

        if request.method == 'GET':
            add_edit_form = model_form(instance=current_obj)
            return render(request, 'thanos/edit_view.html',
                          {"model_name": self.model_name, "add_edit_form": add_edit_form})
        else:
            add_edit_form = model_form(instance=current_obj, data=request.POST)
            add_edit_form.save()
            return redirect('%s?%s' % (self.get_changelist_url(), request.GET.get('_list_filter')))


class CrmSite:
    '''用于分发CRM下的基础URL，并遍历所有注册的类，获取每个类对应的表下的增删改查等URl'''

    def __init__(self):
        self._registry = {}

    def register(self, model_class, config_class=None):
        if not config_class:
            config_class = CrmConfig
        self._registry[model_class] = config_class(model_class, self)

    def get_urls(self):
        urlpatterns = []
        app_labels_list = []
        for model, config_obj in self._registry.items():
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            urlpatterns += [url(r'^%s/%s/' % (app_label, model_name), include(config_obj.urls, None, None))]

            ######待整理######
            # if app_label not in app_labels_list:
            #     app_labels_list.append(app_label)
            ######

        return urlpatterns

    @property
    def urls(self):
        return self.get_urls(), None, None


site = CrmSite()