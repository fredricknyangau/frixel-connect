import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthContext } from '../../context/AuthContext';
import { api } from '../../lib/api';
import { PageTitle } from '../../components/shared/PageTitle';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../../components/ui/card';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '../../components/ui/alert-dialog';
import { ShieldAlert, Download, Trash2, Loader2, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

export default function DataPrivacyPage() {
  const { logout } = useAuthContext();
  const navigate = useNavigate();
  const [isExporting, setIsExporting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleExportData = async () => {
    try {
      setIsExporting(true);
      const response = await api.get('/customers/me/export');
      
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `zealsync_my_data_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      toast.success('Your data has been downloaded successfully.');
    } catch (err) {
      toast.error('Failed to export data. Please try again later.');
    } finally {
      setIsExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    try {
      setIsDeleting(true);
      await api.delete('/customers/me');
      toast.success('Your account has been deleted.');
      logout();
      navigate('/');
    } catch (err) {
      toast.error('Failed to delete account. Please try again later.');
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle title="Data & Privacy | ZealSync" />

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => navigate('/customer/profile')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Data & Privacy</h2>
          <p className="text-muted-foreground">Manage your personal data and account status.</p>
        </div>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-primary">
              <Download className="h-5 w-5" />
              <CardTitle className="text-xl">Download My Data</CardTitle>
            </div>
            <CardDescription>
              Request a copy of your personal data, including your profile information, active vouchers, and session history in a machine-readable JSON format.
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button onClick={handleExportData} disabled={isExporting}>
              {isExporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
              {isExporting ? 'Exporting...' : 'Download JSON Data'}
            </Button>
          </CardFooter>
        </Card>

        <Card className="border-t-destructive">
          <CardHeader>
            <div className="flex items-center gap-2 text-destructive">
              <ShieldAlert className="h-5 w-5" />
              <CardTitle className="text-xl">Delete My Account</CardTitle>
            </div>
            <CardDescription>
              Permanently close your account and anonymize your personal details.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Please note: Deleting your account will anonymize your name, email, and phone number in our database. However, your payment and voucher history will be retained as they are financial records required by law for accounting purposes. You will immediately lose access to the portal and any active subscriptions or vouchers.
            </p>
          </CardContent>
          <CardFooter>
            <AlertDialog>
              <AlertDialogTrigger render={<Button variant="destructive" />}>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete Account
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This action cannot be undone. It will immediately log you out and anonymize your personal profile data. Your payment history will remain intact for legal financial reporting, but it will no longer be associated with your identifiable details.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction 
                    onClick={handleDeleteAccount}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    disabled={isDeleting}
                  >
                    {isDeleting ? 'Deleting...' : 'Yes, delete my account'}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
