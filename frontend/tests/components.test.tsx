import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataState, Stat, StatusBadge } from "@/components/ui/primitives";
import { DownloadCsv } from "@/components/ui/download";
import { buildUrl, type Meta } from "@/lib/api";
import { fmtInt, fmtNum, fmtPct, fmtDuration, NA } from "@/lib/format";

const meta = (s: Meta["data_status"]): Meta => ({
  game: "lol", data_status: s, data_type: "historical", source: "Oracle's Elixir", attribution: null,
  sample_period: null, pagination: null, generated_at: "2026-01-01T00:00:00Z", notes: [],
});
const q = <T,>(over: Partial<{ data: { data: T | null; meta: Meta }; error: Error | null; isLoading: boolean }>) => ({
  data: undefined, error: null, isLoading: false, refetch: () => {}, ...over,
});

describe("format helpers", () => {
  it("never shows missing values as zero", () => {
    expect(fmtInt(null)).toBe(NA);
    expect(fmtNum(undefined)).toBe(NA);
    expect(fmtPct(null)).toBe(NA);
    expect(fmtDuration(null)).toBe(NA);
    expect(fmtInt(0)).toBe("0");
  });
  it("formats values", () => {
    expect(fmtPct(0.5234)).toBe("52.3%");
    expect(fmtDuration(1865)).toBe("31:05");
  });
});

describe("api url builder", () => {
  it("drops empty params", () => {
    const u = new URL(buildUrl("/teams", { q: "", league: undefined, page: 2 }));
    expect(u.pathname).toBe("/api/v1/teams");
    expect(u.searchParams.get("page")).toBe("2");
    expect(u.searchParams.has("q")).toBe(false);
  });
});

describe("DataState", () => {
  it("shows loading", () => {
    render(<DataState query={q<number>({ isLoading: true })}>{() => <p>content</p>}</DataState>);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
  it("shows errors with the message", () => {
    render(<DataState query={q<number>({ error: new Error("boom") })}>{() => <p>content</p>}</DataState>);
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
  });
  it("shows integration pending instead of content", () => {
    render(<DataState gameName="VALORANT" query={q<number>({ data: { data: null, meta: meta("integration_pending") } })}>{() => <p>content</p>}</DataState>);
    expect(screen.getByText(/VALORANT: verified data integration pending/)).toBeInTheDocument();
    expect(screen.queryByText("content")).toBeNull();
  });
  it("shows the no-data state when nothing is imported", () => {
    render(<DataState query={q<number>({ data: { data: 1, meta: meta("empty") } })}>{() => <p>content</p>}</DataState>);
    expect(screen.getByText(/No historical data has been imported/)).toBeInTheDocument();
  });
  it("renders content when available", () => {
    render(<DataState query={q<number>({ data: { data: 7, meta: meta("available") } })}>{(d) => <p>value {d}</p>}</DataState>);
    expect(screen.getByText("value 7")).toBeInTheDocument();
  });
});

describe("small components", () => {
  it("labels statuses", () => {
    render(<StatusBadge status="integration_pending" />);
    expect(screen.getByText("Integration pending")).toBeInTheDocument();
  });
  it("renders a stat", () => {
    render(<Stat label="Games" value="1,234" />);
    expect(screen.getByText("1,234")).toBeInTheDocument();
  });
  it("disables CSV download without rows", () => {
    render(<DownloadCsv rows={[]} filename="x" />);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
