import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CheckoutButton } from "../../checkout-button";

describe("CheckoutButton", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders button with children text", () => {
    render(<CheckoutButton planId="starter">Start free trial</CheckoutButton>);

    expect(screen.getByRole("button", { name: "Start free trial" })).toBeInTheDocument();
  });

  it("shows 'Redirecting...' when loading", async () => {
    // fetch that never resolves to keep loading state
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));

    render(<CheckoutButton planId="starter">Start free trial</CheckoutButton>);

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Redirecting..." })).toBeInTheDocument();
    });

    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("calls fetch with correct payload on click", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ url: "https://checkout.stripe.com/session" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    // Mock window.location.href assignment
    const locationSpy = vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      href: "",
    } as Location);

    render(<CheckoutButton planId="team">Start free trial</CheckoutButton>);

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith("/api/stripe/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planId: "team" }),
      });
    });

    locationSpy.mockRestore();
  });

  it("redirects to login on 401 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    // Use delete + defineProperty to mock location.href assignment
    const originalLocation = window.location;
    const mockLocation = { ...originalLocation, href: "" };
    Object.defineProperty(window, "location", {
      writable: true,
      value: mockLocation,
    });

    render(<CheckoutButton planId="starter">Start free trial</CheckoutButton>);

    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(mockLocation.href).toBe("/login?plan=starter");
    });

    Object.defineProperty(window, "location", {
      writable: true,
      value: originalLocation,
    });
  });
});
