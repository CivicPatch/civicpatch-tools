"""Set a user's role by email, from inside the app container.

The way to make the first admin: the role route takes no service key, so this needs cluster
access instead, a stronger credential than the key. Every user with the email gets the role
(one row per sign-in provider), and their sessions are dropped so it takes effect.

    docker exec -w /app civicpatch-org python src/scripts/grant_role.py someone@example.org admins
    kubectl exec -n civicpatch deploy/civicpatch-org -- python src/scripts/grant_role.py someone@example.org admins
"""

import argparse
import asyncio
import sys

import database.users as users_db
import lib.auth_session as auth_session
from schemas.common import UserRole


async def grant_role(email: str, role: UserRole) -> list[str]:
    users = await users_db.get_users_by_email(email)
    for user in users:
        await users_db.set_user_role(user["id"], role.value)
        await auth_session.invalidate_session(user["provider"], user["provider_user_id"])
    return [user["id"] for user in users]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("role", choices=[role.value for role in UserRole])
    args = parser.parse_args()
    user_ids = asyncio.run(grant_role(args.email, UserRole(args.role)))
    if not user_ids:
        sys.exit(f"No user with email {args.email}")
    for user_id in user_ids:
        print(f"Set {args.email} to '{args.role}' (user_id={user_id})")


if __name__ == "__main__":
    main()
