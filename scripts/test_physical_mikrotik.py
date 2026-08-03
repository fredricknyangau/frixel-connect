#!/usr/bin/env python3
"""
scripts/test_physical_mikrotik.py
==================================
Verification script to test physical connection, REST API calls,
and user lifecycle directly against a real MikroTik CHR over WireGuard.

Usage:
  export MIKROTIK_VPN_IP=10.8.0.2
  export MIKROTIK_PORT=80
  export MIKROTIK_USERNAME=Frixel Connect-api
  export MIKROTIK_PASSWORD=YourPassword
  python scripts/test_physical_mikrotik.py
"""

import os
import sys
import time
import subprocess
import requests

# Try to load environment variables from local .env
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

VPN_IP = os.getenv("MIKROTIK_VPN_IP") or os.getenv("MIKROTIK_HOST")
PORT = os.getenv("MIKROTIK_PORT", "80")
USERNAME = os.getenv("MIKROTIK_USERNAME", "Frixel Connect-api")
PASSWORD = os.getenv("MIKROTIK_PASSWORD")

if not VPN_IP:
    print("[-] Error: MIKROTIK_VPN_IP or MIKROTIK_HOST environment variable is not set.")
    sys.exit(1)

if not PASSWORD:
    print("[-] Error: MIKROTIK_PASSWORD environment variable is not set.")
    sys.exit(1)

BASE_URL = f"http://{VPN_IP}:{PORT}/rest"
AUTH = (USERNAME, PASSWORD)
HEADERS = {"Content-Type": "application/json"}

print("============================================================")
print("  PHYSICAL MIKROTIK CONNECTION VERIFICATION TEST  ")
print("============================================================")
print(f"  Target IP:   {VPN_IP}")
print(f"  Port:        {PORT}")
print(f"  Username:    {USERNAME}")
print(f"  Base URL:    {BASE_URL}")
print("============================================================\n")


def run_step(step_name, fn):
    print(f"[*] Step: {step_name}...")
    start_time = time.time()
    try:
        success, message = fn()
        elapsed = (time.time() - start_time) * 1000
        if success:
            print(f"[+] PASS: {step_name} ({elapsed:.1f}ms) - {message}\n")
            return True
        else:
            print(f"[-] FAIL: {step_name} ({elapsed:.1f}ms) - {message}\n")
            return False
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        print(f"[-] FAIL: {step_name} ({elapsed:.1f}ms) - Exception: {e}\n")
        return False


# Step 1: Ping the Router over WireGuard
def test_ping():
    try:
        # Pings 3 times, wait up to 2 seconds per ping
        res = subprocess.run(
            ["ping", "-c", "3", "-W", "2", VPN_IP],
            capture_output=True,
            text=True,
            timeout=8
        )
        if res.returncode == 0:
            return True, "Ping successful, host is reachable."
        return False, f"Ping failed with return code {res.returncode}. Output:\n{res.stderr or res.stdout}"
    except Exception as e:
        return False, str(e)


# Step 2: Fetch and list hotspot profiles
def test_get_profiles():
    url = f"{BASE_URL}/ip/hotspot/user/profile"
    resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=8)
    if resp.status_code == 200:
        profiles = resp.json()
        profile_names = [p.get("name", "") for p in profiles]
        return True, f"Found profiles: {profile_names}"
    return False, f"API returned status code {resp.status_code}: {resp.text}"


# Step 3: Create a test hotspot user PHYSTEST001
def test_create_user():
    url = f"{BASE_URL}/ip/hotspot/user/add"
    payload = {
        "name": "PHYSTEST001",
        "password": "PHYSTEST001_password",
        "profile": "default",
        "comment": "Frixel Connect-physical-test"
    }
    resp = requests.post(url, json=payload, auth=AUTH, headers=HEADERS, timeout=8)
    if resp.status_code in (200, 201):
        return True, f"User created. ID: {resp.json().get('ret')}"
    return False, f"API returned status code {resp.status_code}: {resp.text}"


# Step 4: Verify user exists
def test_verify_user_exists():
    url = f"{BASE_URL}/ip/hotspot/user"
    resp = requests.get(url, params={"name": "PHYSTEST001"}, auth=AUTH, headers=HEADERS, timeout=8)
    if resp.status_code == 200:
        users = resp.json()
        if users and users[0].get("name") == "PHYSTEST001":
            return True, f"Verified user exists with internal .id: {users[0].get('.id')}"
        return False, "User PHYSTEST001 not found in users list."
    return False, f"API returned status code {resp.status_code}: {resp.text}"


# Step 5: Delete user PHYSTEST001
def test_delete_user():
    # Find .id first
    url_find = f"{BASE_URL}/ip/hotspot/user"
    resp_find = requests.get(url_find, params={"name": "PHYSTEST001"}, auth=AUTH, headers=HEADERS, timeout=8)
    if resp_find.status_code != 200 or not resp_find.json():
        return False, "Could not find user .id to delete."
    
    internal_id = resp_find.json()[0].get(".id")
    url_delete = f"{BASE_URL}/ip/hotspot/user/{internal_id}"
    resp_delete = requests.delete(url_delete, auth=AUTH, headers=HEADERS, timeout=8)
    if resp_delete.status_code in (200, 204):
        return True, "User successfully deleted."
    return False, f"Delete failed with status code {resp_delete.status_code}: {resp_delete.text}"


# Step 6: Verify user is deleted
def test_verify_user_deleted():
    url = f"{BASE_URL}/ip/hotspot/user"
    resp = requests.get(url, params={"name": "PHYSTEST001"}, auth=AUTH, headers=HEADERS, timeout=8)
    if resp.status_code == 200:
        users = resp.json()
        if not users:
            return True, "Verified user is gone."
        return False, f"User still exists: {users}"
    return False, f"API returned status code {resp.status_code}: {resp.text}"


def main():
    steps = [
        ("Ping MikroTik", test_ping),
        ("Get Hotspot User Profiles", test_get_profiles),
        ("Create Test User", test_create_user),
        ("Verify User Exists", test_verify_user_exists),
        ("Delete Test User", test_delete_user),
        ("Verify User Deleted", test_verify_user_deleted),
    ]

    all_passed = True
    for name, fn in steps:
        success = run_step(name, fn)
        if not success:
            all_passed = False

    print("============================================================")
    if all_passed:
        print("  OVERALL RESULT: PASS  ")
    else:
        print("  OVERALL RESULT: FAIL  ")
    print("============================================================")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
