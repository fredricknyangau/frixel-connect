import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuthContext } from '../context/AuthContext';
import { LoginRequest, RegisterRequest, TokenResponse, UserRole } from '../types/auth';
import { AxiosError } from 'axios';

const navigateBasedOnRole = (role: UserRole, navigate: ReturnType<typeof useNavigate>) => {
  if (role === 'admin') navigate('/admin/dashboard');
  else if (role === 'reseller') navigate('/reseller/dashboard');
  else if (role === 'customer') navigate('/customer/dashboard');
};

export const useLogin = () => {
  const { login } = useAuthContext();
  const navigate = useNavigate();

  return useMutation<TokenResponse, AxiosError<{ detail: string }>, LoginRequest>({
    mutationFn: async (data) => {
      const response = await api.post<TokenResponse>('/auth/login', data);
      return response.data;
    },
    onSuccess: (data) => {
      login(data.access_token);
      navigateBasedOnRole(data.role, navigate);
    },
  });
};

export const useRegister = () => {
  const { login } = useAuthContext();
  const navigate = useNavigate();

  // For 409 errors we might receive { detail: string }
  return useMutation<TokenResponse, AxiosError<{ detail: string }>, RegisterRequest>({
    mutationFn: async (data) => {
      const response = await api.post<TokenResponse>('/auth/register', data);
      return response.data;
    },
    onSuccess: (data) => {
      login(data.access_token);
      navigateBasedOnRole(data.role, navigate);
    },
  });
};
