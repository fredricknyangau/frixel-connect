import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

interface TestPaymentGuideDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Inline Daraja sandbox guide-avoids a separate /docs route for first-run tenants. */
export function TestPaymentGuideDialog({ open, onOpenChange }: TestPaymentGuideDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Test an M-Pesa payment</DialogTitle>
          <DialogDescription>
            Use Safaricom&apos;s Daraja sandbox to confirm payments flow into your dashboard.
          </DialogDescription>
        </DialogHeader>
        <ol className="list-decimal space-y-3 pl-5 text-sm text-muted-foreground">
          <li>
            In <strong className="text-foreground">Account &amp; Billing</strong>, confirm your tenant
            is on sandbox mode (default for new trials).
          </li>
          <li>
            Open your customer hotspot portal or use the admin STK test endpoint with a sandbox phone
            number (e.g. 254708374149).
          </li>
          <li>
            Complete the STK prompt on the test handset-amount should match one of your packages.
          </li>
          <li>
            Return to <strong className="text-foreground">Payments</strong>; the record should appear
            within a few seconds once Daraja confirms.
          </li>
        </ol>
        <p className="text-xs text-muted-foreground">
          Need production go-live? Configure live Daraja credentials under Account &amp; Billing once
          you are ready for real customer payments.
        </p>
      </DialogContent>
    </Dialog>
  );
}
