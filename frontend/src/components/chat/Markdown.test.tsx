import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import Markdown from "./Markdown";

describe("Markdown", () => {
  it("renders bold text as <strong>", () => {
    const { container } = render(<Markdown content="This is **important**." />);
    const strong = container.querySelector("strong");
    expect(strong).not.toBeNull();
    expect(strong?.textContent).toBe("important");
  });

  it("renders unordered lists", () => {
    const { container } = render(<Markdown content={"- one\n- two"} />);
    const items = container.querySelectorAll("ul li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("one");
  });

  it("renders ordered lists", () => {
    const { container } = render(<Markdown content={"1. first\n2. second"} />);
    expect(container.querySelector("ol")).not.toBeNull();
    expect(container.querySelectorAll("ol li")).toHaveLength(2);
  });

  it("does not inject raw HTML (XSS-safe)", () => {
    const { container } = render(<Markdown content={'<img src=x onerror="alert(1)">'} />);
    // The angle-bracket string is rendered as text, not as an <img> element.
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
  });

  it("renders inline code", () => {
    const { container } = render(<Markdown content="Run `npm test` now." />);
    expect(container.querySelector("code")?.textContent).toBe("npm test");
  });
});
