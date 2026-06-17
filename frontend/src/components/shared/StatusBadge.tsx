import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';

type StatusType =
  | 'pending'
  | 'confirmed'
  | 'failed'
  | 'cancelled'
  | 'active'
  | 'used'
  | 'expired'
  | 'revoked';

const statusColorMap: Record<StatusType, string> = {
  pending: 'bg-amber-100 text-amber-800 hover:bg-amber-100',
  confirmed: 'bg-green-100 text-green-800 hover:bg-green-100',
  failed: 'bg-red-100 text-red-800 hover:bg-red-100',
  cancelled: 'bg-gray-100 text-gray-800 hover:bg-gray-100',
  active: 'bg-green-100 text-green-800 hover:bg-green-100',
  used: 'bg-blue-100 text-blue-800 hover:bg-blue-100',
  expired: 'bg-gray-100 text-gray-800 hover:bg-gray-100',
  revoked: 'bg-red-100 text-red-800 hover:bg-red-100',
};

interface StatusBadgeProps {
  status: StatusType;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const colorClass = statusColorMap[status] || 'bg-gray-100 text-gray-800';

  return (
    <Badge
      variant="outline"
      className={cn('capitalize border-transparent', colorClass, className)}
    >
      {status}
    </Badge>
  );
}
