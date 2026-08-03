import { useState } from 'react';
import { Wallet, Copy, Check, Ticket, RefreshCw, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useWalletBalance, useWalletTransactions } from '../../hooks/useWallet';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatKES, formatNairobiDate } from '../../lib/utils';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Badge } from '../../components/ui/badge';
import GenerateVoucherDialog from './GenerateVoucherDialog';

export default function WalletPage() {
  const { data: wallet, isLoading: balanceLoading, refetch: refetchBalance } = useWalletBalance();
  const { data: transactions, isLoading: txnsLoading, refetch: refetchTransactions } = useWalletTransactions();

  const [copiedField, setCopiedField] = useState<'paybill' | 'reference' | null>(null);
  const [isVoucherDialogOpen, setIsVoucherDialogOpen] = useState(false);

  const handleCopy = (text: string, field: 'paybill' | 'reference') => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    toast.success(`${field === 'paybill' ? 'Paybill' : 'Reference'} code copied`);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleRefresh = async () => {
    await Promise.all([refetchBalance(), refetchTransactions()]);
    toast.success('Wallet data refreshed');
  };

  const walletBalance = wallet?.balance_kes || 0;
  const paybillNumber = wallet?.paybill_number || '222111'; // Fallback
  const walletReference = wallet?.wallet_reference || 'WS00000'; // Fallback

  const isLoading = balanceLoading || txnsLoading;

  return (
    <div className="space-y-6">
      <PageTitle title="Wallet Ledger | Frixel Connect Reseller" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Reseller Wallet</h2>
          <p className="text-muted-foreground">Manage your prepayed balance and generate customer hotspot vouchers.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={handleRefresh} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
          <Button onClick={() => setIsVoucherDialogOpen(true)} disabled={isLoading}>
            <Ticket className="mr-2 h-4 w-4" /> Generate Voucher
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* Wallet Balance Card */}
        <Card className="md:col-span-1 border-t-4 border-t-primary flex flex-col justify-between">
          <CardHeader>
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-sm font-medium">Available Balance</span>
              <Wallet className="h-5 w-5 text-primary" />
            </div>
            {isLoading ? (
              <div className="h-9 w-28 bg-muted animate-pulse rounded mt-1" />
            ) : (
              <CardTitle className="text-3xl font-bold pt-1">{formatKES(walletBalance)}</CardTitle>
            )}
            <CardDescription className="text-xs pt-1">
              Funds are debited instantly when generating vouchers.
            </CardDescription>
          </CardHeader>
        </Card>

        {/* M-Pesa C2B Paybill Onboarding Card */}
        <Card className="md:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">How to Top Up Your Wallet</CardTitle>
            <CardDescription>
              Frixel Connect supports automated wallet topups via Safaricom M-Pesa C2B.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 text-sm">
            <div className="space-y-3">
              <div className="flex flex-col space-y-1">
                <span className="text-xs text-muted-foreground font-semibold">1. M-PESA PAYBILL</span>
                <div className="flex items-center gap-2">
                  <code className="text-base font-bold bg-muted px-2 py-1 rounded select-all">
                    {paybillNumber}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                    onClick={() => handleCopy(paybillNumber, 'paybill')}
                  >
                    {copiedField === 'paybill' ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              <div className="flex flex-col space-y-1">
                <span className="text-xs text-muted-foreground font-semibold">2. ACCOUNT NUMBER (YOUR REFERENCE)</span>
                <div className="flex items-center gap-2">
                  <code className="text-base font-bold bg-muted px-2 py-1 rounded select-all text-primary">
                    {walletReference}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                    onClick={() => handleCopy(walletReference, 'reference')}
                  >
                    {copiedField === 'reference' ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex flex-col justify-center rounded-md bg-muted/30 p-4 border border-dashed text-xs text-muted-foreground space-y-2">
              <p className="font-semibold text-foreground">Top-up Instructions:</p>
              <ol className="list-decimal pl-4 space-y-1">
                <li>Go to Lipa na M-Pesa on your Safaricom phone.</li>
                <li>Enter the Paybill number shown above.</li>
                <li>Enter the Account Number exactly as displayed.</li>
                <li>Your balance will update automatically in about a minute.</li>
              </ol>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Transaction History Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Ledger & Transaction History</CardTitle>
          <CardDescription>
            Audit log of all funds loaded and debits made for voucher generation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border overflow-x-auto bg-background">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Balance After</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {txnsLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">
                      <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : !transactions || transactions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      No wallet transactions recorded. Perform your first Paybill payment to load funds.
                    </TableCell>
                  </TableRow>
                ) : (
                  transactions.map((txn: any) => (
                    <TableRow key={txn.id}>
                      <TableCell>
                        {txn.type === 'topup' ? (
                          <Badge variant="outline" className="border-transparent bg-green-100 text-green-800 hover:bg-green-100">Top Up</Badge>
                        ) : txn.type === 'debit' ? (
                          <Badge variant="outline" className="border-transparent bg-red-100 text-red-800 hover:bg-red-100">Debit</Badge>
                        ) : (
                          <Badge variant="outline" className="border-transparent bg-gray-100 text-gray-800 hover:bg-gray-100">Adjustment</Badge>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-xs">{txn.reference}</TableCell>
                      <TableCell className={txn.type === 'topup' ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>
                        {txn.type === 'topup' ? '+' : '-'} {formatKES(txn.amount_kes)}
                      </TableCell>
                      <TableCell className="font-medium">{formatKES(txn.balance_after)}</TableCell>
                      <TableCell className="text-muted-foreground whitespace-nowrap">
                        {formatNairobiDate(txn.created_at)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <GenerateVoucherDialog
        open={isVoucherDialogOpen}
        onOpenChange={setIsVoucherDialogOpen}
      />
    </div>
  );
}
