import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';

export const Route = createFileRoute('/login')({
  component: LoginPage,
});

function LoginPage() {
  const { login, register, user, logout } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      if (isRegister) {
        await register(email, username, password);
      } else {
        await login(email, password);
      }
      navigate({ to: '/' });
    } catch {
      setError('Authentication failed. Check your credentials.');
    }
  };

  if (user) {
    return (
      <div className="max-w-md mx-auto mt-16 text-center">
        <p className="mb-4">Logged in as <strong>{user.email}</strong></p>
        <button onClick={logout} className="px-4 py-2 bg-red-600 text-white rounded">
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto mt-16">
      <h2 className="text-2xl font-bold mb-6">{isRegister ? 'Register' : 'Login'}</h2>
      {error && <p className="text-red-600 mb-4">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full border rounded px-3 py-2"
          required
        />
        {isRegister && (
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full border rounded px-3 py-2"
            required
          />
        )}
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full border rounded px-3 py-2"
          required
        />
        <button type="submit" className="w-full py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700">
          {isRegister ? 'Register' : 'Login'}
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-500 text-center">
        <button onClick={() => setIsRegister(!isRegister)} className="text-indigo-600 hover:underline">
          {isRegister ? 'Already have an account? Login' : "Don't have an account? Register"}
        </button>
      </p>
    </div>
  );
}
