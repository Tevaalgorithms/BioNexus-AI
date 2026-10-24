"""Request-scoped dependencies shared by all routers."""

from typing import Annotated

from fastapi import Depends, Header, Request

from bionexus.container import Container
from bionexus.contracts.errors import AccessDenied
from bionexus.contracts.identity import Principal


def get_container(request: Request) -> Container:
    return request.app.state.container


AppContainer = Annotated[Container, Depends(get_container)]


def get_principal(
    container: AppContainer, authorization: Annotated[str, Header()] = ""
) -> Principal:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AccessDenied("Bearer token required")
    return container.projects.with_memberships(container.verifier.verify(token))


Caller = Annotated[Principal, Depends(get_principal)]
