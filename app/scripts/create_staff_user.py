"""
One-time / occasional CLI script to create a staff account.
 
Deliberately NOT an API endpoint: staff accounts are the root of trust for
issuing activation codes, so this is only runnable by someone with direct
access to the running container / database -- there is no HTTP surface for
an attacker to find or brute-force.
 
Usage (run inside the web container):
 
    docker compose exec web python -m app.scripts.create_staff_user \\
        --email staff@oakwood.com \\
        --full-name "Jane Doe" \\
        --community-code OAKWOOD-101 \\
        --community-name "Oakwood Apartments"
 
If --community-code refers to a community that already exists, that
community is used and --community-name is ignored. If it doesn't exist,
--community-name is required and a new Community row is created.
 
The password is never taken as a plain CLI argument (which would leak into
shell history / process lists) -- it's prompted interactively via getpass.
"""

import argparse
import getpass
import sys

from app.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole, Community

def main() -> None:
    parser = argparse.ArgumentParser(description="Create a staff account for a community.")
    parser.add_argument("--email", required=True, help="Email address for the staff account.")
    parser.add_argument("--full-name", required=True, help="Full name of the staff member.")
    parser.add_argument("--community-code", required=True, help="Unique code for the community, e.g. VILLAS-101")
    parser.add_argument("--community-name", required=False, help="Name of the community (required if creating a new community).")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.email == args.email).first()
        if existing_user:
            print(f"Error: User with email '{args.email}' already exists (id={existing_user.id}).")
            sys.exit(1)

            community = db.query(Community).filter(Community.code == args.community_code).first()
            if not community:
                if not args.community_name:
                    print(
                        f"Error: Community with code '{args.community_code}' does not exist, and --community-name was not provided to create a new one."
                    , file = sys.stderr,
                    )
                    sys.exit(1)
                community = Community(name=args.community_name, code=args.community_code)
                db.add(community)
                db.flush()  # Ensure the community gets an ID before committing
                print(f"Created new community '{community.name}' with code ({community.code}).")

            password = getpass.getpass("Create password for the new staff account: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                sys.exit(1)
            if len(password) < 8:
                print("Error: Password must be at least 8 characters long.", file=sys.stderr)
                sys.exit(1)

            staff_user = User(
                email=args.email,
                hashed_password=hash_password(password),
                full_name=args.full_name,
                community_id=community.id,
                role=UserRole.STAFF,
                is_active=True,
            )
            db.add(staff_user)
            db.commit()
            db.refresh(staff_user)

            print(
            f"\nStaff account created:\n"
            f"  id:      {staff_user.id}\n"
            f"  email:   {staff_user.email}\n"
            f"  role:    {staff_user.role.value}\n"
            f"  community: {community.name} ({community.code})\n"
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()