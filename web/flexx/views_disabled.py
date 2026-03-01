from __future__ import annotations

from django.http import HttpRequest, HttpResponse


def contract_workflow_disabled(request: HttpRequest, *args, **kwargs) -> HttpResponse:
    return HttpResponse(
        "Der Workflow zur Vertragserstellung/Unterzeichnung ist vorübergehend deaktiviert.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )

