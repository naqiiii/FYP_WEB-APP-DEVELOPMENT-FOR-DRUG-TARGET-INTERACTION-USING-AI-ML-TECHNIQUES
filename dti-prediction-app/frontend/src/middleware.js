/**
 * Next.js Edge Middleware — server-side auth guard.
 *
 * Checks for the "dti_auth" cookie (set alongside localStorage on login).
 * If no cookie is present and the route is protected, the user is redirected
 * to /login before the page even starts rendering, eliminating the "flash"
 * of the home page that the old client-side redirect produced.
 */

import { NextResponse } from 'next/server';

// These pages should never render without the auth cookie.
const PROTECTED_ROUTES = ['/result', '/history'];

const PUBLIC_ROUTES = ['/login', '/signup', '/about'];

export function middleware(request) {
    const { pathname } = request.nextUrl;
    const token = request.cookies.get('dti_auth')?.value;

    const isProtected = PROTECTED_ROUTES.some(
        (route) => pathname === route || pathname.startsWith(route + '/')
    );

    const isPublic = PUBLIC_ROUTES.some(
        (route) => pathname === route || pathname.startsWith(route + '/')
    );

    // If protected and no token → redirect to login
    if (isProtected && !isPublic && !token) {
        const loginUrl = new URL('/login', request.url);
        loginUrl.searchParams.set('redirect', pathname);
        return NextResponse.redirect(loginUrl);
    }

    // If already authenticated and trying to access login/signup → redirect to home
    if (token && (pathname === '/login' || pathname === '/signup')) {
        return NextResponse.redirect(new URL('/', request.url));
    }

    return NextResponse.next();
}

// Leave static assets and API routes alone.
export const config = {
    matcher: ['/((?!_next/static|_next/image|favicon.ico|api).*)'],
};
