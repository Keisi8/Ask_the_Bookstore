"""Store your Anthropic API key in the operating system's keychain.

    python setup_key.py            # save or replace the key
    python setup_key.py --show     # check whether one is stored
    python setup_key.py --delete   # remove it

The key goes into macOS Keychain, Windows Credential Manager, or the Linux
Secret Service -- never into this folder, so it cannot be committed by accident.
"""

from __future__ import annotations

import sys
from getpass import getpass

SERVICE = "ask-the-bookstore"
ACCOUNT = "anthropic-api-key"


def main() -> int:
    try:
        import keyring
    except ImportError:
        print("The `keyring` package is not installed. Run:\n\n    pip install keyring\n")
        return 1

    backend = keyring.get_keyring().__class__.__name__
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "--show":
        stored = keyring.get_password(SERVICE, ACCOUNT)
        if stored:
            print(f"A key is stored in {backend}: {stored[:12]}...{stored[-4:]}")
        else:
            print(f"No key stored in {backend}.")
        return 0

    if arg == "--delete":
        try:
            keyring.delete_password(SERVICE, ACCOUNT)
            print("Key deleted.")
        except keyring.errors.PasswordDeleteError:
            print("No key was stored.")
        return 0

    print(f"Storing into: {backend}")
    print("Get a key at https://console.anthropic.com/settings/keys\n")
    key = getpass("Paste your Anthropic API key (not echoed): ").strip()
    if not key:
        print("Nothing entered; no changes made.")
        return 1
    if not key.startswith("sk-ant-"):
        print("Warning: that does not look like an Anthropic key, storing anyway.")

    keyring.set_password(SERVICE, ACCOUNT, key)
    print("\nSaved. `python main.py \"...\"` will now find it automatically.")
    print("You do not need a .env file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
