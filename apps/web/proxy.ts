import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const sessionToken = request.cookies.get("daycache_session")?.value;
  const isAuthPage =
    request.nextUrl.pathname === "/login" || request.nextUrl.pathname === "/register";

  // If no session token and trying to access a protected route, redirect to root (which shows AuthView for now)
  // Wait, right now we don't have a /login route, AuthView is rendered on / when unauthenticated.
  // We need to either create a /login route or let the client handle it for the root route.
  // Actually, let's create a /login route so we can properly protect all other routes!

  if (!sessionToken && !isAuthPage && request.nextUrl.pathname !== "/login") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (sessionToken && isAuthPage) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
