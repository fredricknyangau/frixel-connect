export type SubscriptionStatus = 'active' | 'grace' | 'suspended' | 'cancelled';

export interface Subscription {
  id: string;
  customer_id: string;
  package_id: string;
  package_name: string;
  status: SubscriptionStatus;
  current_period_end: string;
  auto_renew: boolean;
  created_at: string;
}
