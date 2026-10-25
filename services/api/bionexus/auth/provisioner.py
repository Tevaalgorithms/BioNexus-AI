"""Creating and disabling sign-in accounts in the identity provider.

The provider (Amazon Cognito) emails the invited person a temporary password. This code never
sees or stores that password. Roles still live in the BioNexus database: the Cognito group is only
a convenience for operators.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from bionexus.contracts.errors import ProvisioningFailed
from bionexus.contracts.identity import Role

GROUP_FOR_ROLE = {Role.SCIENTIST: "scientist", Role.PLATFORM_ADMIN: "platform_admin"}


@dataclass(frozen=True)
class Invitation:
    subject: str  # the identity provider's id for the account
    emailed: bool  # the provider sent the person a temporary password
    existing: bool = False  # the account was already there, so no new email was sent


class UserProvisioner(Protocol):
    def invite(self, email: str, role: Role) -> Invitation: ...
    def disable(self, email: str) -> None: ...


class LocalProvisioner:
    """Development and tests: nothing is sent and no account exists outside this process."""

    def invite(self, email: str, role: Role) -> Invitation:
        return Invitation(subject=f"local-{uuid.uuid5(uuid.NAMESPACE_URL, email)}", emailed=False)

    def disable(self, email: str) -> None:
        return None


def _attribute(attributes: list[dict[str, str]], name: str) -> str:
    return next(a["Value"] for a in attributes if a["Name"] == name)


class CognitoProvisioner:
    def __init__(self, user_pool_id: str, region: str, client: Any = None) -> None:
        self._pool = user_pool_id
        if client is None:
            import boto3  # imported lazily: local use needs no AWS

            client = boto3.client("cognito-idp", region_name=region)
        self._client = client

    def invite(self, email: str, role: Role) -> Invitation:
        try:
            invitation = self._create_or_find(email)
            self._client.admin_add_user_to_group(
                UserPoolId=self._pool, Username=email, GroupName=GROUP_FOR_ROLE[role]
            )
        except ProvisioningFailed:
            raise
        except Exception as error:  # the SDK's errors vary; only "it failed" matters here
            raise ProvisioningFailed(
                f"Could not create the account: {type(error).__name__}"
            ) from error
        return invitation

    def _create_or_find(self, email: str) -> Invitation:
        try:
            created = self._client.admin_create_user(
                UserPoolId=self._pool,
                Username=email,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                ],
                DesiredDeliveryMediums=["EMAIL"],
            )
            return Invitation(_attribute(created["User"]["Attributes"], "sub"), emailed=True)
        except self._client.exceptions.UsernameExistsException:
            found = self._client.admin_get_user(UserPoolId=self._pool, Username=email)
            self._client.admin_enable_user(UserPoolId=self._pool, Username=email)  # if disabled
            return Invitation(_attribute(found["UserAttributes"], "sub"), False, existing=True)

    def disable(self, email: str) -> None:
        try:
            self._client.admin_disable_user(UserPoolId=self._pool, Username=email)
            self._client.admin_user_global_sign_out(UserPoolId=self._pool, Username=email)
        except Exception as error:
            raise ProvisioningFailed(
                f"Could not disable the account: {type(error).__name__}"
            ) from error
