import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { SkeletonTable } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ColumnDef,
  ColumnFiltersState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  OnChangeFn,
  PaginationState,
  SortingState,
  useReactTable,
  VisibilityState,
} from '@tanstack/react-table';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Loader2,
} from 'lucide-react';
import { useState } from 'react';

/**
 * Server-side pagination info (Django Ninja format)
 */
interface ServerPagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  searchKey?: string;
  searchPlaceholder?: string;
  showColumnToggle?: boolean;
  showPagination?: boolean;
  pageSize?: number;
  /** Loading state */
  isLoading?: boolean;
  /** Server-side pagination (for Django integration) */
  serverPagination?: ServerPagination;
  /** Callback for server-side pagination */
  onPaginationChange?: (page: number, pageSize: number) => void;
  /** Callback for server-side search */
  onSearchChange?: (search: string) => void;
  /** Debounce delay for search (ms) */
  searchDebounce?: number;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  searchKey,
  searchPlaceholder = 'Search...',
  showColumnToggle = true,
  showPagination = true,
  pageSize = 10,
  isLoading = false,
  serverPagination,
  onPaginationChange,
  onSearchChange,
  searchDebounce = 300,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [rowSelection, setRowSelection] = useState({});
  const [searchValue, setSearchValue] = useState('');

  // Debounced search for server-side
  const [searchTimeout, setSearchTimeout] = useState<ReturnType<
    typeof setTimeout
  > | null>(null);

  const handleSearchChange = (value: string) => {
    setSearchValue(value);

    if (onSearchChange) {
      // Server-side search with debounce
      if (searchTimeout) clearTimeout(searchTimeout);
      setSearchTimeout(
        setTimeout(() => {
          onSearchChange(value);
        }, searchDebounce)
      );
    }
  };

  // Server-side pagination state
  const isServerSide = !!serverPagination;
  const pagination: PaginationState = isServerSide
    ? {
        pageIndex: serverPagination.page - 1,
        pageSize: serverPagination.pageSize,
      }
    : { pageIndex: 0, pageSize };

  const handlePaginationChange: OnChangeFn<PaginationState> = updater => {
    if (!onPaginationChange) return;

    const newState =
      typeof updater === 'function' ? updater(pagination) : updater;
    onPaginationChange(newState.pageIndex + 1, newState.pageSize);
  };

  const table = useReactTable({
    data,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: isServerSide ? undefined : getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: isServerSide ? undefined : getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    ...(isServerSide
      ? {
          manualPagination: true,
          manualFiltering: true,
          pageCount: serverPagination.totalPages,
          onPaginationChange: handlePaginationChange,
        }
      : {
          initialState: {
            pagination: {
              pageSize,
            },
          },
        }),
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      ...(isServerSide && { pagination }),
    },
  });

  // Show skeleton while loading
  if (isLoading && data.length === 0) {
    return <SkeletonTable rows={pageSize} columns={columns.length} />;
  }

  const currentPage = isServerSide
    ? serverPagination.page
    : table.getState().pagination.pageIndex + 1;
  const totalPages = isServerSide
    ? serverPagination.totalPages
    : table.getPageCount();
  const totalRows = isServerSide
    ? serverPagination.total
    : table.getFilteredRowModel().rows.length;

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex flex-1 items-center space-x-2">
          {(searchKey || onSearchChange) && (
            <div className="relative">
              <Input
                placeholder={searchPlaceholder}
                value={
                  onSearchChange
                    ? searchValue
                    : ((table
                        .getColumn(searchKey!)
                        ?.getFilterValue() as string) ?? '')
                }
                onChange={event =>
                  onSearchChange
                    ? handleSearchChange(event.target.value)
                    : table
                        .getColumn(searchKey!)
                        ?.setFilterValue(event.target.value)
                }
                className="max-w-sm"
              />
              {isLoading && (
                <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
              )}
            </div>
          )}
        </div>

        {showColumnToggle && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="ml-auto">
                Columns <ChevronDown className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {table
                .getAllColumns()
                .filter(column => column.getCanHide())
                .map(column => {
                  return (
                    <DropdownMenuCheckboxItem
                      key={column.id}
                      className="capitalize"
                      checked={column.getIsVisible()}
                      onCheckedChange={value =>
                        column.toggleVisibility(!!value)
                      }
                    >
                      {column.id}
                    </DropdownMenuCheckboxItem>
                  );
                })}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map(headerGroup => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map(header => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map(row => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && 'selected'}
                >
                  {row.getVisibleCells().map(cell => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {showPagination && (
        <div className="flex items-center justify-between px-2">
          <div className="flex-1 text-sm text-muted-foreground">
            {isServerSide ? (
              <>
                Showing {data.length} of {totalRows} row(s)
              </>
            ) : (
              <>
                {table.getFilteredSelectedRowModel().rows.length} of {totalRows}{' '}
                row(s) selected.
              </>
            )}
          </div>
          <div className="flex items-center space-x-6 lg:space-x-8">
            <div className="flex items-center space-x-2">
              <p className="text-sm font-medium">Rows per page</p>
              <select
                value={
                  isServerSide
                    ? serverPagination.pageSize
                    : table.getState().pagination.pageSize
                }
                onChange={e => {
                  const newSize = Number(e.target.value);
                  if (onPaginationChange) {
                    onPaginationChange(1, newSize); // Reset to page 1 on size change
                  } else {
                    table.setPageSize(newSize);
                  }
                }}
                className="h-8 w-[70px] rounded border border-input bg-background px-2 text-sm"
                disabled={isLoading}
              >
                {[10, 20, 30, 40, 50].map(size => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex w-[100px] items-center justify-center text-sm font-medium">
              Page {currentPage} of {totalPages || 1}
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                className="hidden h-8 w-8 p-0 lg:flex"
                onClick={() => {
                  if (onPaginationChange) {
                    onPaginationChange(1, serverPagination!.pageSize);
                  } else {
                    table.setPageIndex(0);
                  }
                }}
                disabled={currentPage <= 1 || isLoading}
              >
                <span className="sr-only">Go to first page</span>
                <ChevronsLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="h-8 w-8 p-0"
                onClick={() => {
                  if (onPaginationChange) {
                    onPaginationChange(
                      currentPage - 1,
                      serverPagination!.pageSize
                    );
                  } else {
                    table.previousPage();
                  }
                }}
                disabled={currentPage <= 1 || isLoading}
              >
                <span className="sr-only">Go to previous page</span>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="h-8 w-8 p-0"
                onClick={() => {
                  if (onPaginationChange) {
                    onPaginationChange(
                      currentPage + 1,
                      serverPagination!.pageSize
                    );
                  } else {
                    table.nextPage();
                  }
                }}
                disabled={currentPage >= totalPages || isLoading}
              >
                <span className="sr-only">Go to next page</span>
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="hidden h-8 w-8 p-0 lg:flex"
                onClick={() => {
                  if (onPaginationChange) {
                    onPaginationChange(totalPages, serverPagination!.pageSize);
                  } else {
                    table.setPageIndex(totalPages - 1);
                  }
                }}
                disabled={currentPage >= totalPages || isLoading}
              >
                <span className="sr-only">Go to last page</span>
                <ChevronsRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
