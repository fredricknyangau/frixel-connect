import { useMyInvoices } from '../../hooks/useInvoices';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatKES, formatNairobiDate } from '../../lib/utils';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../../components/ui/card';
import { Loader2, Receipt, Download } from 'lucide-react';

export default function CustomerInvoicesPage() {
  const { data: invoices, isLoading } = useMyInvoices();

  return (
    <div className="space-y-6">
      <PageTitle title="My Invoices | ZealSync" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Billing History</h2>
          <p className="text-muted-foreground">Download your KRA eTIMS compliant receipts.</p>
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-40 w-full bg-muted animate-pulse rounded-xl" />
          ))}
        </div>
      ) : !invoices || invoices.length === 0 ? (
        <Card className="flex flex-col items-center justify-center p-12 text-center">
          <Receipt className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <CardTitle className="text-xl mb-2">No Invoices Found</CardTitle>
          <CardDescription>
            You haven't made any payments yet. Invoices will appear here once you purchase a package.
          </CardDescription>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {invoices.map((invoice) => (
            <Card key={invoice.id} className="flex flex-col h-full">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-lg font-mono">{invoice.invoice_number}</CardTitle>
                    <CardDescription>{formatNairobiDate(invoice.created_at)}</CardDescription>
                  </div>
                  <Receipt className="h-5 w-5 text-muted-foreground" />
                </div>
              </CardHeader>
              <CardContent className="flex-1">
                <div className="flex justify-between items-end">
                  <span className="text-sm text-muted-foreground">Amount Paid</span>
                  <span className="text-2xl font-bold text-primary">{formatKES(invoice.amount_kes)}</span>
                </div>
              </CardContent>
              <CardFooter className="pt-3 border-t">
                <Button variant="outline" className="w-full" asChild>
                  <a href={invoice.pdf_url} target="_blank" rel="noopener noreferrer" download>
                    <Download className="mr-2 h-4 w-4" /> Download Receipt
                  </a>
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
