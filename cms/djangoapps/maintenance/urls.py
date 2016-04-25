"""
URLs for the maintenance app.
"""
from django.conf.urls import patterns, url

from . import views

urlpatterns = patterns(
    '',
    url(r'^$', views.index, name="maintenance"),
    url(r'^show_orphans/?$', views.show_orphans, name="show_orphans"),
    url(r'^delete_orphans/?$', views.delete_orphans, name="delete_orphans"),
    url(r'^export_course/?$', views.export_course, name="export_course"),
    url(r'^import_course/?$', views.import_course, name="import_course"),
    url(r'^delete_course/?$', views.delete_course, name="delete_course"),
    url(r'^force_publish_course/?$', views.force_publish_course, name="force_publish_course"),
)
