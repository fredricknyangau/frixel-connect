/**
 * src/types/setup.ts
 * ==================
 * TypeScript types for the Magic Command router onboarding flow.
 *
 * These types correspond to the backend schemas defined in:
 *   app/modules/routers/schemas.py-MagicInitRequest, MagicInitResponse, RouterStatusResponse
 */

/**
 * Response from POST /api/v1/admin/routers/onboarding/init-magic
 * Contains everything the wizard needs to display the command step.
 */
export interface MagicInitResponse {
  /** UUID of the newly created router record (status='pending_setup') */
  router_id: string;

  /**
   * The raw setup token (43 characters, URL-safe base64).
   * Stored in state so we can build the resume URL if needed.
   * Never display the full token in the UI-it's a credential.
   */
  setup_token: string;

  /**
   * The complete one-line command to paste into MikroTik terminal.
   * Example (CHR):
   *   /tool fetch url="http://192.168.56.1:8000/api/v1/setup/TOKEN" dst-path=Frixel Connect-setup.rsc mode=http; /import Frixel Connect-setup.rsc
   * Example (Production):
   *   /tool fetch url="https://api.Frixel Connect.dev/api/v1/setup/TOKEN" dst-path=Frixel Connect-setup.rsc mode=https; /import Frixel Connect-setup.rsc
   */
  magic_command: string;

  /** ISO 8601 timestamp-24 hours from when init-magic was called */
  expires_at: string;

  /**
   * True if this command was generated for CHR (VirtualBox) testing.
   * Used to show the CHR warning banner in the UI.
   */
  is_chr: boolean;
}

/**
 * Response from GET /api/v1/admin/routers/onboarding/status/{router_id}
 * Polled every 3 seconds by the wizard's command step.
 *
 * Status lifecycle:
 *   pending_setup → (router calls /confirm) → online
 *   pending_setup → (token expires) → wizard shows expired error
 */
export interface RouterStatusResponse {
  router_id: string;
  /**
   * 'pending_setup' = router hasn't called /confirm yet
   * 'online'        = router completed setup, wizard should advance to complete
   * 'offline'       = heartbeat missed (only after online, not during setup)
   * 'failed'        = setup failed (future: explicit failure mode)
   */
  status: 'pending_setup' | 'online' | 'offline' | 'failed' | string;
}
