import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { useProduct, useVariants } from '@/hooks/use-products';
import { useReviews, useReviewSummary, useCreateReview } from '@/hooks/use-reviews';
import { useAddToCart } from '@/hooks/use-cart';
import { useAuth } from '@/lib/store';
import { StarRating } from '@/components/products/StarRating';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatPrice, formatDate } from '@/lib/utils';
import { ShoppingCart, Star, Package, ChevronLeft } from 'lucide-react';
import { Link } from '@tanstack/react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

export const Route = createFileRoute('/products/$productId')({
  component: ProductDetailPage,
});

const reviewSchema = z.object({
  rating: z.number().min(1).max(5),
  title: z.string().min(1, 'Title is required').max(100),
  body: z.string().min(10, 'Review must be at least 10 characters').max(2000),
});
type ReviewFormData = z.infer<typeof reviewSchema>;

function ProductDetailPage() {
  const { productId } = Route.useParams();
  const { isAuthenticated } = useAuth();
  const [selectedVariantId, setSelectedVariantId] = useState<string | undefined>();
  const [quantity, setQuantity] = useState(1);
  const [hoverRating, setHoverRating] = useState(0);

  const { data: product, isLoading: productLoading } = useProduct(productId);
  const { data: variantsData } = useVariants(productId);
  const { data: reviewsData, isLoading: reviewsLoading } = useReviews(productId);
  const { data: reviewSummary } = useReviewSummary(productId);
  const addToCart = useAddToCart();
  const createReview = useCreateReview(productId);

  const variants = variantsData?.items ?? [];
  const reviews = reviewsData?.items ?? [];

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<ReviewFormData>({
    resolver: zodResolver(reviewSchema),
    defaultValues: { rating: 0, title: '', body: '' },
  });
  const formRating = watch('rating');

  function handleAddToCart() {
    if (!product) return;
    addToCart.mutate({
      productId: product.id,
      variantId: selectedVariantId,
      quantity,
    });
  }

  function onReviewSubmit(data: ReviewFormData) {
    createReview.mutate(data, { onSuccess: () => reset() });
  }

  if (productLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="grid md:grid-cols-2 gap-10">
          <Skeleton className="h-96 rounded-xl" />
          <div className="space-y-4">
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-6 w-1/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-10 w-1/2 mt-4" />
          </div>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="container mx-auto px-4 py-20 text-center">
        <Package className="w-12 h-12 text-slate-300 mx-auto mb-4" />
        <p className="text-slate-600 text-lg">Product not found</p>
        <Link to="/products">
          <Button variant="outline" className="mt-4">Back to Products</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="container mx-auto px-4 py-8">
        {/* Breadcrumb */}
        <Link to="/products" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-6">
          <ChevronLeft className="w-4 h-4" />
          Back to Products
        </Link>

        {/* Product Main */}
        <div className="grid md:grid-cols-2 gap-10 mb-12">
          {/* Image */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden aspect-square flex items-center justify-center">
            {product.imageUrl ? (
              <img
                src={product.imageUrl}
                alt={product.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <Package className="w-20 h-20 text-slate-300" />
            )}
          </div>

          {/* Details */}
          <div className="space-y-5">
            <div>
              {!product.isActive && (
                <Badge className="mb-2 bg-red-100 text-red-700">Out of Stock</Badge>
              )}
              <h1 className="text-3xl font-bold text-slate-900">{product.name}</h1>

              {reviewSummary && reviewSummary.totalReviews > 0 && (
                <div className="flex items-center gap-2 mt-2">
                  <StarRating rating={reviewSummary.averageRating} size="sm" />
                  <span className="text-sm text-slate-500">
                    ({reviewSummary.totalReviews} review{reviewSummary.totalReviews !== 1 ? 's' : ''})
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-baseline gap-3">
              <span className="text-3xl font-bold text-slate-900">
                {formatPrice(product.price)}
              </span>
              {product.compareAtPrice && (
                <span className="text-lg text-slate-400 line-through">
                  {formatPrice(product.compareAtPrice)}
                </span>
              )}
            </div>

            {product.description && (
              <p className="text-slate-600 leading-relaxed">{product.description}</p>
            )}

            <Separator />

            {/* Variant Selection */}
            {variants.length > 0 && (
              <div>
                <Label className="text-sm font-medium text-slate-700 mb-2 block">Variant</Label>
                <Select value={selectedVariantId} onValueChange={setSelectedVariantId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select a variant" />
                  </SelectTrigger>
                  <SelectContent>
                    {variants.filter((v) => v.isActive).map((variant) => (
                      <SelectItem key={variant.id} value={variant.id}>
                        {variant.name} {variant.priceOverride ? `— ${formatPrice(variant.priceOverride)}` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Quantity */}
            <div>
              <Label className="text-sm font-medium text-slate-700 mb-2 block">Quantity</Label>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                >−</Button>
                <span className="w-10 text-center font-medium">{quantity}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuantity((q) => q + 1)}
                >+</Button>
              </div>
            </div>

            {/* Add to Cart */}
            <Button
              size="lg"
              className="w-full bg-indigo-600 hover:bg-indigo-700 gap-2"
              disabled={!product.isActive || addToCart.isPending}
              onClick={handleAddToCart}
            >
              <ShoppingCart className="w-5 h-5" />
              {addToCart.isPending ? 'Adding...' : 'Add to Cart'}
            </Button>
          </div>
        </div>

        {/* Reviews Section */}
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-xl font-bold text-slate-900 mb-6">Customer Reviews</h2>

          {/* Summary */}
          {reviewSummary && reviewSummary.totalReviews > 0 && (
            <div className="flex items-start gap-8 mb-8 pb-8 border-b border-slate-100">
              <div className="text-center">
                <p className="text-5xl font-bold text-slate-900">
                  {reviewSummary.averageRating.toFixed(1)}
                </p>
                <StarRating rating={reviewSummary.averageRating} size="md" />
                <p className="text-sm text-slate-500 mt-1">
                  {reviewSummary.totalReviews} reviews
                </p>
              </div>
              <div className="flex-1 space-y-2">
                {[5, 4, 3, 2, 1].map((star) => {
                  const count = reviewSummary.ratingDistribution[star.toString()] ?? 0;
                  const pct = reviewSummary.totalReviews > 0 ? (count / reviewSummary.totalReviews) * 100 : 0;
                  return (
                    <div key={star} className="flex items-center gap-2 text-sm">
                      <span className="w-4 text-slate-500">{star}</span>
                      <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />
                      <div className="flex-1 bg-slate-100 rounded-full h-2">
                        <div
                          className="bg-yellow-400 h-2 rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="w-6 text-right text-slate-400">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Review List */}
          {reviewsLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
            </div>
          ) : reviews.length === 0 ? (
            <p className="text-slate-500 text-center py-8">No reviews yet. Be the first to review!</p>
          ) : (
            <div className="space-y-6 mb-8">
              {reviews.map((review) => (
                <div key={review.id} className="border-b border-slate-100 pb-6 last:border-0">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <StarRating rating={review.rating} size="sm" />
                      <p className="font-semibold text-slate-900 mt-1">{review.title}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-xs text-slate-400">{formatDate(review.createdAt)}</span>
                      {review.isVerifiedPurchase && (
                        <Badge className="ml-2 bg-green-100 text-green-700 text-xs">Verified</Badge>
                      )}
                    </div>
                  </div>
                  <p className="text-slate-600 text-sm leading-relaxed">{review.body}</p>
                </div>
              ))}
            </div>
          )}

          {/* Review Form */}
          {isAuthenticated && (
            <>
              <Separator className="mb-6" />
              <h3 className="text-lg font-semibold text-slate-900 mb-4">Write a Review</h3>
              <form onSubmit={handleSubmit(onReviewSubmit)} className="space-y-4">
                {/* Star picker */}
                <div>
                  <Label className="text-sm font-medium text-slate-700 mb-2 block">Rating</Label>
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        onMouseEnter={() => setHoverRating(star)}
                        onMouseLeave={() => setHoverRating(0)}
                        onClick={() => setValue('rating', star, { shouldValidate: true })}
                        className="p-0.5"
                      >
                        <Star
                          className={`w-6 h-6 transition-colors ${
                            star <= (hoverRating || formRating)
                              ? 'text-yellow-400 fill-yellow-400'
                              : 'text-slate-300'
                          }`}
                        />
                      </button>
                    ))}
                  </div>
                  {errors.rating && (
                    <p className="text-red-500 text-xs mt-1">Please select a rating</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="review-title">Title</Label>
                  <Input
                    id="review-title"
                    placeholder="Summarize your experience"
                    {...register('title')}
                    className="mt-1"
                  />
                  {errors.title && <p className="text-red-500 text-xs mt-1">{errors.title.message}</p>}
                </div>

                <div>
                  <Label htmlFor="review-body">Review</Label>
                  <Textarea
                    id="review-body"
                    placeholder="Tell others what you think..."
                    rows={4}
                    {...register('body')}
                    className="mt-1"
                  />
                  {errors.body && <p className="text-red-500 text-xs mt-1">{errors.body.message}</p>}
                </div>

                <Button
                  type="submit"
                  disabled={createReview.isPending}
                  className="bg-indigo-600 hover:bg-indigo-700"
                >
                  {createReview.isPending ? 'Submitting...' : 'Submit Review'}
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
