"""
Generate Polymarket CLOB API credentials from your private key.

Usage:
    POLYMARKET_PRIVATE_KEY=0x... python scripts/generate_clob_creds.py

This will print the three values you need to set in Railway:
    POLYMARKET_API_KEY
    POLYMARKET_API_SECRET
    POLYMARKET_API_PASSPHRASE
"""
import os
import sys

def main():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    if not pk:
        print("ERROR: Set POLYMARKET_PRIVATE_KEY environment variable first.")
        print("  export POLYMARKET_PRIVATE_KEY=0xYourPrivateKeyHere")
        sys.exit(1)

    from py_clob_client.client import ClobClient

    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=pk,
    )

    print("Deriving/creating CLOB API credentials...")
    creds = client.create_or_derive_api_creds()
    print()
    print("=" * 60)
    print("Set these in Railway environment variables:")
    print("=" * 60)
    print(f"POLYMARKET_API_KEY={creds.api_key}")
    print(f"POLYMARKET_API_SECRET={creds.api_secret}")
    print(f"POLYMARKET_API_PASSPHRASE={creds.api_passphrase}")
    print("=" * 60)


if __name__ == "__main__":
    main()
