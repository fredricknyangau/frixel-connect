import { Loader2 } from 'lucide-react';

interface StkPendingStateProps {
  title?: string;
  description?: string;
}

export function StkPendingState({ 
  title = "Waiting for M-Pesa...", 
  description = "Please check your phone and enter your M-Pesa PIN. We're waiting for the confirmation. This page will update automatically." 
}: StkPendingStateProps) {
  return (
    <div className="flex flex-col items-center space-y-4">
      <div className="relative">
        <div className="absolute inset-0 bg-primary/20 rounded-full animate-ping"></div>
        <div className="relative p-4 bg-primary/10 rounded-full">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
        </div>
      </div>
      <div className="text-center">
        <p className="font-semibold text-foreground mb-1">{title}</p>
        <p className="text-sm text-muted-foreground max-w-[280px] mx-auto">
          {description}
        </p>
      </div>
    </div>
  );
}
