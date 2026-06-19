import { Badge } from '../ui/badge';
import { cn } from '../../lib/utils';
import { RouterStatus } from '../../types/routers';

const statusColorMap: Record<RouterStatus, string> = {
  online: 'bg-green-100 text-green-800 hover:bg-green-100',
  offline: 'bg-red-100 text-red-800 hover:bg-red-100',
  unknown: 'bg-gray-100 text-gray-800 hover:bg-gray-100',
  pending_setup: 'bg-amber-100 text-amber-800 hover:bg-amber-100',
  testing: 'bg-blue-100 text-blue-800 hover:bg-blue-100',
};

interface RouterStatusBadgeProps {
  status: RouterStatus;
  className?: string;
}

export function RouterStatusBadge({ status, className }: RouterStatusBadgeProps) {
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
