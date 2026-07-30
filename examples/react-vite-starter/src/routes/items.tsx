import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { useItems, useCreateItem, useDeleteItem } from '@/hooks/useItems';
import { useAuth } from '@/hooks/useAuth';
import { ProtectedRoute } from '@/components/ProtectedRoute';

export const Route = createFileRoute('/items')({
  component: () => (
    <ProtectedRoute>
      <ItemsPage />
    </ProtectedRoute>
  ),
});

function ItemsPage() {
  const { user } = useAuth();
  const { data: items = [], isLoading } = useItems();
  const createItem = useCreateItem();
  const deleteItem = useDeleteItem();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await createItem.mutateAsync({ name, description });
    setName('');
    setDescription('');
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Items</h2>

      {user && (
        <form onSubmit={handleCreate} className="mb-8 p-4 border rounded bg-white space-y-3">
          <h3 className="font-semibold">Add Item</h3>
          <input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border rounded px-3 py-2"
            required
          />
          <input
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full border rounded px-3 py-2"
          />
          <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700">
            Create
          </button>
        </form>
      )}

      {isLoading ? (
        <p className="text-slate-500">Loading...</p>
      ) : items.length === 0 ? (
        <p className="text-slate-500">No items yet. {!user && 'Login to create one.'}</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="p-4 border rounded bg-white flex justify-between items-start">
              <div>
                <h3 className="font-semibold">{item.name}</h3>
                <p className="text-sm text-slate-500">{item.description}</p>
                <p className="text-xs text-slate-400 mt-1">{new Date(item.created_at).toLocaleDateString()}</p>
              </div>
              {user && (
                <button
                  onClick={() => deleteItem.mutate(item.id)}
                  className="text-red-600 text-sm hover:underline"
                >
                  Delete
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
