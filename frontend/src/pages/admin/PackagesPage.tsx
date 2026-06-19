import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Pencil, Trash2, Plus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { usePackages, useCreatePackage, useUpdatePackage, useDeactivatePackage } from '../../hooks/usePackages';
import { Package } from '../../types/packages';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatKES } from '../../lib/utils';
import { formatDuration } from '../../lib/formatDuration';
import { cn } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../../components/ui/alert-dialog';

const packageSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
  description: z.string().optional(),
  price_kes: z.coerce.number().positive('Price must be greater than 0'),
  duration_minutes: z.coerce.number().int().positive('Duration must be a positive number'),
  speed_mbps: z.coerce.number().int().positive('Speed must be a positive number'),
});

type PackageFormValues = z.infer<typeof packageSchema>;

export default function PackagesPage() {
  const { data: packages, isLoading } = usePackages();
  const createPackage = useCreatePackage();
  const updatePackage = useUpdatePackage();
  const deactivatePackage = useDeactivatePackage();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [editingPackage, setEditingPackage] = useState<Package | null>(null);
  const [deletingPackageId, setDeletingPackageId] = useState<string | null>(null);

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<PackageFormValues>({
    resolver: zodResolver(packageSchema) as any,
  });

  // Reset form when editingPackage changes
  useEffect(() => {
    if (editingPackage) {
      reset({
        name: editingPackage.name,
        description: editingPackage.description || '',
        price_kes: editingPackage.price_kes,
        duration_minutes: editingPackage.duration_minutes,
        speed_mbps: editingPackage.speed_mbps,
      });
    } else {
      reset({ name: '', description: '', price_kes: 0, duration_minutes: 0, speed_mbps: 0 });
    }
  }, [editingPackage, reset]);

  const handleOpenDialog = (pkg?: Package) => {
    setEditingPackage(pkg || null);
    setIsDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setEditingPackage(null);
  };

  const onSubmit = async (data: PackageFormValues) => {
    try {
      if (editingPackage) {
        await updatePackage.mutateAsync({ id: editingPackage.id, data: { ...data, description: data.description || '' } });
        toast.success('Package updated successfully');
      } else {
        await createPackage.mutateAsync({ ...data, description: data.description || '' });
        toast.success('Package created successfully');
      }
      handleCloseDialog();
    } catch (error) {
      toast.error('Failed to save package');
    }
  };

  const handleDeactivate = async () => {
    if (deletingPackageId) {
      try {
        await deactivatePackage.mutateAsync(deletingPackageId);
        toast.success('Package deactivated');
      } catch (error) {
        toast.error('Failed to deactivate package');
      } finally {
        setIsDeleteDialogOpen(false);
        setDeletingPackageId(null);
      }
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle title="Packages | ZealSync Admin" />

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Packages</h2>
          <p className="text-muted-foreground">Manage your WiFi plans and pricing.</p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" /> Add Package
        </Button>
      </div>

      <div className="rounded-md border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
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
                <TableCell colSpan={6} className="text-center py-8">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : !packages?.length ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No packages found. Create your first package to get started.
                </TableCell>
              </TableRow>
            ) : (
              packages.map((pkg) => (
                <TableRow key={pkg.id} className={cn(!pkg.is_active && 'text-muted-foreground opacity-60')}>
                  <TableCell className="font-medium">{pkg.name}</TableCell>
                  <TableCell>{pkg.speed_mbps} Mbps</TableCell>
                  <TableCell>{formatDuration(pkg.duration_minutes)}</TableCell>
                  <TableCell>{formatKES(pkg.price_kes)}</TableCell>
                  <TableCell>
                    {pkg.is_active ? (
                      <Badge variant="outline" className="border-transparent bg-green-100 text-green-800">Active</Badge>
                    ) : (
                      <Badge variant="outline" className="bg-gray-100 text-gray-800 border-transparent">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(pkg)} disabled={!pkg.is_active}>
                        <Pencil className="h-4 w-4" />
                        <span className="sr-only">Edit</span>
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="text-destructive hover:text-destructive/90 hover:bg-destructive/10"
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
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{editingPackage ? 'Edit Package' : 'Add Package'}</DialogTitle>
            <DialogDescription>
              {editingPackage ? 'Update package details below.' : 'Create a new WiFi package offering.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit as any)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Package Name</Label>
              <Input id="name" placeholder="e.g. Bronze Plan" {...register('name')} />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="speed_mbps">Speed (Mbps)</Label>
                <Input id="speed_mbps" type="number" {...register('speed_mbps')} />
                {errors.speed_mbps && <p className="text-sm text-destructive">{errors.speed_mbps.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="duration_minutes">Duration (Minutes)</Label>
                <Input id="duration_minutes" type="number" {...register('duration_minutes')} />
                {errors.duration_minutes && <p className="text-sm text-destructive">{errors.duration_minutes.message}</p>}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="price_kes">Price (KES)</Label>
              <Input id="price_kes" type="number" {...register('price_kes')} />
              {errors.price_kes && <p className="text-sm text-destructive">{errors.price_kes.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description (Optional)</Label>
              <Input id="description" placeholder="Short description" {...register('description')} />
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleCloseDialog}>Cancel</Button>
              <Button type="submit" disabled={isSubmitting || createPackage.isPending || updatePackage.isPending}>
                {isSubmitting || createPackage.isPending || updatePackage.isPending ? 'Saving...' : 'Save Package'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate this package?</AlertDialogTitle>
            <AlertDialogDescription>
              Existing vouchers will not be affected. This action will hide the package from the customer portal so no new purchases can be made.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeactivate} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}