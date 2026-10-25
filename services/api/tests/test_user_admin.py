"""Inviting, listing and disabling users from the admin console."""

import pytest
from fastapi.testclient import TestClient

from bionexus.api.app import create_app
from bionexus.application.users import MAX_INVITES_PER_DAY
from bionexus.auth.provisioner import CognitoProvisioner, Invitation, LocalProvisioner
from bionexus.container import build_container
from bionexus.contracts.errors import Conflict, ProvisioningFailed
from bionexus.contracts.identity import Role
from tests.conftest import ADMIN, TOKENS


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class RecordingProvisioner:
    """Remembers what it was asked to do; can be told to fail."""

    def __init__(self):
        self.invited: list[tuple[str, Role]] = []
        self.disabled: list[str] = []
        self.fail = False

    def invite(self, email, role):
        if self.fail:
            raise ProvisioningFailed("down")
        self.invited.append((email, role))
        return Invitation(subject=f"sub-{email}", emailed=True)

    def disable(self, email):
        if self.fail:
            raise ProvisioningFailed("down")
        self.disabled.append(email)


@pytest.fixture
def provisioner():
    return RecordingProvisioner()


@pytest.fixture
def client(storage, provisioner):
    storage.users.upsert("admin", ADMIN)  # the caller is a registered admin, as in production
    container = build_container(TOKENS, storage=storage, provisioner=provisioner)
    return TestClient(create_app(container))


def disable(client, user_id, token="admin"):
    return client.post("/admin/users/disable", json={"user_id": user_id}, headers=auth(token))


def invite(client, email="new@lab.org", role="scientist", token="admin"):
    return client.post("/admin/users", json={"email": email, "role": role}, headers=auth(token))


def test_admin_invites_a_scientist(client, provisioner):
    reply = invite(client)
    assert reply.status_code == 201
    assert reply.json() == {
        "user_id": "new@lab.org",
        "role": "scientist",
        "emailed": True,
        "existing": False,
    }
    assert provisioner.invited == [("new@lab.org", Role.SCIENTIST)]


def test_admin_invites_another_admin(client, provisioner):
    assert invite(client, role="platform_admin").status_code == 201
    assert provisioner.invited == [("new@lab.org", Role.PLATFORM_ADMIN)]


def test_email_is_trimmed_and_lowercased(client, provisioner):
    invite(client, email="  New@Lab.ORG ")
    assert provisioner.invited[0][0] == "new@lab.org"


@pytest.mark.parametrize(
    "email",
    [
        "",
        "nobody",
        "a@b",
        "a b@lab.org",
        "x@lab.org, y@lab.org",
        '"q"@lab.org',
        "a@" + "b" * 260 + ".org",
    ],
)
def test_a_bad_email_is_refused(client, provisioner, email):
    assert invite(client, email=email).status_code == 422
    assert provisioner.invited == []


def test_an_unknown_role_is_refused(client, provisioner):
    assert invite(client, role="root").status_code == 422
    assert provisioner.invited == []


def test_the_invitee_can_be_listed_with_the_chosen_role(client):
    invite(client)
    users = client.get("/admin/users", headers=auth("admin")).json()
    assert {
        "user_id": "new@lab.org",
        "role": "scientist",
        "tenant_id": "org-a",
        "active": True,
    } in users


def test_listing_never_exposes_the_identity_subject(client):
    invite(client)
    assert "sub-" not in client.get("/admin/users", headers=auth("admin")).text


def test_inviting_twice_is_a_conflict(client, provisioner):
    invite(client)
    assert invite(client).status_code == 409
    assert len(provisioner.invited) == 1


def test_a_scientist_cannot_invite_or_list_or_disable(client, provisioner):
    assert invite(client, token="sci").status_code == 403
    assert client.get("/admin/users", headers=auth("sci")).status_code == 403
    assert disable(client, "x", "sci").status_code == 403
    assert provisioner.invited == []


def test_no_token_is_denied(client):
    assert client.post("/admin/users", json={"email": "a@lab.org"}).status_code == 403


def test_the_invitation_is_audited(client):
    invite(client)
    trail = client.get("/admin/audit", headers=auth("admin")).text
    assert "user.invited" in trail and "new@lab.org as scientist" in trail


def test_a_provider_failure_creates_no_local_account(client, provisioner):
    provisioner.fail = True
    assert invite(client).status_code == 502
    users = client.get("/admin/users", headers=auth("admin")).json()
    assert all(u["user_id"] != "new@lab.org" for u in users)


def test_the_daily_limit_applies(client):
    for number in range(MAX_INVITES_PER_DAY):
        assert invite(client, email=f"user{number}@lab.org").status_code == 201
    assert invite(client, email="one-more@lab.org").status_code == 429


