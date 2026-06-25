import asyncio
import ipaddress
import os
import sys
from uuid import UUID
import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.integrations.mikrotik import get_mikrotik_client

tenant_id = UUID("aaaaaaaa-0000-0000-0000-000000000001")
ip_range = "10.10.10.1/24"
interface = "ether3"

async def main():
    print(f"Provisioning CHR router for tenant {tenant_id} on {interface} with IP range {ip_range}...")
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    try:
        row = await conn.fetchrow(
            "SELECT * FROM routers WHERE name = 'CHR Test 01' AND tenant_id = $1",
            tenant_id,
        )
        if not row:
            print("Router 'CHR' not found in database!")
            return

        router_id = row["id"]
        network = ipaddress.IPv4Network(ip_range, strict=False)
        hosts = list(network.hosts())
        gateway = str(hosts[0])
        pool_start = str(hosts[1])
        pool_end = str(hosts[-1])
        network_base = str(network.network_address)

        mikrotik = get_mikrotik_client(dict(row))

        frontend_url = getattr(settings, "FRONTEND_URL", "https://portal.zealsync.dev")
        radius_ip = "10.8.0.1"
        is_chr = "192.168.56." in row["host"]
        if is_chr:
            chr_host = getattr(settings, "CHR_HOST_IP", "192.168.56.1")
            frontend_url = getattr(settings, "CHR_FRONTEND_URL", f"http://{chr_host}")
            radius_ip = chr_host
            chr_port = getattr(settings, "CHR_BACKEND_PORT", 8000)
            backend_base = f"http://{chr_host}:{chr_port}"
        else:
            backend_base = settings.API_BASE_URL
            
        radius_secret = settings.RADIUS_COA_SECRET
        
        import urllib.parse
        encoded_frontend_url = urllib.parse.quote(frontend_url, safe="")
        login_html_url = f"{backend_base}/api/v1/hotspot/login.html?tenant_id={tenant_id}&frontend_url={encoded_frontend_url}"
        
        print("Creating speed profiles...")
        await mikrotik.create_speed_profiles()
        print("Setting up hotspot server...")
        await mikrotik.setup_hotspot_server(
            interface=interface,
            gateway=gateway,
            network_base=network_base,
            pool_start=pool_start,
            pool_end=pool_end,
            frontend_url=frontend_url,
            tenant_id=str(tenant_id),
            radius_ip=radius_ip,
            radius_secret=radius_secret,
            login_html_url=login_html_url,
        )
        
        await conn.execute(
            "UPDATE routers SET status = 'online' WHERE id = $1", router_id
        )
        print("Successfully provisioned!")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
