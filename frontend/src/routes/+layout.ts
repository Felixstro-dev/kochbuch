import { error, redirect } from '@sveltejs/kit';
import { api, ApiError } from '#lib/api';
import type { AuthStatus } from '#lib/types';

export const ssr = false;
export const prerender = false;
export const trailingSlash = 'never';

export async function load({ url }: { url: URL }) {
  let status: AuthStatus;
  try {
    status = await api.get<AuthStatus>('/auth/status');
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 401) {
      status = {
        setup_required: false,
        authenticated: false,
        user: null,
        embed_public: false,
        app_name: 'Kochbuch',
        version: ''
      };
    } else {
      throw error(503, 'Der Server ist momentan nicht erreichbar.');
    }
  }

  const path = url.pathname;
  const embed = url.searchParams.get('embed') === '1';
  const isAuthPage = path === '/login' || path === '/setup';

  if (status.setup_required && path !== '/setup') {
    throw redirect(307, '/setup');
  }
  if (!status.setup_required && status.authenticated && isAuthPage) {
    throw redirect(307, '/');
  }
  if (!status.setup_required && !status.authenticated && !isAuthPage && !status.embed_public) {
    const next = `${url.pathname}${url.search}`;
    throw redirect(307, `/login?next=${encodeURIComponent(next)}`);
  }

  return { status, embed, path };
}
