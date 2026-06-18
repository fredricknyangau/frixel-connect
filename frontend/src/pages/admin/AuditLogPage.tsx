import React, { useState } from 'react';
import { useAuditLog } from '../../hooks/useSystemHealth';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatNairobiDate } from '../../lib/utils';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Loader2, ScrollText, ChevronDown, ChevronRight, ChevronLeft, ChevronRight as ChevronRightIcon } from 'lucide-react';

export default function AuditLogPage() {
  const [actionFilter, setActionFilter] = useState<string>('All');
  const [page, setPage] = useState(0);
  const limit = 20;
  const offset = page * limit;

  const { data: auditData, isLoading } = useAuditLog(actionFilter, limit, offset);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const toggleRow = (id: string) => {
    setExpandedRow(expandedRow === id ? null : id);
  };

  const KNOWN_ACTIONS = [
    'All',
    'tenant.registered',
    'tenant.suspended',
    'package.created',
    'router.created',
    'payment.received',
    'voucher.generated',
    'subscription.suspended',
    'subscription.reactivated',
    'customer.deleted'
  ];

  const totalItems = auditData?.total || 0;
  const hasMore = offset + limit < totalItems;

  return (
    <div className="space-y-6">
      <PageTitle title="Audit Log | Admin" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">System Audit Log</h2>
          <p className="text-muted-foreground">Immutable record of all critical system actions.</p>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <ScrollText className="h-5 w-5 text-muted-foreground" />
            Event History
          </CardTitle>
          <CardDescription>Track who did what, and when.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex justify-between items-center mb-4">
            <div className="w-full md:w-64">
              <Select value={actionFilter} onValueChange={(v) => { setActionFilter(v); setPage(0); }}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by action" />
                </SelectTrigger>
                <SelectContent>
                  {KNOWN_ACTIONS.map(action => (
                    <SelectItem key={action} value={action}>
                      {action === 'All' ? 'All Actions' : action}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>{auditData?.items.length || 0} items showing</span>
              <div className="flex gap-1 ml-2">
                <Button 
                  variant="outline" 
                  size="icon" 
                  className="h-8 w-8" 
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0 || isLoading}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button 
                  variant="outline" 
                  size="icon" 
                  className="h-8 w-8" 
                  onClick={() => setPage(p => p + 1)}
                  disabled={!hasMore || isLoading}
                >
                  <ChevronRightIcon className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>

          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10"></TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">
                      <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : !auditData || auditData.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      No audit logs found.
                    </TableCell>
                  </TableRow>
                ) : (
                  auditData.items.map((entry) => (
                    <React.Fragment key={entry.id}>
                      <TableRow 
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => toggleRow(entry.id)}
                      >
                        <TableCell>
                          {expandedRow === entry.id ? 
                            <ChevronDown className="h-4 w-4 text-muted-foreground" /> : 
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          }
                        </TableCell>
                        <TableCell>
                          <div className="font-medium text-sm">{entry.actor_email}</div>
                          <div className="text-xs text-muted-foreground font-mono">{entry.actor_user_id.substring(0, 8)}...</div>
                        </TableCell>
                        <TableCell>
                          <span className="px-2 py-1 bg-muted rounded text-xs font-mono font-semibold">
                            {entry.action}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">{entry.target_type}</div>
                          <div className="text-xs text-muted-foreground font-mono">{entry.target_id.substring(0, 8)}...</div>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
                          {formatNairobiDate(entry.created_at)}
                        </TableCell>
                      </TableRow>
                      {expandedRow === entry.id && (
                        <TableRow className="bg-muted/30">
                          <TableCell colSpan={5} className="p-0 border-b">
                            <div className="p-4 bg-muted/30 inner-shadow">
                              <p className="text-xs font-semibold mb-2 text-muted-foreground uppercase tracking-wider">Metadata Payload</p>
                              <pre className="text-xs bg-slate-950 text-green-400 p-4 rounded-md overflow-x-auto whitespace-pre-wrap font-mono">
                                {JSON.stringify(entry.metadata, null, 2)}
                              </pre>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
