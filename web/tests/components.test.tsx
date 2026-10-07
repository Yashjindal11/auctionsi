import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BarChart, ContributionBars, Histogram, Line, Scatter } from "../src/charts";
import { Button, ErrorNote, Stat, StatusBadge, Table } from "../src/ui";

afterEach(cleanup);

describe("Table", () => {
  const rows = [
    { id: "a", price: 0.5 },
    { id: "b", price: 0 },
  ];
  const columns = [
    { key: "id", label: "Id" },
    { key: "price", label: "Price", align: "right" as const },
  ];

  it("shows the empty message without rows", () => {
    render(<Table rows={[]} columns={columns} empty="Nothing here." />);
    expect(screen.getByText("Nothing here.")).toBeTruthy();
  });

  it("formats cells with fmt", () => {
    render(<Table rows={rows} columns={columns} />);
    expect(screen.getByText("0.5")).toBeTruthy();
    expect(screen.getByText("0")).toBeTruthy();
  });

  it("activates rows by click and keyboard", () => {
    const onRow = vi.fn();
    render(<Table rows={rows} columns={columns} onRow={onRow} />);
    const [, first, second] = screen.getAllByRole("row");
    fireEvent.click(first);
    fireEvent.keyDown(second, { key: "Enter" });
    fireEvent.keyDown(second, { key: " " });
    fireEvent.keyDown(second, { key: "a" });
    expect(onRow.mock.calls.map((c) => c[0].id)).toEqual(["a", "b", "b"]);
    expect(first.getAttribute("tabindex")).toBe("0");
  });

  it("rows are not focusable without a handler", () => {
    render(<Table rows={rows} columns={columns} />);
    expect(screen.getAllByRole("row")[1].hasAttribute("tabindex")).toBe(false);
  });
});

describe("small components", () => {
  it("Button defaults to type=button and forwards clicks", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    const button = screen.getByRole("button", { name: "Go" });
    expect(button.getAttribute("type")).toBe("button");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("ErrorNote renders only with an error", () => {
    const { container, rerender } = render(<ErrorNote error={null} />);
    expect(container.textContent).toBe("");
    rerender(<ErrorNote error="boom" />);
    expect(screen.getByText("boom")).toBeTruthy();
  });

  it("Stat and StatusBadge render values", () => {
    render(
      <>
        <Stat label="Agents" value={1200} hint="registered" />
        <StatusBadge status="settled" />
      </>,
    );
    expect(screen.getByText("1,200")).toBeTruthy();
    expect(screen.getByText("registered")).toBeTruthy();
    expect(screen.getByText("settled")).toBeTruthy();
  });
});

describe("charts", () => {
  it("render placeholders without data", () => {
    render(
      <>
        <BarChart data={[]} label="b" />
        <Histogram values={[]} label="h" />
        <Scatter points={[]} label="s" />
        <Line values={[1]} label="l" />
      </>,
    );
    expect(screen.getAllByText("No data.")).toHaveLength(3);
    expect(screen.getByText("Not enough data.")).toBeTruthy();
  });

  it("render labelled SVGs with data", () => {
    render(
      <>
        <BarChart data={[{ label: "a", value: 2 }, { label: "b", value: 1 }]} label="share" />
        <Histogram values={[1, 1, 1]} label="prices" />
        <Scatter points={[{ x: 1, y: 2 }, { x: 2, y: 3 }]} label="scatter" />
        <Line values={[0.2, 0.1, 0.3]} label="hhi" />
      </>,
    );
    for (const name of ["share", "prices", "scatter", "hhi"]) {
      expect(screen.getByRole("img", { name })).toBeTruthy();
    }
  });

  it("histogram puts every value in a bin", () => {
    const { container } = render(<Histogram values={[0, 0.5, 1, 1]} bins={2} label="h" />);
    const titles = [...container.querySelectorAll("rect title")].map((t) => t.textContent);
    expect(titles).toEqual(["0: 1", "0.5: 3"]);
  });

  it("contribution bars sign positive values only", () => {
    render(<ContributionBars contributions={{ price: -0.25, quality: 0.1, zero: 0 }} />);
    expect(screen.getByText("-0.25")).toBeTruthy();
    expect(screen.getByText("+0.1")).toBeTruthy();
    expect(screen.getByText("0")).toBeTruthy();
  });
});
