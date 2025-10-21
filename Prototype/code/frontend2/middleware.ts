import { NextRequest, NextResponse } from 'next/server';

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // public routes
  if (pathname.startsWith('/login') || pathname.startsWith('/_next') || pathname.startsWith('/public')) {
    return NextResponse.next();
  }

  const hasAccess = req.cookies.get('access')?.value;
  if (!hasAccess) {
    const url = new URL('/login', req.url);
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/', '/((?!api|_next|public).*)'],
};
