import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useCategories, useTags } from '@/hooks/use-blog';
import type { PostListParams } from '@/types/blog';

interface PostFiltersProps {
  params: PostListParams;
  onChange: (params: PostListParams) => void;
}

export function PostFilters({ params, onChange }: PostFiltersProps) {
  const { data: tags = [] } = useTags();
  const { data: categories = [] } = useCategories();

  return (
    <div className="flex flex-wrap gap-3 items-center">
      {/* Category filter */}
      <Select
        value={params.category ?? 'all'}
        onValueChange={val =>
          onChange({ ...params, category: val === 'all' ? undefined : val, page: 1 })
        }
      >
        <SelectTrigger className="w-44">
          <SelectValue placeholder="All categories" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All categories</SelectItem>
          {categories.map(cat => (
            <SelectItem key={cat.id} value={cat.slug}>
              {cat.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Tag filter */}
      <Select
        value={params.tag ?? 'all'}
        onValueChange={val =>
          onChange({ ...params, tag: val === 'all' ? undefined : val, page: 1 })
        }
      >
        <SelectTrigger className="w-44">
          <SelectValue placeholder="All tags" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All tags</SelectItem>
          {tags.map(tag => (
            <SelectItem key={tag.id} value={tag.slug}>
              {tag.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Featured toggle */}
      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <input
          type="checkbox"
          checked={params.featured ?? false}
          onChange={e =>
            onChange({
              ...params,
              featured: e.target.checked || undefined,
              page: 1,
            })
          }
          className="h-4 w-4 rounded border-input accent-primary"
        />
        Featured only
      </label>
    </div>
  );
}
