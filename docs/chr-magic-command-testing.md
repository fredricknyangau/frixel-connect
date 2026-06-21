# CHR Magic Command Testing Guide

**ZealSync Magic Command Router Onboarding — MikroTik CHR on VirtualBox**

This document walks through the complete end-to-end test of the Magic Command
onboarding flow using MikroTik CHR (Cloud Hosted Router) running in VirtualBox.

> **CHR vs Physical MikroTik differences are highlighted with ⚠️ CHR markers.**
> Everything marked ⚠️ CHR is specific to the VirtualBox test environment.
> A physical MikroTik in production requires none of these workarounds.

---

## 1. Prerequisites Checklist

Complete ALL of these before proceeding. Skip none — each prerequisite
is a dependency of the next.

### 1.1 VirtualBox and CHR VM

```bash
# Verify CHR VM is running
vboxmanage list runningvms | grep -i chr
# Expected: something like "MikroTik CHR" {xxxxxxxx-xxxx-...}

# If not running, start it
vboxmanage startvm "MikroTik CHR" --type headless
```

Verify the CHR has both network interfaces:
- **Adapter 1 (ether1):** NAT — gives CHR internet access for downloads
- **Adapter 2 (ether2):** Host-Only (vboxnet0) — gives Ubuntu host access at 192.168.56.1

⚠️ **CHR:** If you only have one adapter, add a host-only adapter in VirtualBox
Settings → Network → Adapter 2 → Host-Only Adapter → vboxnet0.

### 1.2 CHR SSH Access

```bash
# SSH into CHR from Ubuntu
ssh admin@192.168.56.100

# If you get "Connection refused", check CHR's IP:
# In Winbox or CHR console: /ip address print
# The host-only interface should show 192.168.56.100/24
```

### 1.3 CHR REST API Reachable

```bash
# From Ubuntu, test CHR REST API
# Replace 'yourpassword' with your CHR admin password
curl -s -u admin:yourpassword http://192.168.56.100/rest/ip/hotspot/user/profile | python3 -m json.tool
# Expected: JSON array (may be empty [] if no profiles yet)
```

If this returns a connection error, check CHR:
```
/ip service print where name=www
```
The `www` service should be enabled with port 80. If disabled:
```
/ip service enable www
/ip service set www port=80
```

### 1.4 ZealSync Backend Running

```bash
# From Ubuntu
docker compose ps
# Expected: wifi_billing_api shows "Up" and "0.0.0.0:8000->8000/tcp"

# Test health
curl -s http://localhost:8000/health
# Expected: {"status":"ok","service":"WiFi Billing System",...}

# Also test that CHR can reach the backend (from CHR console):
# /tool fetch url="http://192.168.56.1:8000/health" mode=http output=user
# Expected: "status":"ok" in the output
```

