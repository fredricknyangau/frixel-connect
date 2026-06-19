import { useState } from 'react';
import { Plus, Loader2, Pencil, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

import { useRouters, useCreateRouter, useUpdateRouter, useDeleteRouter } from '../../hooks/useRouters';
import { MikrotikRouter } from '../../types/routers';
import { PageTitle } from '../../components/shared/PageTitle';
import { RouterStatusBadge } from '../../components/shared/RouterStatusBadge';
import { formatNairobiDate } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../../components/ui/alert-dialog';
import { RouterForm, RouterFormValues } from '../../components/shared/RouterForm';

export default function RoutersPage() {
  const navigate = useNavigate();
  const { data: routers, isLoading } = useRouters();
  const createRouter = useCreateRouter();
  const updateRouter = useUpdateRouter();
  const deleteRouter = useDeleteRouter();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [editingRouter, setEditingRouter] = useState<MikrotikRouter | null>(null);
  const [deletingRouterId, setDeletingRouterId] = useState<string | null>(null);

  const handleOpenEditDialog = (router: MikrotikRouter) => {
    setEditingRouter(router);
    setIsDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setEditingRouter(null);
  };

  const onSubmit = async (data: RouterFormValues) => {
    try {
      if (editingRouter) {
        await updateRouter.mutateAsync({
          id: editingRouter.id,
          data: {
            name: data.name,
            host: data.host,
            port: data.port,
            username: data.username,
            password: data.password || undefined,
            site_name: data.site_name,
          },
        });
        toast.success('Router configuration updated');
      } else {
        await createRouter.mutateAsync({
          name: data.name,
          host: data.host,
          port: data.port,
          username: data.username,
          password: data.password || '',
          site_name: data.site_name,
        });
        toast.success('Router connected successfully');
      }
      handleCloseDialog();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save router details.');
    }
  };

  const handleDelete = async () => {
    if (deletingRouterId) {
      try {
        await deleteRouter.mutateAsync(deletingRouterId);
        toast.success('Router profile removed');
      } catch (err: any) {
        toast.error(err.response?.data?.detail || 'Failed to remove router.');
      } finally {
        setIsDeleteDialogOpen(false);
        setDeletingRouterId(null);
      }
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle title="MikroTik Routers | ZealSync Admin" />

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">MikroTik Routers</h2>
          <p className="text-muted-foreground">Manage your router site configurations and credentials.</p>
        </div>
        <Button onClick={() => navigate('/admin/onboarding/router')}>
          <Plus className="mr-2 h-4 w-4" /> Connect Router
        </Button>
      </div>

      <div className="rounded-md border bg-background overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Host/IP</TableHead>
              <TableHead>Site/Location</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last Heartbeat</TableHead>
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
            ) : !routers?.length ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No routers connected yet. Add your first MikroTik router to begin.
                </TableCell>
              </TableRow>
            ) : (
              routers.map((router) => (
                <TableRow key={router.id}>
                  <TableCell className="font-medium">{router.name}</TableCell>
                  <TableCell>{router.host}:{router.port}</TableCell>
                  <TableCell>{router.site_name}</TableCell>
                  <TableCell>
                    <RouterStatusBadge status={router.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {router.last_heartbeat_at ? formatNairobiDate(router.last_heartbeat_at) : 'Never'}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      {router.status === 'pending_setup' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/admin/onboarding/router?router_id=${router.id}`)}
                          className="text-xs h-7"
                        >
                          Resume Setup
                        </Button>
                      ) : (
                        <Button variant="ghost" size="icon" onClick={() => handleOpenEditDialog(router)}>
                          <Pencil className="h-4 w-4" />
                          <span className="sr-only">Edit</span>
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive hover:text-destructive/90 hover:bg-destructive/10"
                        onClick={() => {
                          setDeletingRouterId(router.id);
                          setIsDeleteDialogOpen(true);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                        <span className="sr-only">Delete</span>
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
            <DialogTitle>{editingRouter ? 'Edit Router API' : 'Connect MikroTik Router'}</DialogTitle>
            <DialogDescription>
              {editingRouter
                ? 'Update connection parameters. Leave password empty unless rotating.'
                : 'Define credentials for your local MikroTik router.'}
            </DialogDescription>
          </DialogHeader>
          <RouterForm
            onSubmit={onSubmit}
            defaultValues={
              editingRouter
                ? {
                    name: editingRouter.name,
                    host: editingRouter.host ?? '',
                    port: editingRouter.port ?? 80,
                    username: editingRouter.username ?? 'admin',
                    site_name: editingRouter.site_name,
                  }
                : undefined
            }
            isEdit={!!editingRouter}
            isPending={createRouter.isPending || updateRouter.isPending}
            onCancel={handleCloseDialog}
            submitLabel={editingRouter ? 'Update Router' : 'Add Router'}
          />
        </DialogContent>
      </Dialog>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Disconnect this router?</AlertDialogTitle>
            <AlertDialogDescription>
              Deleting this router will remove the VPN connection and disconnect all customers currently using it. Active sessions will be terminated. Are you sure?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Disconnect Router
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
