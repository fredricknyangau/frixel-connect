import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { superAdminApi } from '../lib/superAdminApi';
import { useSuperAdminAuth } from '../context/SuperAdminAuthContext';
import {
  SuperAdminPreAuthResponse,
  SuperAdminTOTPSetupResponse,
  SuperAdminTokenResponse,
} from '../types/superAdmin';
import { LoginRequest } from '../types/auth';

/**
 * usePasswordLogin
 * Step 1 of the super admin authentication process.
 * Sends email and password to POST /super-admin/auth/login.
 * On success, saves the short-lived pre-auth token in the auth context
 * and moves the loginStep to either 'totp_setup' or 'totp_verify'.
 */
export const usePasswordLogin = () => {
  const { setPreAuthToken, setLoginStep } = useSuperAdminAuth();

  return useMutation<
    SuperAdminPreAuthResponse,
    AxiosError<{ detail: string }>,
    LoginRequest
  >({
    mutationFn: async (data) => {
      const response = await superAdminApi.post<SuperAdminPreAuthResponse>(
        '/super-admin/auth/login',
        data
      );
      return response.data;
    },
    onSuccess: (data) => {
      setPreAuthToken(data.pre_auth_token);
      setLoginStep(data.totp_setup_required ? 'totp_setup' : 'totp_verify');
    },
  });
};

/**
 * useTOTPSetup
 * Requests TOTP setup credentials (QR code base64 and secret preview)
 * for first-time super admin login.
 * Sends pre_auth_token to POST /super-admin/auth/totp/setup.
 */
export const useTOTPSetup = () => {
  return useMutation<
    SuperAdminTOTPSetupResponse,
    AxiosError<{ detail: string }>,
    { pre_auth_token: string }
  >({
    mutationFn: async ({ pre_auth_token }) => {
      const response = await superAdminApi.post<SuperAdminTOTPSetupResponse>(
        '/super-admin/auth/totp/setup',
        { pre_auth_token }
      );
      return response.data;
    },
  });
};

/**
 * useTOTPVerify
 * Step 2 of the super admin authentication process.
 * Verifies the 6-digit TOTP code using the pre-auth token.
 * Sends credentials to POST /super-admin/auth/totp/verify.
 * On success, initializes the authenticated session and redirects to dashboard.
 */
export const useTOTPVerify = () => {
  const { login } = useSuperAdminAuth();
  const navigate = useNavigate();

  return useMutation<
    SuperAdminTokenResponse,
    AxiosError<{ detail: string }>,
    { pre_auth_token: string; totp_code: string }
  >({
    mutationFn: async (data) => {
      const response = await superAdminApi.post<SuperAdminTokenResponse>(
        '/super-admin/auth/totp/verify',
        data
      );
      return response.data;
    },
    onSuccess: (data) => {
      login(data.access_token, {
        id: data.super_admin_id,
        full_name: data.full_name,
      });
      navigate('/super-admin/dashboard');
    },
  });
};
