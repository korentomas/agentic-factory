import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const isAuthenticated = !!req.auth;
  const { pathname } = req.nextUrl;

  // Protected routes — redirect to login if unauthenticated
  const isProtected =
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/chat") ||
    pathname.startsWith("/analytics");

  if (isProtected && !isAuthenticated) {
    return NextResponse.redirect(new URL("/login", req.nextUrl.origin));
  }

  // Redirect authenticated users from landing page and login to /chat
  if ((pathname === "/" || pathname === "/login") && isAuthenticated) {
    return NextResponse.redirect(new URL("/chat", req.nextUrl.origin));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/", "/dashboard/:path*", "/chat/:path*", "/analytics", "/login"],
};