def test_disabling_blocks_the_user_and_switches_off_sign_in(client, provisioner):
    invite(client)
    reply = disable(client, "new@lab.org", "admin")
    assert reply.status_code == 200
    assert reply.json()["sign_in_disabled"] is True
    assert provisioner.disabled == ["new@lab.org"]
    active = [u for u in client.get("/admin/users", headers=auth("admin")).json() if u["active"]]
    assert all(u["user_id"] != "new@lab.org" for u in active)


def test_a_disabled_user_can_be_invited_again(client):
    invite(client)
    disable(client, "new@lab.org", "admin")
    assert invite(client).status_code == 201


def test_disabling_still_works_when_the_provider_is_down(client, provisioner):
    invite(client)
    provisioner.fail = True
    reply = disable(client, "new@lab.org", "admin")
    assert reply.status_code == 200
    assert reply.json()["sign_in_disabled"] is False


def test_you_cannot_disable_yourself(client):
    assert disable(client, "admin-1", "admin").status_code == 422


def test_an_unknown_user_is_not_found(client):
    assert disable(client, "ghost@lab.org", "admin").status_code == 404


def test_an_admin_can_be_disabled_while_another_remains(client):
    invite(client, email="second@lab.org", role="platform_admin")
    assert disable(client, "second@lab.org", "admin").status_code == 200


def test_the_last_admin_cannot_be_disabled(storage, provisioner):
    storage.users.upsert("admin", ADMIN)
    service = build_container(TOKENS, storage=storage, provisioner=provisioner).users
    other_admin = ADMIN.model_copy(update={"user_id": "ops-1"})  # a caller who is not the target
    with pytest.raises(Conflict):
        service.disable(other_admin, "admin-1")


def test_local_provisioner_sends_nothing_and_is_stable():
    first = LocalProvisioner().invite("a@lab.org", Role.SCIENTIST)
    again = LocalProvisioner().invite("a@lab.org", Role.SCIENTIST)
    assert first.subject == again.subject and first.emailed is False


class FakeCognito:
    """The few Cognito calls the adapter makes."""

    class exceptions:  # noqa: N801 - mirrors the SDK's attribute
        class UsernameExistsException(Exception):
            pass

    def __init__(self, existing=False, fail=False):
        self.existing, self.fail = existing, fail
        self.calls: list[tuple[str, dict]] = []

    def _note(self, name, kwargs):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append((name, kwargs))

    def admin_create_user(self, **kwargs):
        self._note("create", kwargs)
        if self.existing:
            raise self.exceptions.UsernameExistsException()
        return {"User": {"Attributes": [{"Name": "sub", "Value": "sub-new"}]}}

    def admin_get_user(self, **kwargs):
        self._note("get", kwargs)
        return {"UserAttributes": [{"Name": "sub", "Value": "sub-old"}]}

    def admin_enable_user(self, **kwargs):
        self._note("enable", kwargs)

    def admin_add_user_to_group(self, **kwargs):
        self._note("group", kwargs)

    def admin_disable_user(self, **kwargs):
        self._note("disable", kwargs)

    def admin_user_global_sign_out(self, **kwargs):
        self._note("signout", kwargs)


def names(fake):
    return [name for name, _ in fake.calls]


def test_cognito_creates_the_account_and_emails_the_invitation():
    fake = FakeCognito()
    result = CognitoProvisioner("pool-1", "us-west-2", fake).invite("a@lab.org", Role.SCIENTIST)
    assert result == Invitation("sub-new", emailed=True)
    create = fake.calls[0][1]
    assert create["DesiredDeliveryMediums"] == ["EMAIL"]
    assert "TemporaryPassword" not in create  # Cognito generates it; this code never sees one
    assert fake.calls[1] == (
        "group",
        {"UserPoolId": "pool-1", "Username": "a@lab.org", "GroupName": "scientist"},
    )


def test_cognito_reuses_an_existing_account_without_a_second_email():
    fake = FakeCognito(existing=True)
    result = CognitoProvisioner("pool-1", "us-west-2", fake).invite(
        "a@lab.org", Role.PLATFORM_ADMIN
    )
    assert result == Invitation("sub-old", emailed=False, existing=True)
    assert names(fake) == ["create", "get", "enable", "group"]
    assert fake.calls[-1][1]["GroupName"] == "platform_admin"


def test_cognito_errors_become_a_provisioning_failure_without_details():
    with pytest.raises(ProvisioningFailed) as error:
        CognitoProvisioner("pool-1", "us-west-2", FakeCognito(fail=True)).invite(
            "a@lab.org", Role.SCIENTIST
        )
    assert "RuntimeError" in str(error.value) and "boom" not in str(error.value)


def test_cognito_disable_also_signs_the_user_out_everywhere():
    fake = FakeCognito()
    CognitoProvisioner("pool-1", "us-west-2", fake).disable("a@lab.org")
    assert names(fake) == ["disable", "signout"]
