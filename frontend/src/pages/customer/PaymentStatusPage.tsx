import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2, CheckCircle2, XCircle, ArrowLeft, Ticket } from 'lucide-react';

import { usePaymentStatus } from '../../hooks/usePayments';
import { PageTitle } from '../../components/shared/PageTitle';
import { StkPendingState } from '../../components/shared/StkPendingState';

import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';

export default function PaymentStatusPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: statusInfo, isLoading, isError } = usePaymentStatus(id || '');

  // If the user navigates directly without an ID, send them back
  useEffect(() => {
    if (!id) {
      navigate('/customer/dashboard', { replace: true });
    }
  }, [id, navigate]);

  if (!id) return null;

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <PageTitle title="Payment Status | ZealSync" />

      <Card className="w-full max-w-md shadow-lg border-primary/20">
        <CardHeader className="text-center pb-2">
          <CardTitle className="text-2xl">Payment Status</CardTitle>
          <CardDescription>
            {statusInfo?.status === 'pending' && "Waiting for M-Pesa confirmation..."}
            {statusInfo?.status === 'confirmed' && "Payment successful!"}
            {statusInfo?.status === 'failed' && "Payment failed or cancelled."}
            {!statusInfo && "Loading status..."}
          </CardDescription>
        </CardHeader>
        
        <CardContent className="flex flex-col items-center justify-center py-8 space-y-6">
          {isLoading ? (
            <StkPendingState />
          ) : isError ? (
            <div className="flex flex-col items-center space-y-4">
              <XCircle className="h-16 w-16 text-destructive" />
              <p className="text-center font-medium">Failed to fetch payment status.</p>
            </div>
          ) : statusInfo?.status === 'pending' ? (
            <StkPendingState />
          ) : statusInfo?.status === 'confirmed' ? (
            <div className="flex flex-col items-center space-y-6 w-full">
              <CheckCircle2 className="h-20 w-20 text-green-500" />
              
              <div className="w-full p-6 bg-gradient-to-br from-green-50 to-green-100 border border-green-200 rounded-xl flex flex-col items-center space-y-3">
                <p className="text-sm font-semibold text-green-800 uppercase tracking-wider">Your WiFi Voucher Code</p>
                <div className="flex items-center gap-2 bg-white px-4 py-3 rounded-lg shadow-sm border border-green-200 w-full justify-center">
                  <Ticket className="h-5 w-5 text-green-600" />
                  <span className="text-3xl font-mono font-bold tracking-widest text-gray-900">
                    {statusInfo.voucher_code || 'N/A'}
                  </span>
                </div>
                <p className="text-xs text-green-700 text-center">
                  Connect to our WiFi network and enter this code to start browsing.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-4">
              <XCircle className="h-20 w-20 text-destructive" />
              <div className="p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20 text-center w-full">
                <p className="font-semibold">Payment Failed</p>
                <p className="text-sm mt-1">The transaction was cancelled or failed to process.</p>
              </div>
            </div>
          )}
        </CardContent>
        
        <CardFooter className="flex justify-center border-t bg-muted/30 p-4">
          <Button 
            variant={statusInfo?.status === 'confirmed' ? "default" : "outline"}
            className="w-full"
            onClick={() => navigate('/customer/dashboard')}
          >
            {statusInfo?.status === 'confirmed' ? "Go to Dashboard" : (
              <>
                <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
              </>
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}