import { useState, useMemo } from 'react';
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';

import { useAdminSessions } from '../../hooks/useSessions';
import { useAdminCustomers } from '../../hooks/useUsers';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatNairobiDate, formatBytes } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';

const ITEMS_PER_PAGE = 10;

export default function SessionsPage() {
  const { data: sessions, isLoading } = useAdminSessions();
  const { data: customers } = useAdminCustomers();

  const [currentPage, setCurrentPage] = useState(1);

  const sortedSessions = useMemo(() => {
    if (!sessions) return [];
    return [...sessions].sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
  }, [sessions]);

  const totalPages = Math.ceil(sortedSessions.length / ITEMS_PER_PAGE);
  
  const currentSessions = useMemo(() => {
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    return sortedSessions.slice(startIndex, startIndex + ITEMS_PER_PAGE);
  }, [sortedSessions, currentPage]);

  const getCustomerPhone = (customerId: string) => customers?.find(c => c.id === customerId)?.phone || 'Unknown';

  const handlePrevPage = () => {
    setCurrentPage(prev => Math.max(1, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage(prev => Math.min(totalPages, prev + 1));
  };

  return (
    <div className="space-y-6">
      <PageTitle title="Network Sessions | ZealSync Admin" />

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Active & Past Sessions</h2>
          <p className="text-muted-foreground">Monitor customer network connections and data usage.</p>
        </div>
      </div>

      <div className="rounded-md border bg-background overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>IP Address</TableHead>
              <TableHead>MAC Address</TableHead>
              <TableHead>Data Up</TableHead>
              <TableHead>Data Down</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Ended</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : currentSessions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                  No sessions found.
                </TableCell>
              </TableRow>
            ) : (
              currentSessions.map((session) => (
                <TableRow key={session.id}>
                  <TableCell className="font-medium">{getCustomerPhone(session.customer_id)}</TableCell>
                  <TableCell>
                    {session.ended_at ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">Closed</span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Active</span>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-sm">{session.ip_address}</TableCell>
                  <TableCell className="font-mono text-sm">{session.mac_address}</TableCell>
                  <TableCell>{formatBytes(session.bytes_uploaded)}</TableCell>
                  <TableCell>{formatBytes(session.bytes_downloaded)}</TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatNairobiDate(session.started_at)}
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {session.ended_at ? formatNairobiDate(session.ended_at) : '-'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {(currentPage - 1) * ITEMS_PER_PAGE + 1} to {Math.min(currentPage * ITEMS_PER_PAGE, sortedSessions.length)} of {sortedSessions.length} entries
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrevPage}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNextPage}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}