import { useState } from 'react';
import { Button } from '../../../../components/ui/button';
import { Input } from '../../../../components/ui/input';
import { Plus, Trash2, CheckCircle2, XCircle, Loader2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

interface ProfileItem {
  name: string;
  rateLimit: string;
}

interface ProfileSetupStepProps {
  onSuccess: () => void;
  isPending: boolean;
  onSetupProfiles: (profiles: { name: string; rate_limit: string }[]) => Promise<{ created: string[]; failed: string[] }>;
}

export function ProfileSetupStep({ onSuccess, isPending, onSetupProfiles }: ProfileSetupStepProps) {
  const [profiles, setProfiles] = useState<ProfileItem[]>([
    { name: '10Mbps', rateLimit: '10M/10M' },
    { name: '20Mbps', rateLimit: '20M/20M' },
    { name: '50Mbps', rateLimit: '50M/50M' },
  ]);

  const [validationErrors, setValidationErrors] = useState<Record<number, string>>({});
  const [results, setResults] = useState<{ created: string[]; failed: string[] } | null>(null);
  const [hasRun, setHasRun] = useState(false);

  const addProfile = () => {
    setProfiles([...profiles, { name: '', rateLimit: '' }]);
  };

  const removeProfile = (index: number) => {
    setProfiles(profiles.filter((_, idx) => idx !== index));
    const newErrors = { ...validationErrors };
    delete newErrors[index];
    setValidationErrors(newErrors);
  };

  const updateProfile = (index: number, field: keyof ProfileItem, value: string) => {
    const updated = [...profiles];
    updated[index][field] = value;
    setProfiles(updated);

    // Validate rate limit format /^\d+M\/\d+M$/ on type
    if (field === 'rateLimit') {
      const newErrors = { ...validationErrors };
      if (value && !/^\d+M\/\d+M$/.test(value)) {
        newErrors[index] = 'Format must be like 10M/10M (download/upload)';
      } else {
        delete newErrors[index];
      }
      setValidationErrors(newErrors);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Check errors
    const errors: Record<number, string> = {};
    profiles.forEach((p, idx) => {
      if (!p.name) {
        errors[idx] = 'Profile name is required';
      } else if (!p.rateLimit) {
        errors[idx] = 'Rate limit is required';
      } else if (!/^\d+M\/\d+M$/.test(p.rateLimit)) {
        errors[idx] = 'Format must be like 10M/10M';
      }
    });

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      toast.error('Please fix validation errors before submitting.');
      return;
    }

    try {
      const payload = profiles.map((p) => ({
        name: p.name,
        rate_limit: p.rateLimit,
      }));
      const response = await onSetupProfiles(payload);
      setResults(response);
      setHasRun(true);
      toast.success('Hotspot profiles configuration completed!');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to setup profiles.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-foreground">Configure Speed Tier Profiles</h3>
        <p className="text-sm text-muted-foreground">
          Define the packages that will be pushed to your MikroTik. These limit user speeds upon payment activation.
        </p>
      </div>

      {!hasRun ? (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-3">
            <div className="grid grid-cols-12 gap-2 text-xs font-semibold text-muted-foreground px-1">
              <div className="col-span-5">Profile Name</div>
              <div className="col-span-5">Rate Limit (Download/Upload)</div>
              <div className="col-span-2"></div>
            </div>

            <div className="space-y-3 max-h-[220px] overflow-y-auto pr-1">
              {profiles.map((profile, index) => (
                <div key={index} className="space-y-1">
                  <div className="grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-5">
                      <Input
                        placeholder="e.g. 10Mbps"
                        value={profile.name}
                        onChange={(e) => updateProfile(index, 'name', e.target.value)}
                        className={validationErrors[index] ? 'border-destructive text-xs h-9' : 'text-xs h-9'}
                      />
                    </div>
                    <div className="col-span-5">
                      <Input
                        placeholder="e.g. 10M/10M"
                        value={profile.rateLimit}
                        onChange={(e) => updateProfile(index, 'rateLimit', e.target.value)}
                        className={validationErrors[index] ? 'border-destructive text-xs h-9' : 'text-xs h-9'}
                      />
                    </div>
                    <div className="col-span-2 flex justify-end">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeProfile(index)}
                        disabled={profiles.length === 1}
                        className="text-destructive hover:bg-destructive/10 h-9 w-9"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  {validationErrors[index] && (
                    <p className="text-[10px] text-destructive pl-1">{validationErrors[index]}</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={addProfile} className="text-xs h-8">
              <Plus className="h-3.5 w-3.5 mr-1" /> Add Profile Row
            </Button>
          </div>

          <div className="pt-2">
            <Button type="submit" disabled={isPending} className="w-full flex items-center justify-center gap-2">
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Pushing Profiles...
                </>
              ) : (
                <>
                  Create Profiles on MikroTik <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-6">
          <div className="border rounded-lg bg-muted/20 p-4 space-y-3">
            <span className="text-xs font-semibold text-foreground uppercase tracking-wider block mb-1">
              Configuration Summary:
            </span>
            <div className="space-y-2">
              {profiles.map((profile, i) => {
                const isCreated = results?.created.includes(profile.name);
                const isFailed = results?.failed.some((f) => f.startsWith(profile.name));

                return (
                  <div key={i} className="flex items-center justify-between p-2 rounded bg-background border text-xs">
                    <div className="flex items-center space-x-2 font-medium">
                      <span className="font-mono">{profile.name}</span>
                      <span className="text-muted-foreground font-normal">({profile.rateLimit})</span>
                    </div>
                    {isCreated ? (
                      <span className="text-primary flex items-center gap-1 font-semibold">
                        <CheckCircle2 className="h-4 w-4 text-primary" /> Created
                      </span>
                    ) : isFailed ? (
                      <span className="text-destructive flex items-center gap-1 font-semibold">
                        <XCircle className="h-4 w-4 text-destructive" /> Failed / Exists
                      </span>
                    ) : (
                      <span className="text-zinc-500 font-semibold">Skipped</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="pt-2">
            <Button onClick={onSuccess} className="w-full flex items-center justify-center gap-2">
              Next Step <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
