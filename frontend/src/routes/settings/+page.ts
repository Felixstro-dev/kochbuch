import { api, ApiError } from '#lib/api';
import type { AppSettings, FetchStatus } from '#lib/types';

export async function load({ parent }: { parent: () => Promise<{ status: { user: { role: string } | null } }> }) {
  const layout = await parent();
  const isAdmin = layout.status.user?.role === 'admin';
  try {
    const settings = await api.get<AppSettings>('/settings');
    let status: FetchStatus | null = null;
    if (isAdmin) {
      try {
        status = await api.get<FetchStatus>('/system/fetch-status');
      } catch {
        status = null;
      }
    }
    return { settings, status, isAdmin };
  } catch (cause) {
    return {
      settings: null,
      status: null,
      isAdmin,
      error:
        cause instanceof ApiError
          ? cause.message
          : 'Die Einstellungen konnten nicht geladen werden.'
    };
  }
}
