import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { catalogApi } from '@/api/catalog';
import { storesApi } from '@/api/stores';
import { useAuth } from '@/lib/store';
import { DashboardLayout } from '@/components/layouts/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { formatPrice, slugify } from '@/lib/utils';
import { Plus, Pencil, Trash2, Package, ToggleLeft, ToggleRight } from 'lucide-react';
import type { Product } from '@/types';

export const Route = createFileRoute('/dashboard/products/')({
  component: DashboardProductsPage,
});

const productSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  slug: z.string().min(2, 'Slug required').regex(/^[a-z0-9-]+$/, 'Lowercase letters, numbers, hyphens only'),
  price: z.string().regex(/^\d+(\.\d{1,2})?$/, 'Invalid price'),
  compareAtPrice: z.string().regex(/^\d+(\.\d{1,2})?$/, 'Invalid price').optional().or(z.literal('')),
  description: z.string().optional(),
  imageUrl: z.string().url('Must be a valid URL').optional().or(z.literal('')),
  categoryId: z.string().optional(),
});
type ProductFormData = z.infer<typeof productSchema>;

function DashboardProductsPage() {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  useEffect(() => {
    if (!isAuthenticated) navigate({ to: '/auth/login' });
  }, [isAuthenticated, navigate]);

  // Find user's store
  const { data: storesData } = useQuery({
    queryKey: ['stores', 'mine'],
    queryFn: () => storesApi.list({ limit: 1 }),
    enabled: isAuthenticated,
  });
  const myStore = storesData?.items?.find((s) => s.ownerId === user?.id) ?? null;

  // Products for store
  const { data: productsData, isLoading } = useQuery({
    queryKey: ['products', { store: myStore?.id }],
    queryFn: () => catalogApi.listProducts({ store: myStore!.id, limit: 50 }),
    enabled: !!myStore,
  });
  const products = productsData?.items ?? [];

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<ProductFormData>({ resolver: zodResolver(productSchema) });

  const createMutation = useMutation({
    mutationFn: (data: ProductFormData) =>
      catalogApi.createProduct({ ...data, storeId: myStore!.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      toast.success('Product created');
      setDialogOpen(false);
      reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProductFormData }) =>
      catalogApi.updateProduct(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      toast.success('Product updated');
      setDialogOpen(false);
      setEditingProduct(null);
      reset();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      catalogApi.updateProduct(id, { isActive }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] }),
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => catalogApi.deleteProduct(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      toast.success('Product deleted');
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function openCreate() {
    setEditingProduct(null);
    reset({ name: '', slug: '', price: '', compareAtPrice: '', description: '', imageUrl: '' });
    setDialogOpen(true);
  }

  function openEdit(product: Product) {
    setEditingProduct(product);
    reset({
      name: product.name,
      slug: product.slug,
      price: product.price,
      compareAtPrice: product.compareAtPrice ?? '',
      description: product.description ?? '',
      imageUrl: product.imageUrl ?? '',
      categoryId: product.categoryId ?? '',
    });
    setDialogOpen(true);
  }

  function onSubmit(data: ProductFormData) {
    if (editingProduct) {
      updateMutation.mutate({ id: editingProduct.id, data });
    } else {
      createMutation.mutate(data);
    }
  }

  if (!isAuthenticated) return null;

  return (
    <DashboardLayout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Products</h1>
            <p className="text-slate-500 mt-1">Manage your store's products</p>
          </div>
          {myStore ? (
            <Button onClick={openCreate} className="bg-indigo-600 hover:bg-indigo-700 gap-2">
              <Plus className="w-4 h-4" />
              Add Product
            </Button>
          ) : null}
        </div>

        {!myStore && !isLoading ? (
          <div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
            <Package className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600 font-medium">You don't have a store yet</p>
            <p className="text-slate-400 text-sm mt-1">Create a store first to add products</p>
            <Button
              className="mt-4 bg-indigo-600 hover:bg-indigo-700"
              onClick={() => navigate({ to: '/dashboard/store' })}
            >
              Create Store
            </Button>
          </div>
        ) : isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
          </div>
        ) : products.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
            <Package className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600 font-medium">No products yet</p>
            <p className="text-slate-400 text-sm mt-1">Add your first product to get started</p>
            <Button onClick={openCreate} className="mt-4 bg-indigo-600 hover:bg-indigo-700 gap-2">
              <Plus className="w-4 h-4" />
              Add Product
            </Button>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="divide-y divide-slate-100">
              {products.map((product) => (
                <div key={product.id} className="flex items-center gap-4 p-4 hover:bg-slate-50 transition-colors">
                  {/* Image */}
                  <div className="w-12 h-12 bg-slate-100 rounded-lg flex-shrink-0 overflow-hidden">
                    {product.imageUrl ? (
                      <img src={product.imageUrl} alt={product.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-5 h-5 text-slate-300" />
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-900 truncate">{product.name}</p>
                    <p className="text-sm text-slate-500">/{product.slug}</p>
                  </div>

                  {/* Price */}
                  <div className="text-right hidden sm:block">
                    <p className="font-semibold text-slate-900">{formatPrice(product.price)}</p>
                    {product.compareAtPrice && (
                      <p className="text-xs text-slate-400 line-through">{formatPrice(product.compareAtPrice)}</p>
                    )}
                  </div>

                  {/* Status toggle */}
                  <button
                    onClick={() => toggleMutation.mutate({ id: product.id, isActive: !product.isActive })}
                    disabled={toggleMutation.isPending}
                    className="flex items-center gap-1.5 text-sm"
                    title={product.isActive ? 'Deactivate' : 'Activate'}
                  >
                    {product.isActive ? (
                      <ToggleRight className="w-6 h-6 text-green-500" />
                    ) : (
                      <ToggleLeft className="w-6 h-6 text-slate-300" />
                    )}
                    <Badge className={product.isActive ? 'bg-green-100 text-green-700 text-xs' : 'bg-slate-100 text-slate-500 text-xs'}>
                      {product.isActive ? 'Active' : 'Inactive'}
                    </Badge>
                  </button>

                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-slate-400 hover:text-indigo-600"
                      onClick={() => openEdit(product)}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 text-slate-400 hover:text-red-600"
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        if (confirm(`Delete "${product.name}"?`)) {
                          deleteMutation.mutate(product.id);
                        }
                      }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Create / Edit Dialog */}
        <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) setEditingProduct(null); }}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>{editingProduct ? 'Edit Product' : 'Add Product'}</DialogTitle>
            </DialogHeader>
            <Separator />
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
              <div>
                <Label htmlFor="p-name">Name</Label>
                <Input
                  id="p-name"
                  {...register('name', {
                    onChange: (e) => {
                      if (!editingProduct) {
                        setValue('slug', slugify(e.target.value), { shouldValidate: true });
                      }
                    },
                  })}
                  placeholder="Product name"
                  className="mt-1"
                />
                {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>}
              </div>

              <div>
                <Label htmlFor="p-slug">Slug</Label>
                <Input id="p-slug" {...register('slug')} placeholder="product-slug" className="mt-1" />
                {errors.slug && <p className="text-red-500 text-xs mt-1">{errors.slug.message}</p>}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="p-price">Price</Label>
                  <Input id="p-price" {...register('price')} placeholder="29.99" className="mt-1" />
                  {errors.price && <p className="text-red-500 text-xs mt-1">{errors.price.message}</p>}
                </div>
                <div>
                  <Label htmlFor="p-compare">Compare At</Label>
                  <Input id="p-compare" {...register('compareAtPrice')} placeholder="39.99" className="mt-1" />
                </div>
              </div>

              <div>
                <Label htmlFor="p-desc">Description</Label>
                <Textarea id="p-desc" {...register('description')} rows={3} placeholder="Product description..." className="mt-1" />
              </div>

              <div>
                <Label htmlFor="p-image">Image URL</Label>
                <Input id="p-image" {...register('imageUrl')} placeholder="https://..." className="mt-1" />
                {errors.imageUrl && <p className="text-red-500 text-xs mt-1">{errors.imageUrl.message}</p>}
              </div>

              <div className="flex gap-3 pt-1">
                <Button
                  type="submit"
                  className="flex-1 bg-indigo-600 hover:bg-indigo-700"
                  disabled={createMutation.isPending || updateMutation.isPending}
                >
                  {createMutation.isPending || updateMutation.isPending
                    ? 'Saving...'
                    : editingProduct ? 'Save Changes' : 'Create Product'}
                </Button>
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
}
