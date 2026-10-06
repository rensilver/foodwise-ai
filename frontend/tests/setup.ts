import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);

// jsdom does not implement native dialog or viewport APIs; browser tests cover focus.
if (typeof window !== "undefined") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: () => ({
      matches: true,
      addEventListener() {},
      removeEventListener() {},
    }),
  });
  HTMLDialogElement.prototype.show = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.showModal = HTMLDialogElement.prototype.show;
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
}
