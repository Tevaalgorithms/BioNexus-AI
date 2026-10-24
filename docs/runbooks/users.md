# Users, roles and invitations

Roles live in the BioNexus database (`app_users`, `memberships`), not in Cognito claims. Cognito proves
*who* someone is; the API decides *what* they may do. App clients and groups are not the boundary.

## First administrator (once, by an AWS administrator)
1. `aws cognito-idp admin-create-user --user-pool-id $POOL --username admin@org.example --user-attributes Name=email,Value=admin@org.example Name=email_verified,Value=true`
2. Read the user's `sub`: `aws cognito-idp admin-get-user --user-pool-id $POOL --username admin@org.example --query 'UserAttributes[?Name==\`sub\`].Value' --output text`
3. On the host: `docker compose exec api python -m bionexus.admin_cli add-user --subject <sub> --user-id admin-1 --role platform_admin --tenant org`
4. The user signs in at `/admin/login`, sets their own password, and records the recovery procedure with the AWS administrator.
There is no public registration and no shared admin password.

## Invite a scientist
Same two steps with `--role scientist --tenant org --project <project-id>` (repeat `--project`).
Sign-in is at `/login`. Re-running `add-user` replaces role and project membership (role change).

## Disable / revoke
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
