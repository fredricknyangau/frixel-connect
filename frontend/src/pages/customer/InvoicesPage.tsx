import { useMyInvoices } from '../../hooks/useInvoices';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatKES, formatNairobiDate } from '../../lib/utils';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../../components/ui/card';
import { Receipt, Download, ExternalLink } from 'lucide-react';
import { api } from '../../lib/api';
import { toast } from 'sonner';

const parseQrData = (qrData: string | null) => {
  if (!qrData) return { qrUrl: '', kraSign: '' };
  if (qrData.includes('|')) {
    const parts = qrData.split('|');
    return { kraSign: parts[0], qrUrl: parts[1] };
  }
  return { qrUrl: qrData, kraSign: '' };
};

const handleDownload = async (pdfUrl: string | null, invoiceNumber: string | number) => {
  if (!pdfUrl) return;
  try {
    const response = await api.get(pdfUrl, {
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `invoice_${invoiceNumber}.pdf`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    toast.error("Failed to download invoice PDF.");
  }
};

export default function CustomerInvoicesPage() {
  const { data: invoices, isLoading } = useMyInvoices();

  return (
    <div className="space-y-6">
      <PageTitle title="My Invoices | Frixel Connect" />

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
          {invoices.map((invoice) => {
            const { qrUrl, kraSign } = parseQrData(invoice.kra_etims_qr_code);
            return (
              <Card key={invoice.id} className="flex flex-col h-full">
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <CardTitle className="text-lg font-mono">INV-{invoice.invoice_number}</CardTitle>
                      <CardDescription>{formatNairobiDate(invoice.created_at)}</CardDescription>
                    </div>
                    <Receipt className="h-5 w-5 text-muted-foreground" />
                  </div>
                </CardHeader>
                <CardContent className="flex-1 space-y-4">
                  <div className="flex justify-between items-end pb-3 border-b">
                    <span className="text-sm text-muted-foreground">Amount Paid</span>
                    <span className="text-2xl font-bold text-primary">{formatKES(invoice.amount_kes)}</span>
                  </div>

                  {/* KRA eTIMS QR section inside card */}
                  {qrUrl && (
                    <div className="flex items-center justify-between gap-3 bg-muted/30 p-2.5 rounded-lg border border-dashed">
                      <div className="space-y-1 text-left min-w-0">
                        <span className="text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400 block tracking-wide">
                          eTIMS Compliant
                        </span>
                        {kraSign && (
                          <p className="text-[9px] font-mono text-muted-foreground truncate" title={kraSign}>
                            Sign: {kraSign}
                          </p>
                        )}
                        <a 
                          href={qrUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-primary hover:underline font-semibold flex items-center gap-1"
                        >
                          Verify Receipt <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      </div>
                      <div className="bg-white p-1 rounded border shrink-0">
                        <img 
                          src={`https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=${encodeURIComponent(qrUrl)}`}
                          alt="KRA eTIMS QR"
                          className="w-14 h-14"
                          loading="lazy"
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
                <CardFooter className="pt-3 border-t">
                  <Button 
                    variant="outline" 
                    className="w-full h-9 text-xs font-semibold"
                    disabled={!invoice.pdf_url}
                    onClick={() => handleDownload(invoice.pdf_url, invoice.invoice_number)}
                  >
                    <Download className="mr-2 h-4 w-4" /> Download Receipt
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
