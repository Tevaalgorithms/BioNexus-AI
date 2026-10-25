# Users, roles and invitations

Roles live in the BioNexus database (`app_users`, `memberships`), not in Cognito claims. Cognito proves
*who* someone is; the API decides *what* they may do. App clients and groups are not the boundary.

## First administrator (once, by an AWS administrator)
1. `aws cognito-idp admin-create-user --user-pool-id $POOL --username admin@org.example --user-attributes Name=email,Value=admin@org.example Name=email_verified,Value=true`
2. Read the user's `sub`: `aws cognito-idp admin-get-user --user-pool-id $POOL --username admin@org.example --query 'UserAttributes[?Name==\`sub\`].Value' --output text`
3. On the host: `docker compose exec api python -m bionexus.cli.admin add-user --subject <sub> --user-id admin-1 --role platform_admin --tenant org`
4. The user signs in at `/admin/login`, sets their own password, and records the recovery procedure with the AWS administrator.
There is no public registration and no shared admin password.

## Invite a scientist or an administrator (the Users page)
Platform admins do this in the admin console, **Users**, with no command line:

1. Enter the person's email and choose **Scientist** or **Platform admin**, then **Send invitation**.
2. Amazon Cognito creates the sign-in and emails a temporary password. BioNexus never sees or stores it.
   The person signs in (scientists at `/login`, admins at `/admin/login`) and chooses their own password.
3. BioNexus records the role. A new scientist belongs to no project yet: a project owner adds them by
   their user id, which is their email address.

Rules the server enforces: only platform admins can use the page; the email is checked and lower-cased; an
address that already has access is refused; a role must be one of the two above; each admin may send at most
25 invitations a day; every invitation and every disable is written to the audit log. If the address already
has a Cognito sign-in (for example it was disabled before), no second email is sent and the access is restored.

The API reaches Cognito with the same server credentials it uses for settings. Their policy allows exactly
six Cognito actions on this one pool (`infra/terraform/ssm.tf`, `manage-bionexus-users`). A sign-in created
this way has no access until BioNexus records a role, so the database stays the authority.

**By hand (fallback).** Same two steps as for the first administrator, with `--role scientist --tenant org
--project <project-id>` (repeat `--project`). Re-running `add-user` replaces role and project membership.

## Disable / revoke
**Users page:** **Disable**, then **Confirm disable**. Access stops on the next request, tokens issued so
far are rejected, and the Cognito sign-in is switched off and signed out everywhere. You cannot disable yourself
or the last platform admin. If Cognito cannot be reached, access is still removed and the page tells you to
switch the sign-in off in Cognito too. To bring someone back, invite them again.

By hand:
- `admin_cli disable-user --subject <sub>`: the next request is refused (account lookup fails).
- `admin_cli revoke-sessions --subject <sub>`: tokens issued before now are rejected even though
  Cognito JWTs otherwise validate offline until expiry.
- Also `aws cognito-idp admin-disable-user ...` to stop new sign-ins.

## Project spaces
Scientists create their own project spaces in the app (**Projects → New project**, or **New project** on the
New analysis page). The creator becomes the owner and can invite existing scientists in the same organisation by
user id. Administrators do not create projects and cannot open them. Operators can still assign a user to a
project from the command line (`add-user --project <id>`); both kinds of membership are combined. A project can
only be opened by its members, and reviewed evidence is reused only inside the project where it was approved.
