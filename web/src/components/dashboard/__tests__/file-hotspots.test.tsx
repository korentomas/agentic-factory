import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FileHotspotsPanel } from "../file-hotspots";
import type { FileHotspot } from "@/lib/data/types";

function makeHotspot(overrides: Partial<FileHotspot> = {}): FileHotspot {
  return {
    path: "src/auth/login.ts",
    appearances: 8,
    inSuccessful: 6,
    inFailed: 2,
    ...overrides,
  };
}

describe("FileHotspotsPanel", () => {
  it("returns null when no hotspots", () => {
    const { container } = render(<FileHotspotsPanel hotspots={[]} />);

    expect(container.innerHTML).toBe("");
  });

  it("renders the heading and description", () => {
    render(<FileHotspotsPanel hotspots={[makeHotspot()]} />);

    expect(screen.getByText("File Hotspots")).toBeInTheDocument();
    expect(
      screen.getByText("Most frequently changed files across agent tasks")
    ).toBeInTheDocument();
  });

  it("renders file paths", () => {
    render(
      <FileHotspotsPanel
        hotspots={[
          makeHotspot({ path: "src/auth/login.ts" }),
          makeHotspot({ path: "src/api/routes.ts" }),
          makeHotspot({ path: "tests/auth.test.ts" }),
        ]}
      />
    );

    expect(screen.getByText("src/auth/login.ts")).toBeInTheDocument();
    expect(screen.getByText("src/api/routes.ts")).toBeInTheDocument();
    expect(screen.getByText("tests/auth.test.ts")).toBeInTheDocument();
  });

  it("shows appearance counts", () => {
    render(
      <FileHotspotsPanel
        hotspots={[
          makeHotspot({ path: "src/a.ts", appearances: 8 }),
          makeHotspot({ path: "src/b.ts", appearances: 5 }),
          makeHotspot({ path: "src/c.ts", appearances: 3 }),
        ]}
      />
    );

    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders success/failure bars for each hotspot", () => {
    const { container } = render(
      <FileHotspotsPanel
        hotspots={[
          makeHotspot({
            path: "src/auth.ts",
            appearances: 10,
            inSuccessful: 7,
            inFailed: 3,
          }),
        ]}
      />
    );

    // Two inner bar divs (success and failure) inside the bar container
    // The bar container has w-20 class
    const barContainers = container.querySelectorAll(".w-20");
    expect(barContainers.length).toBe(1);

    // Each bar container should have 2 child divs (success bar and failure bar)
    const bars = barContainers[0].querySelectorAll("div");
    expect(bars.length).toBe(2);
  });

  it("limits display to 10 hotspots", () => {
    const hotspots = Array.from({ length: 15 }, (_, i) =>
      makeHotspot({
        path: `src/file-${i}.ts`,
        appearances: 15 - i,
      })
    );
    render(<FileHotspotsPanel hotspots={hotspots} />);

    // Should show only first 10
    expect(screen.getByText("src/file-0.ts")).toBeInTheDocument();
    expect(screen.getByText("src/file-9.ts")).toBeInTheDocument();
    expect(screen.queryByText("src/file-10.ts")).not.toBeInTheDocument();
  });

  it("renders correctly with a single hotspot", () => {
    render(
      <FileHotspotsPanel
        hotspots={[
          makeHotspot({
            path: "README.md",
            appearances: 1,
            inSuccessful: 1,
            inFailed: 0,
          }),
        ]}
      />
    );

    expect(screen.getByText("README.md")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});
