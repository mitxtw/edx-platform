"""
Index view for the maintenance app.
"""

from student.roles import GlobalStaff

from edxmako.shortcuts import render_to_response

from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


MAINTENANCE_INDEX_URLS = [
    {
        "url": reverse_lazy("maintenance:show_orphans"),
        "name": _("Print Orphans"),
        "description": _("View orphans."),
    },
    {
        "url": reverse_lazy("maintenance:delete_orphans"),
        "name": _("Delete Orphans"),
        "description": _("Delete orphans."),
    },
    {
        "url": reverse_lazy("maintenance:export_course"),
        "name": _("Export Course"),
        "description": _("Export course"),
    },
    {
        "url": reverse_lazy("maintenance:import_course"),
        "name": _("Import Course"),
        "description": _("Import Course."),
    },
    {
        "url": reverse_lazy("maintenance:delete_course"),
        "name": _("Delete Course"),
        "description": _("Delete course."),
    },
    {
        "url": reverse_lazy("maintenance:force_publish_course"),
        "name": _("Force Publish Course"),
        "description": _("Force publish course."),
    },
]


@login_required
def index(request):
    """Render the maintenance index view. """
    # Only global staff (PMs) are able to activate/deactivate certificate configuration
    if not GlobalStaff().has_user(request.user):
        raise PermissionDenied()
    context = {
        "urls": MAINTENANCE_INDEX_URLS,
    }
    return render_to_response("maintenance/index.html", context)

@login_required
def show_orphans(request):
    """Render show orphans view """
    # Only global staff (PMs) are able to activate/deactivate certificate configuration
    if not GlobalStaff().has_user(request.user):
        raise PermissionDenied()
    context = {
        "orphans": [],
    }
    return render_to_response("maintenance/show_orphans.html", context)


@login_required
def delete_orphans(request):
    """Render delete orphans view """
    # Only global staff (PMs) are able to activate/deactivate certificate configuration
    if not GlobalStaff().has_user(request.user):
        raise PermissionDenied()
    context = {
        "orphans": [1,2],
    }
    return render_to_response("maintenance/delete_orphans.html", context)


@login_required
def export_course(request):
    """Render export_course view """
    # Only global staff (PMs) are able to activate/deactivate certificate configuration
    if not GlobalStaff().has_user(request.user):
        raise PermissionDenied()
    context = {
    }
    return render_to_response("maintenance/export_course.html", context)


@login_required
def import_course(request):
    """Render import_course view """
    # Only global staff (PMs) are able to activate/deactivate certificate configuration
    if not GlobalStaff().has_user(request.user):
        raise PermissionDenied()
    context = {
    }
    return render_to_response("maintenance/import_course.html", context)


@login_required
def delete_course(request):
    """Render delete_course view """
    # Only global staff (PMs) are able to activate/deactivate certificate configuration
    if not GlobalStaff().has_user(request.user):
        raise PermissionDenied()
    context = {
    }
    return render_to_response("maintenance/delete_course.html", context)


@login_required
def force_publish_course(request):
    """Render force_publish_course view """
    # Only global staff (PMs) are able to activate/deactivate certificate configuration
    if not GlobalStaff().has_user(request.user):
        raise PermissionDenied()
    context = {
    }
    return render_to_response("maintenance/force_publish_course.html", context)
