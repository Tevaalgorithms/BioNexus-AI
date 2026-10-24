"""Operator procedure for users (AUTH-05/16): `python -m bionexus.cli.admin <command>`.

Cognito users are created separately with the AWS CLI (see docs/runbooks); this registers the
matching application account, role, tenant and project membership.
"""

import argparse
from datetime import UTC, datetime

from bionexus.contracts.identity import Principal, Role
from bionexus.params import parameters
from bionexus.storage.postgres import Database, postgres_storage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bionexus-admin")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add-user", help="register or update an invited user")
    add.add_argument("--subject", required=True, help="Cognito 'sub' of the user")
    add.add_argument("--user-id", required=True)
    add.add_argument("--role", choices=[r.value for r in Role], required=True)
    add.add_argument("--tenant", required=True)
    add.add_argument("--project", action="append", default=[])
    disable = sub.add_parser("disable-user")
    disable.add_argument("--subject", required=True)
    revoke = sub.add_parser("revoke-sessions", help="reject every token issued so far")
    revoke.add_argument("--subject", required=True)
    return parser


def run(args: argparse.Namespace, users) -> str:
    if args.command == "add-user":
        principal = Principal(
            user_id=args.user_id,
            role=Role(args.role),
            tenant_id=args.tenant,
            project_ids=frozenset(args.project),
        )
        users.upsert(args.subject, principal)
        return f"registered {args.user_id} as {args.role}"
    if args.command == "disable-user":
        users.disable(args.subject)
        return "disabled"
    users.revoke_sessions(args.subject, datetime.now(UTC))
    return "sessions revoked"


def main() -> None:
    args = build_parser().parse_args()
    storage = postgres_storage(Database(parameters().require("BIONEXUS_DATABASE_URL")))
    print(run(args, storage.users))


if __name__ == "__main__":
    main()
