import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecisionCard } from "../components/DecisionCard";

describe("DecisionCard", () => {
  it("renders awaiting state without decision", () => {
    render(<DecisionCard decision={null} signal={null} />);
    expect(screen.getByText(/Awaiting committee decision/i)).toBeInTheDocument();
  });

  it("renders BUY with confidence and rationale", () => {
    render(
      <DecisionCard
        signal={null}
        decision={{
          action: "BUY",
          confidence: 0.55,
          size_pct: 2,
          stop_loss_pct: 3,
          rationale: "Momentum with sized risk",
        }}
      />,
    );
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText(/55% confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Momentum with sized risk/i)).toBeInTheDocument();
  });
});
