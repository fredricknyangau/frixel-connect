import { Link } from 'react-router-dom';
import { CheckCircle2, Circle, ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { cn } from '../../lib/utils';

export interface ChecklistItem {
  id: string;
  title: string;
  description: string;
  done: boolean;
  ctaLabel: string;
  ctaHref?: string;
  onCtaClick?: () => void;
}

interface SetupChecklistProps {
  items: ChecklistItem[];
}

/** First-run setup grid — each row shows completion state and a deep-link CTA. */
export function SetupChecklist({ items }: SetupChecklistProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {items.map((item) => (
        <Card key={item.id} className={cn(item.done && 'border-primary/20 bg-primary/5')}>
          <CardContent className="flex h-full flex-col gap-3 p-4 pt-4">
            <div className="flex items-start gap-3">
              {item.done ? (
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden />
              ) : (
                <Circle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
              )}
              <div className="space-y-1">
                <p className="font-medium leading-tight">{item.title}</p>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            </div>
            {!item.done && (
              item.onCtaClick ? (
                <Button variant="outline" size="sm" className="mt-auto w-fit" onClick={item.onCtaClick}>
                  {item.ctaLabel}
                </Button>
              ) : (
                <Link
                  to={item.ctaHref ?? '#'}
                  className="mt-auto inline-flex h-7 w-fit items-center gap-1 rounded-lg border border-border bg-background px-2.5 text-sm hover:bg-muted"
                >
                  {item.ctaLabel}
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              )
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
