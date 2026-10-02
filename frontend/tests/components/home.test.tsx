import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import Home from "../../src/app/page";
import { PRODUCT_NAME } from "../../src/lib/product";

test("the startup page identifies the product and its development status", () => {
  render(<Home />);

  expect(screen.getByRole("main")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { level: 1, name: PRODUCT_NAME }),
  ).toBeVisible();
  expect(screen.getByText(/recommender is under development/)).toBeVisible();
});
