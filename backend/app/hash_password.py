"""Generate a bcrypt hash for a users-config entry.

Usage: ``python -m app.hash_password`` — prompts without echo and prints the
hash to paste into the ``password_hash`` field. Hash generation only; account
management is the seeded config's job (see backend/config/users.example.toml).
"""

import getpass

import bcrypt


def main() -> None:
    password = getpass.getpass("Password: ")
    if not password:
        raise SystemExit("empty password refused")
    print(bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii"))


if __name__ == "__main__":
    main()
