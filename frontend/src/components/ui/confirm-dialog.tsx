"use client";
import { Dialog } from "radix-ui";
import { Button } from "./button";
import type { ReactNode } from "react";
export function ConfirmDialog({ trigger, title, children, onConfirm, busy = false }: { trigger: string; title: string; children: ReactNode; onConfirm: () => Promise<void>; busy?: boolean }) {
  return <Dialog.Root><Dialog.Trigger asChild><Button variant="danger" disabled={busy}>{trigger}</Button></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="dialog stack"><Dialog.Title>{title}</Dialog.Title><Dialog.Description asChild><div>{children}</div></Dialog.Description><div className="actions"><Dialog.Close asChild><Button variant="secondary">Keep it</Button></Dialog.Close><Dialog.Close asChild><Button variant="danger" onClick={() => { void onConfirm(); }}>Confirm deletion</Button></Dialog.Close></div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
