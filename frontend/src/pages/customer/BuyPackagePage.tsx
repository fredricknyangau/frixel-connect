import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Zap, Clock, Smartphone } from 'lucide-react';
import { toast } from 'sonner';

import { usePackages } from '../../hooks/usePackages';
import { useInitiateSTKPush } from '../../hooks/usePayments';

import { PageTitle } from '../../components/shared/PageTitle';
import { formatKES } from '../../lib/utils';


import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';

export default function BuyPackagePage() {
  const navigate = useNavigate();

  const { data: packages, isLoading } = usePackages();
  const initiatePayment = useInitiateSTKPush();

  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const activePackages = packages?.filter(p => p.is_active) || [];

  const handleBuyClick = (packageId: string) => {
    setSelectedPackageId(packageId);
    setIsDialogOpen(true);
  };

  const handleConfirmPayment = async () => {
    if (!selectedPackageId) return;

    try {
      const payment = await initiatePayment.mutateAsync({
        package_id: selectedPackageId,
        phone: phoneNumber,
      });

      setIsDialogOpen(false);
      // Redirect to status page
      navigate(`/customer/status/${payment.id}`);
      
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to initiate payment. Please try again.');
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle title="Buy Package | ZealSync" />

      <div>
        <h2 className="text-2xl font-bold tracking-tight">Choose Your Plan</h2>
        <p className="text-muted-foreground">Select an internet package that fits your needs.</p>
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : activePackages.length === 0 ? (
        <div className="text-center py-12 bg-muted/30 rounded-lg border border-dashed">
          <p className="text-muted-foreground">No internet packages are currently available.</p>
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {activePackages.map(pkg => (
            <Card key={pkg.id} className="flex flex-col relative overflow-hidden transition-all hover:shadow-md border-primary/20">
              <div className="absolute top-0 right-0 bg-primary text-primary-foreground px-3 py-1 rounded-bl-lg text-xs font-bold shadow-sm">
                {pkg.speed_mbps} Mbps
              </div>
              <CardHeader>
                <CardTitle>{pkg.name}</CardTitle>
                <div className="mt-2 flex items-baseline text-3xl font-extrabold text-primary">
                  {formatKES(pkg.price_kes)}
                </div>
                <CardDescription className="pt-2 min-h-[3rem]">
                  {pkg.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1 space-y-4">
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span>Duration: <span className="font-semibold">{pkg.duration_days} Days</span></span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Zap className="h-4 w-4 text-muted-foreground" />
                  <span>Speed: <span className="font-semibold">{pkg.speed_mbps} Mbps</span></span>
                </div>
              </CardContent>
              <CardFooter>
                <Button 
                  className="w-full font-semibold" 
                  onClick={() => handleBuyClick(pkg.id)}
                >
                  Buy via M-Pesa
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Confirm Payment</DialogTitle>
            <DialogDescription>
              Enter your M-Pesa phone number to receive the payment prompt.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="phone">M-Pesa Phone Number</Label>
              <div className="relative">
                <Smartphone className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="phone"
                  className="pl-9"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="0712 345 678"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Format: 07XX XXX XXX or 2547XX XXX XXX
              </p>
            </div>
            
            <div className="bg-muted p-3 rounded-md text-sm">
              <p className="font-medium text-primary mb-1">What happens next?</p>
              <ol className="list-decimal list-inside space-y-1 text-muted-foreground text-xs">
                <li>You will receive an M-Pesa prompt on your phone.</li>
                <li>Enter your M-Pesa PIN to confirm the payment.</li>
                <li>Wait for the confirmation page to give you your voucher code.</li>
              </ol>
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
            <Button 
              onClick={handleConfirmPayment} 
              disabled={!phoneNumber || initiatePayment.isPending}
            >
              {initiatePayment.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Sending Prompt...
                </>
              ) : (
                'Send M-Pesa Prompt'
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}