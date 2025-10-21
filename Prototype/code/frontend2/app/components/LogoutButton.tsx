'use client';

import { useRouter } from 'next/navigation';
import { logout } from '../../lib/auth';

export default function LogoutButton() {
  const router = useRouter();

  const onClick = async () => {
    await logout();
    router.replace('/login');
  };

  return (
    <button
      onClick={onClick}
      className="inline-flex items-center rounded-md bg-neutral-200 hover:bg-neutral-300
                 dark:bg-neutral-700 dark:hover:bg-neutral-600 px-3 py-1.5 text-sm font-medium"
      title="Sign out"
    >
      Logout
    </button>
  );
}
