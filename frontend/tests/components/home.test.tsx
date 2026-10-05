import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import Home from "../../src/app/page";

test("meal workspace provides editable examples and accessible category choices", () => {
  render(<Home />);
  expect(screen.getByRole("heading", { level: 1, name: "What sounds good?" })).toBeVisible();
  expect(screen.getByRole("radio", { name: "Eat out" })).toBeVisible();
  expect(screen.getByRole("radio", { name: "Cook" })).toBeVisible();
  expect(screen.getByLabelText("Message")).toBeVisible();
  expect(screen.getByText("Synthetic teaching catalog")).toBeVisible();
});
