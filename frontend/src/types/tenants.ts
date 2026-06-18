export interface Tenant {
  id: string;
  business_name: string;
  owner_email: string;
  owner_phone: string;
  subscription_tier: 'starter' | 'growth' | 'scale' | 'enterprise';
  max_customers: number;
  status: 'active' | 'suspended' | 'cancelled';
  current_customer_count: number;
  billing_status: 'active' | 'grace' | 'suspended';
  next_billing_date: string;
  created_at: string;
}

export interface TenantRegisterRequest {
  business_name: string;
  owner_email: string;
  owner_phone: string;
  password: string;
  subscription_tier: Tenant['subscription_tier'];
}
