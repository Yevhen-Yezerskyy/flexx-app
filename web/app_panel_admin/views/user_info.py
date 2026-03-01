from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from app_users.models import FlexxUser, TippgeberClient

from .common import admin_only


def _render_client_user_info(request: HttpRequest, target: FlexxUser) -> HttpResponse:
    link = (
        TippgeberClient.objects.filter(client=target)
        .select_related("tippgeber")
        .first()
    )
    return render(
        request,
        "app_panel_admin/_user_info_client.html",
        {
            "target": target,
            "tippgeber": link.tippgeber if link and link.tippgeber_id else None,
        },
    )


def _render_tippgeber_user_info(request: HttpRequest, target: FlexxUser) -> HttpResponse:
    links = (
        TippgeberClient.objects.filter(tippgeber=target)
        .select_related("client")
        .order_by("client__email")
    )
    clients = [link.client for link in links if link.client_id and link.client]
    return render(
        request,
        "app_panel_admin/_user_info_tippgeber.html",
        {
            "target": target,
            "clients": clients,
        },
    )


@login_required
def user_info_modal(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    target = get_object_or_404(FlexxUser, id=user_id)
    if target.role == FlexxUser.Role.CLIENT:
        return _render_client_user_info(request, target)
    if target.role == FlexxUser.Role.AGENT:
        return _render_tippgeber_user_info(request, target)
    raise Http404("Unsupported user role")
