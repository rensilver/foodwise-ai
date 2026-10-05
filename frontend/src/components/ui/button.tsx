import { Slot } from "radix-ui";
import { cva, type VariantProps } from "class-variance-authority";
import { twMerge } from "tailwind-merge";
import type { ButtonHTMLAttributes } from "react";

const variants = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-md border px-4 py-2 font-semibold",
  {
    variants: {
      variant: {
        primary: "border-cobalt bg-cobalt text-white",
        secondary: "border-slate bg-white text-ink",
        danger: "border-[#a52222] bg-white text-[#a52222]",
      },
    },
    defaultVariants: { variant: "primary" },
  },
);
export function Button({
  asChild,
  className,
  variant,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof variants> & { asChild?: boolean }) {
  const Component = asChild ? Slot.Root : "button";
  return (
    <Component
      className={twMerge(variants({ variant }), className)}
      {...props}
    />
  );
}
