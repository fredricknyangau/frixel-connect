export interface WireGuardParams {
  serverPublicKey: string;
  serverEndpoint: string;
  assignedIp: string;
}

export const ROUTEROS_COMMANDS = {
  v7: {
    wireguard_setup: (params: WireGuardParams) => {
      const endpointParts = params.serverEndpoint.split(':');
      const host = endpointParts[0];
      const port = endpointParts[1] || '51820';
      return `/interface wireguard add name=wg-zealsync
/interface wireguard peers add \\
  interface=wg-zealsync \\
  public-key="${params.serverPublicKey}" \\
  endpoint-address=${host} \\
  endpoint-port=${port} \\
  allowed-address=10.8.0.1/32 \\
  persistent-keepalive=25s
/ip address add \\
  address=${params.assignedIp.split('/')[0]}/24 \\
  interface=wg-zealsync`;
    },
    get_public_key: `/interface wireguard print
# Look for the 'public-key' column under the 'wg-zealsync' interface`,
    create_api_user: (password: string) => `/user group add name=zealsync-api-group policy=api,read,write,test
/user add name=zealsync-api \\
  password=${password} \\
  group=zealsync-api-group`,
    enable_rest_api: (port: number) => `/ip service enable www
/ip service set www port=${port}`,
    create_hotspot_profile: (name: string, rateLimit: string) => `/ip hotspot user profile add name="${name}" rate-limit="${rateLimit}"`,
    verify_tunnel: `/ping 10.8.0.1 count=3`,
    verify_api: `/ip service print`,
  },
  v6: {
    wireguard_setup: () => `# WireGuard is NOT supported natively on RouterOS v6.
# You must upgrade your router to RouterOS v7 to use ZealSync VPN onboarding.
# Alternatively, configure a custom SSTP/PPTP/L2TP client to 10.8.0.1 manually.`,
    get_public_key: `# WireGuard not supported on v6. No public key available.`,
    create_api_user: (password: string) => `/user group add name=zealsync-api-group policy=api,read,write,test
/user add name=zealsync-api \\
  password=${password} \\
  group=zealsync-api-group`,
    enable_router_api: (port: number) => `/ip service enable api
/ip service set api port=${port}`,
    create_hotspot_profile: (name: string, rateLimit: string) => `/ip hotspot user profile add name="${name}" rate-limit="${rateLimit}"`,
    verify_tunnel: `/ping 10.8.0.1 count=3`,
    verify_api: `/ip service print`,
  }
};

export const WINBOX_PATHS = {
  v7: {
    wireguard: `1. Go to "WireGuard" tab in sidebar
2. Click "+" (Add New)
3. Set Name to: wg-zealsync. Click Apply/OK
4. Go to "Peers" sub-tab, click "+" (Add New)
5. Select Interface: wg-zealsync
6. Paste Public Key, Endpoint, Endpoint Port (51820)
7. Set Allowed IPs to: 10.8.0.1/32
8. Set Persistent Keepalive to: 25
9. Click OK
10. Go to "IP" -> "Addresses", click "+" (Add New)
11. Set Address to: [YOUR_ASSIGNED_IP]/24
12. Select Interface: wg-zealsync. Click OK`,
    get_public_key: `1. Go to "WireGuard" tab in sidebar
2. Double-click "wg-zealsync" interface
3. Copy the value in the "Public Key" field`,
    api_user: `1. Go to "System" -> "Users"
2. Click "Groups" tab, click "+" (Add New)
3. Name: zealsync-api-group, check: api, read, write, test. Click OK
4. Click "Users" tab, click "+" (Add New)
5. Name: zealsync-api, Group: zealsync-api-group, Password: [YOUR_PASSWORD]. Click OK`,
    enable_rest_api: `1. Go to "IP" -> "Services"
2. Select "www", click the Green Checkmark to Enable
3. Double-click "www" to change Port to 80 (or desired port)`,
    hotspot_profile: `1. Go to "IP" -> "Hotspot"
2. Select "User Profiles" tab, click "+" (Add New)
3. Name: [PROFILE_NAME] (e.g. 10Mbps)
4. Rate Limit (rx/tx): [RATE_LIMIT] (e.g. 10M/10M)
5. Click OK`,
  },
  v6: {
    wireguard: `Not supported on RouterOS v6. Please upgrade your firmware to RouterOS v7.`,
    get_public_key: `Not supported on RouterOS v6.`,
    api_user: `1. Go to "System" -> "Users"
2. Click "Groups" tab, click "+" (Add New)
3. Name: zealsync-api-group, check: api, read, write, test. Click OK
4. Click "Users" tab, click "+" (Add New)
5. Name: zealsync-api, Group: zealsync-api-group, Password: [YOUR_PASSWORD]. Click OK`,
    enable_router_api: `1. Go to "IP" -> "Services"
2. Select "api" (Port 8728), click the Green Checkmark to Enable
3. (Do NOT enable www REST API as it is not supported in RouterOS v6)`,
    hotspot_profile: `1. Go to "IP" -> "Hotspot"
2. Select "User Profiles" tab, click "+" (Add New)
3. Name: [PROFILE_NAME]
4. Rate Limit (rx/tx): [RATE_LIMIT]
5. Click OK`,
  }
};