⚠️ **CHR:** The backend is at `192.168.56.1:8000` from CHR's perspective
(Ubuntu's host-only adapter IP). This is NOT localhost from CHR's perspective.

### 1.5 Admin Logged In on Frontend

Open `http://localhost` or `http://localhost:5173` (dev server) in your browser.
Log in as the admin user for the test tenant.

### 1.6 CHR Has Internet Access (for ether1)

⚠️ **CHR:** The `/tool fetch` command needs to reach the backend, NOT the internet.
But CHR needs NAT working for DNS. Verify:
```
# In CHR console
/tool fetch url="http://192.168.56.1:8000/health" mode=http output=user
# Expected: {"status":"ok",...}
```

If this works, CHR → Backend connectivity is confirmed.

---

## 2. Generate the Magic Command

### 2.1 Open the Admin Portal

Navigate to: `http://localhost/admin/routers` (or `http://localhost:5173/admin/routers`)

Click **"Connect Router"** in the top-right.

### 2.2 Fill in the Details Form

| Field | Value |
|-------|-------|
| Router Name | `CHR Test 01` |
| Site Name | `Local Dev` |
| CHR Mode Toggle | **ON** (enable the switch) |

When CHR mode is ON, you'll see the amber banner:
> ⚠ CHR mode active — commands use your local IP (192.168.56.1). WireGuard is skipped...

### 2.3 Generate the Command

Click **"Generate Setup Command"**.

The button shows a spinner briefly, then the **command step** appears with:
- A dark terminal code block containing the magic command
- A "Copy Command" button
- Three numbered instructions
- A grey pulse dot: "Waiting for your router to connect..."

The command should look like:
```
/tool fetch url="http://192.168.56.1:8000/api/v1/setup/XXXXXXXXXXXXXXXXXXXXXXXXXX" dst-path=zealsync-setup.rsc mode=http; /import zealsync-setup.rsc
```

⚠️ **CHR:** Note `http://` (not `https://`) and `192.168.56.1:8000` (not `api.zealsync.dev`).

### 2.4 Copy the Command

Click **"Copy Command"**. The button changes to **"Copied! ✓"** for 2 seconds.

---

## 3. Run the Command on CHR

### 3.1 Open CHR SSH Session

```bash
# From Ubuntu
ssh admin@192.168.56.100
# Press Enter for password if it's blank, or type your password
```

### 3.2 Paste and Execute

Paste the copied command and press Enter:

```
[admin@MikroTik] > /tool fetch url="http://192.168.56.1:8000/api/v1/setup/XXXXXXXX..." dst-path=zealsync-setup.rsc mode=http; /import zealsync-setup.rsc
```

### 3.3 Expected Output Sequence

```
      status: fetching...
      status: connecting...
      status: verifying content...
      status: downloading...
         url: http://192.168.56.1:8000/api/v1/setup/XXXXXXXX...
   file-name: zealsync-setup.rsc

Opening script file zealsync-setup.rsc
Script file loaded and executed successfully
```

After the import starts, you'll see log entries (check with `/log print`):
```
ZealSync: Starting auto-configuration for router: CHR Test 01
ZealSync: CHR mode - skipping WireGuard setup (same-machine networking)
ZealSync: Creating API user and permissions group...
ZealSync: Enabling REST API on port 80...
ZealSync: Creating hotspot speed profiles...
ZealSync: Configuring API firewall rule (CHR host-only mode)...
ZealSync: Setting router identity...
ZealSync: Notifying ZealSync server of successful setup...
ZealSync: Setup complete! Router is now connected to ZealSync.
```

### 3.4 Troubleshooting the Fetch Step

**Problem:** `failed: Connection refused`
- Check: Is the backend running? `docker compose ps`
- Check: Is `192.168.56.1` correct? Run `ip addr show vboxnet0` on Ubuntu
- Check: Is there a firewall blocking port 8000? `sudo ufw status`

**Problem:** `failed: no such file or directory`
- The token was already used. Generate a new command in the admin portal.

**Problem:** `failed: TLS handshake failed`
- CHR mode should use `mode=http`, not `mode=https`.
  Check that you enabled the CHR toggle before clicking Generate.

---

## 4. Verify Each Script Action on CHR

After the script runs, verify in the CHR SSH session:

### 4.1 API User Created

```
/user print where name=zealsync-api
```

**Expected:**
```
Flags: X - disabled
 #   NAME         GROUP              LAST-LOGGED-IN
 0   zealsync-api zealsync-api-group never
```

### 4.2 API User Group Created

```
/user group print where name=zealsync-api-group
```

**Expected:**
```
 # NAME               POLICY
 0 zealsync-api-group api,read,write,test,...
```

### 4.3 REST API Enabled

```
/ip service print where name=www
```

**Expected:**
```
Flags: X - invalid; D - dynamic
 #   NAME   PORT   ADDRESS   CERTIFICATE   TLS-VERSION
 0   www     80               none
```

The row should NOT have `X` at the start (X means disabled).

### 4.4 Hotspot Speed Profiles Created

```
/ip hotspot user profile print
```

**Expected:** Three profiles:
```
 #   NAME    RATE-LIMIT   SHARED-USERS
 0   10Mbps  10M/10M      1
 1   20Mbps  20M/20M      1
 2   50Mbps  50M/50M      1
```

(There may also be a `default` profile which is pre-existing.)

### 4.5 Firewall Rule Added

```
/ip firewall filter print where comment~"ZealSync"
```

**Expected:**
```
 0  chain=input action=accept protocol=tcp src-address=192.168.56.0/24 dst-port=80 comment="ZealSync API access from dev host"
```

⚠️ **CHR:** The source address is `192.168.56.0/24` (host-only network).
For a physical MikroTik in production, this would be `10.8.0.1/32` (WG VPN IP).

### 4.6 Router Identity Updated

```
/system identity print
```

**Expected:**
```
name: zealsync-CHR Test 01
```

### 4.7 Script Self-Deleted

```
/file print where name=zealsync-setup.rsc
```

**Expected:** Empty result (no output). The script deleted itself in Section 8.

If the script is still there, it means the setup did not complete.
Check `/log print` for errors.

---

## 5. Verify on the Frontend

### 5.1 Check the Wizard Advanced

Within 3 seconds of the router calling `/confirm`, the wizard should automatically
advance to the **"Router Connected!"** complete screen.

You should see:
- ✅ Animated checkmark drawing itself
- "Router Connected!" title
- Summary card showing:
  - Router name: CHR Test 01
  - Site: Local Dev
  - Status: ✅ Online
  - Network: Local (VirtualBox host-only)
  - API user: zealsync-api ✅ Created
  - Speed tiers: 10 / 20 / 50 Mbps ✅ Created

### 5.2 If the Wizard Didn't Advance

**Step 1:** Check FastAPI logs for the confirm call:
```bash
docker compose logs api --tail=50 | grep "confirm"
```

**Step 2:** Manually trigger the confirm (simulates what the router does):
```bash
# Get the token from the frontend URL or localStorage
TOKEN="your_token_here"
curl -X POST http://localhost:8000/api/v1/setup/${TOKEN}/confirm
# Expected: {"status":"confirmed","router_id":"..."}
```

**Step 3:** Check the router status directly:
```bash
# Get the router_id from the admin portal URL or response
ROUTER_ID="your_router_id_here"
TOKEN_HEADER="Authorization: Bearer $(cat ~/.zealsync_dev_token)"
curl -s -H "$TOKEN_HEADER" http://localhost:8000/api/v1/admin/routers/onboarding/status/${ROUTER_ID}
# Expected: {"router_id":"...","status":"online"}
```

**Step 4:** Check the database:
```bash
docker compose exec db psql -U zealnet -d wifi_billing \
  -c "SELECT name, status, last_heartbeat_at FROM routers WHERE name='CHR Test 01';"
# Expected: status=online, last_heartbeat_at IS NOT NULL
```

**Step 5:** Check that the token was consumed:
```bash
docker compose exec db psql -U zealnet -d wifi_billing \
  -c "SELECT token, used_at, router_wg_private_key FROM setup_tokens ORDER BY created_at DESC LIMIT 1;"
# Expected: used_at IS NOT NULL, router_wg_private_key IS NULL
```

---

## 6. Verify the API Works

From Ubuntu, test the freshly configured REST API:

```bash
# Get the encrypted password from the DB
ENCRYPTED_PW=$(docker compose exec -T db psql -U zealnet -d wifi_billing -t \
  -c "SELECT password_encrypted FROM routers WHERE name='CHR Test 01';" | tr -d ' \n')

# Decrypt it in Python
API_PW=$(docker compose exec api python -c "
from app.core.security import decrypt_secret
print(decrypt_secret('${ENCRYPTED_PW}'))
")

echo "API Password: ${API_PW}"

# Test the REST API with the decrypted password
curl -s -u "zealsync-api:${API_PW}" \
  http://192.168.56.100/rest/ip/hotspot/user/profile \
  | python3 -m json.tool
```

**Expected:** JSON array with three profile objects:
```json
[
    {".id": "*1", "name": "10Mbps", "rate-limit": "10M/10M", ...},
    {".id": "*2", "name": "20Mbps", "rate-limit": "20M/20M", ...},
    {".id": "*3", "name": "50Mbps", "rate-limit": "50M/50M", ...}
]
```

If authentication fails (401), double-check the username is `zealsync-api` (not `admin`).

---

## 7. Full Billing Pipeline Test

With the router now connected and verified, test the complete billing pipeline:

### 7.1 Create a Test Voucher

In the admin portal, navigate to **Vouchers** → **Generate Vouchers**.
Select the "CHR Test 01" router, choose a package (e.g., 10Mbps), generate 1 voucher.
Note the voucher code.

### 7.2 Fire a Test Payment Webhook

```bash
# Simulate M-Pesa STK push confirmation
curl -X POST http://localhost:8000/api/v1/webhooks/mpesa/stk-callback \
  -H "Content-Type: application/json" \
  -d '{
    "Body": {
      "stkCallback": {
        "MerchantRequestID": "test-001",
        "CheckoutRequestID": "test-001",
        "ResultCode": 0,
        "ResultDesc": "The service request is processed successfully.",
        "CallbackMetadata": {
          "Item": [
            {"Name": "Amount", "Value": 100},
            {"Name": "MpesaReceiptNumber", "Value": "TEST0001"},
            {"Name": "PhoneNumber", "Value": 254712345678}
          ]
        }
      }
    }
  }'
```

### 7.3 Verify Hotspot User Created on CHR

```
# On CHR console
/ip hotspot user print
```

The voucher code should appear as a hotspot user.

### 7.4 Revoke and Verify

Revoke the voucher in the admin portal. Then on CHR:
```
/ip hotspot user print
```

The hotspot user for the revoked voucher should be gone.

---

## 8. What Changes for a Physical MikroTik

| Aspect | CHR (this guide) | Physical MikroTik |
|--------|-----------------|-------------------|
| CHR Mode toggle | ✅ ON | ❌ OFF |
| Script URL | `http://192.168.56.1:8000/...` | `https://api.zealsync.dev/...` |
| WireGuard section | Skipped | Full setup |
| Confirm URL | `http://192.168.56.1:8000/...` | `https://api.zealsync.dev/...` |
| Firewall rule | `192.168.56.0/24` | `10.8.0.1/32` (WG VPN only) |
| HTTPS | Not needed (local) | Required (public internet) |
| Token must work | Same | Same |

**When moving to a physical MikroTik:**
1. Ensure `MOCK_WIREGUARD=False` in production `.env`
2. Ensure the WireGuard server (`wg0`) is running on the Ubuntu/Oracle Cloud host
3. Turn OFF the CHR mode toggle when generating the command
4. The router needs a path to the public internet to reach `api.zealsync.dev`

---

## 9. Database Cleanup (After Testing)

To reset and run the test again:

```bash
# Delete the test router (cascade deletes the setup_token too)
docker compose exec db psql -U zealnet -d wifi_billing \
  -c "DELETE FROM routers WHERE name='CHR Test 01';"

# Verify cleanup
docker compose exec db psql -U zealnet -d wifi_billing \
  -c "SELECT count(*) FROM setup_tokens;"
# Should be 0 if you only had the test token
```

On CHR, clean up the test configuration:
```
/user remove [find name=zealsync-api]
/user group remove [find name=zealsync-api-group]
/ip hotspot user profile remove [find comment~"ZealSync"]
/ip firewall filter remove [find comment~"ZealSync"]
/system identity set name=MikroTik
```
