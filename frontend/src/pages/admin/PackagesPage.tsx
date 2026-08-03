import { useMemo, useState } from 'react';
import { Pencil, Trash2, Plus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { usePackages, useCreatePackage, useUpdatePackage, useDeactivatePackage } from '../../hooks/usePackages';
import { Package } from '../../types/packages';
import type { ServiceType } from '../../types/onboarding';
import { PackageForm, PackageFormSubmitValues } from '../../components/admin/PackageForm';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatKES } from '../../lib/utils';
import { formatDuration } from '../../lib/formatDuration';
import { cn } from '../../lib/utils';
import { resolvePackageServiceType, savePackageServiceType } from '../../lib/packageServiceType';

import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../../components/ui/alert-dialog';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';

type ServiceFilter = 'all' | ServiceType;

function ServiceTypeBadge({ type }: { type: ServiceType }) {
  if (type === 'pppoe') {
    return (
      <Badge variant="outline" className="border-transparent bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200">
        Fiber
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="border-transparent bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200">
      Hotspot
    </Badge>
  );
}

export default function PackagesPage() {
  const { data: packages, isLoading } = usePackages();
  const createPackage = useCreatePackage();
  const updatePackage = useUpdatePackage();
  const deactivatePackage = useDeactivatePackage();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [editingPackage, setEditingPackage] = useState<Package | null>(null);
  const [deletingPackageId, setDeletingPackageId] = useState<string | null>(null);
  const [serviceFilter, setServiceFilter] = useState<ServiceFilter>('all');
  const [formServiceType, setFormServiceType] = useState<ServiceType>('hotspot');

  const filteredPackages = useMemo(() => {
    if (!packages) return [];
    if (serviceFilter === 'all') return packages;
    return packages.filter((pkg) => resolvePackageServiceType(pkg) === serviceFilter);
  }, [packages, serviceFilter]);

  const handleOpenDialog = (pkg?: Package) => {
    setEditingPackage(pkg ?? null);
    setFormServiceType(pkg ? resolvePackageServiceType(pkg) : 'hotspot');
    setIsDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setEditingPackage(null);
  };

  const onSubmit = async (data: PackageFormSubmitValues) => {
    try {
      if (editingPackage) {
        await updatePackage.mutateAsync({
          id: editingPackage.id,
          data: { ...data, description: data.description || '' },
        });
        savePackageServiceType(editingPackage.id, formServiceType);
        toast.success('Package updated successfully');
      } else {
        const created = await createPackage.mutateAsync({
          ...data,
          description: data.description || '',
        });
        savePackageServiceType(created.id, formServiceType);
        toast.success('Package created successfully');
      }
      handleCloseDialog();
    } catch {
      toast.error('Failed to save package');
    }
  };

  const handleDeactivate = async () => {
    if (deletingPackageId) {
      try {
        await deactivatePackage.mutateAsync(deletingPackageId);
        toast.success('Package deactivated');
      } catch {
        toast.error('Failed to deactivate package');
      } finally {
        setIsDeleteDialogOpen(false);
        setDeletingPackageId(null);
      }
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle title="Packages | Frixel Connect Admin" />

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Packages</h2>
          <p className="text-muted-foreground">Manage your WiFi plans and pricing.</p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" /> Add Package
        </Button>
      </div>

      <Tabs value={serviceFilter} onValueChange={(v) => setServiceFilter(v as ServiceFilter)}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="hotspot">Hotspot</TabsTrigger>
          <TabsTrigger value="pppoe">Fiber PPPoE</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="rounded-md border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Service</TableHead>
              <TableHead>Speed (Mbps)</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="py-8 text-center">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : filteredPackages.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                  No packages found. Create your first package to get started.
                </TableCell>
              </TableRow>
            ) : (
              filteredPackages.map((pkg) => {
                const pkgType = resolvePackageServiceType(pkg);
                return (
                  <TableRow key={pkg.id} className={cn(!pkg.is_active && 'text-muted-foreground opacity-60')}>
                    <TableCell className="font-medium">{pkg.name}</TableCell>
                    <TableCell>
                      <ServiceTypeBadge type={pkgType} />
                    </TableCell>
                    <TableCell>{pkg.speed_mbps} Mbps</TableCell>
                    <TableCell>{formatDuration(pkg.duration_minutes)}</TableCell>
                    <TableCell>{formatKES(pkg.price_kes)}</TableCell>
                    <TableCell>
                      {pkg.is_active ? (
                        <Badge variant="outline" className="border-transparent bg-green-100 text-green-800">
                          Active
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="border-transparent bg-gray-100 text-gray-800">
                          Inactive
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleOpenDialog(pkg)}
                          disabled={!pkg.is_active}
                        >
                          <Pencil className="h-4 w-4" />
                          <span className="sr-only">Edit</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:bg-destructive/10 hover:text-destructive/90"
                          onClick={() => {
                            setDeletingPackageId(pkg.id);
                            setIsDeleteDialogOpen(true);
                          }}
                          disabled={!pkg.is_active}
                        >
                          <Trash2 className="h-4 w-4" />
                          <span className="sr-only">Deactivate</span>
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>{editingPackage ? 'Edit Package' : 'Add Package'}</DialogTitle>
            <DialogDescription>
              {editingPackage ? 'Update package details below.' : 'Create a new WiFi package offering.'}
            </DialogDescription>
          </DialogHeader>
          <PackageForm
            key={editingPackage?.id ?? 'new'}
            allowServiceTypeSelect
            serviceType={formServiceType}
            onServiceTypeChange={setFormServiceType}
            showServiceBadge={false}
            defaultValues={
              editingPackage
                ? {
                    name: editingPackage.name,
                    description: editingPackage.description || '',
                    price_kes: editingPackage.price_kes,
                    speed_mbps: editingPackage.speed_mbps,
                    duration_minutes: editingPackage.duration_minutes,
                  }
                : undefined
            }
            isPending={createPackage.isPending || updatePackage.isPending}
            onCancel={handleCloseDialog}
            onSubmit={onSubmit}
          />
        </DialogContent>
      </Dialog>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate this package?</AlertDialogTitle>
            <AlertDialogDescription>
              Existing vouchers will not be affected. This action will hide the package from the
              customer portal so no new purchases can be made.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeactivate}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
