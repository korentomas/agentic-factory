import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Lightweight middleware that checks for the session cookie's EXISTENCE
 * without decoding it. Actual auth validation happens server-side in
 * route handlers via auth(). This avoids importing the full NextAuth +
 * Drizzle adapter + postgres driver into the edge bundle (~140kB savings).
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check for session token cookie (don't decode -- just check existence)
  const sessionToken =
    request.cookies.get("authjs.session-token")?.value ||
    request.cookies.get("__Secure-authjs.session-token")?.value;

  const isAuthenticated = !!sessionToken;

  // Protected routes -- redirect to login if unauthenticated
  const isProtected =
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/chat") ||
    pathname.startsWith("/analytics");

  if (isProtected && !isAuthenticated) {
    return NextResponse.redirect(new URL("/login", request.nextUrl.origin));
  }

  // Redirect authenticated users from landing page and login to /chat
  if ((pathname === "/" || pathname === "/login") && isAuthenticated) {
    return NextResponse.redirect(new URL("/chat", request.nextUrl.origin));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/dashboard/:path*", "/chat/:path*", "/analytics", "/login"],
};
