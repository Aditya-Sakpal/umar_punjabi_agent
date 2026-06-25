import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentPanel } from "../components/AgentPanel";

describe("AgentPanel", () => {
  it("streams token text for an agent", () => {
    render(
      <AgentPanel name="signal" status="thinking" tokens="Bull case forming on volume." />,
    );
    expect(screen.getByTestId("agent-tokens-signal")).toHaveTextContent("Bull case forming");
    expect(screen.getByText("Thinking...")).toBeInTheDocument();
  });

  it("uses challenging label for risk agent", () => {
    render(<AgentPanel name="risk" status="challenging" tokens="Funding elevated" accent="risk" />);
    expect(screen.getByText("Challenging...")).toBeInTheDocument();
  });
});
