"use client";
import { PageShell } from "../../components/layout/page-shell";
import { useRef, useState } from "react";
import { Button } from "../../components/ui/button";
import { ConfirmDialog } from "../../components/ui/confirm-dialog";
import type { Schema } from "../../lib/api/client";
import { RecipeDiscovery } from "../catalog/recipe-discovery";
import { PreferencesPanel } from "../preferences/preferences-panel";
import { useConversation } from "./use-conversation";
import { StageProgress } from "./stage-progress";
import { ImageAttachment } from "./image-attachment";
import { ConversationHistory } from "./conversation-history";
export function MealWorkspace({ conversationId }: { conversationId?: string }) {
  const latest = useRef<HTMLDivElement>(null);
  const chat = useConversation(conversationId);
  const [attachment, setAttachment] = useState<{
    id?: string;
    blocked: boolean;
  }>();
  const [attachmentKey, setAttachmentKey] = useState(0);
  const [pending, setPending] = useState<Schema["PreferenceUpdate"] | null>();
  const [categoryChoice, setCategory] = useState<string>();
  const retainedCategories = chat.history?.messages.findLast(
    (message) => message.role === "user",
  )?.payload?.categories as Schema["Category"][] | undefined;
  const category =
    categoryChoice ??
    (retainedCategories?.length === 1
      ? retainedCategories[0] === "recipe"
        ? "Cook"
        : "Eat out"
      : "Both");
  const currentAttachment = attachment ?? {
    id: chat.resume?.media_id ?? undefined,
    blocked: false,
  };
  const currentPreferences =
    pending === null ? undefined : (pending ?? chat.resume?.explicit);
  const categories: Schema["Category"][] =
    category === "Both"
      ? ["restaurant", "recipe"]
      : category === "Cook"
        ? ["recipe"]
        : ["restaurant"];
  function resetControls() {
    setPending(undefined);
    setCategory(undefined);
    setAttachment({ blocked: false });
    setAttachmentKey((key) => key + 1);
  }
  return (
    <PageShell
      active="meal"
      sidebarLabel="Menu and preferences"
      sidebar={
        <>
          <PreferencesPanel
            key={JSON.stringify(chat.history?.preferences)}
            saved={chat.history?.preferences}
            pending={currentPreferences}
            onChange={(value) => setPending(value ?? null)}
            disabled={chat.busy || chat.loading}
          />
          <div className="sidebar-conversation">
            <Button
              variant="secondary"
              disabled={chat.busy}
              onClick={() => {
                chat.startNew();
                resetControls();
              }}
            >
              New conversation
            </Button>
          </div>
        </>
      }
    >
      <h1>What sounds good?</h1>
      <p className="note">Synthetic teaching catalog</p>
      <p>Find a place to eat, or your next favorite thing to cook.</p>
      <p className="mobile-restrictions note">
        Must avoid:{" "}
        {[
          ...(chat.history?.preferences?.constraints ?? []).filter(
            (c) =>
              c.strength === "hard" &&
              !currentPreferences?.remove_constraints.some(
                (removed) =>
                  removed.kind === c.kind && removed.value === c.value,
              ),
          ),
          ...(currentPreferences?.constraints ?? []).filter(
            (c) => c.strength === "hard",
          ),
        ]
          .map((c) => c.value)
          .filter((value, index, all) => all.indexOf(value) === index)
          .join(", ") || "No hard restrictions saved"}
        {currentPreferences ? " (changes pending)" : ""}. Edit in Menu and
        preferences.
      </p>
      <div className="actions">
        {chat.id && (
          <ConfirmDialog
            trigger="Delete conversation"
            title="Delete this conversation?"
            busy={chat.busy || chat.loading}
            onConfirm={async () => {
              if (await chat.deleteConversation()) resetControls();
            }}
          >
            This removes its history, preferences and unshared uploads. A new
            conversation keeps this one available at its URL.
          </ConfirmDialog>
        )}
      </div>
      {chat.loading && <p role="status">Loading saved conversation…</p>}
      {chat.error && (
        <p className="notice error" role="alert">
          {chat.error}
        </p>
      )}
      {chat.id && !chat.busy && (
        <Button
          variant="secondary"
          onClick={() => {
            void chat.recover();
          }}
          disabled={chat.loading}
        >
          Load saved history
        </Button>
      )}
      <div className="meal-layout">
        <div className="meal-main">
          <StageProgress events={chat.events} busy={chat.busy} />
          {chat.history?.messages.length || chat.events.length > 0 ? (
            <Button
              variant="secondary"
              onClick={() => {
                latest.current?.scrollIntoView({ block: "center" });
                latest.current?.focus();
              }}
            >
              Jump to latest response
            </Button>
          ) : null}
          <ConversationHistory history={chat.history} events={chat.events} />
          <div
            ref={latest}
            role="region"
            tabIndex={-1}
            aria-label="Latest response"
          />
          <form
            className="composer stack"
            onSubmit={(e) => {
              e.preventDefault();
              if (currentAttachment.blocked) return;
              void chat
                .send(categories, currentPreferences, currentAttachment.id)
                .then((accepted) => {
                  if (accepted) {
                    setPending(undefined);
                    setAttachment({ blocked: false });
                    setAttachmentKey((key) => key + 1);
                  }
                });
            }}
          >
            <fieldset
              className="category-choice"
              disabled={chat.busy || chat.loading}
            >
              <legend>Find a meal</legend>
              {["Eat out", "Cook", "Both"].map((label) => (
                <label key={label}>
                  <input
                    name="category"
                    type="radio"
                    checked={category === label}
                    onChange={() => setCategory(label)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <label className="sr-only" htmlFor="message">
              Message
            </label>
            <textarea
              id="message"
              rows={2}
              maxLength={2000}
              value={chat.draft}
              disabled={chat.busy || chat.loading}
              onChange={(e) => chat.setDraft(e.target.value)}
              placeholder="Tell us what you feel like eating…"
            />
            <ImageAttachment
              initialMediaId={chat.resume?.media_id ?? undefined}
              key={`${attachmentKey}:${chat.resume?.client_request_id ?? "draft"}`}
              disabled={chat.busy || chat.loading}
              onChange={(id, blocked) => setAttachment({ id, blocked })}
            />

            <div className="actions">
              <Button
                type="submit"
                disabled={
                  chat.busy ||
                  chat.loading ||
                  chat.recoveryNeeded ||
                  currentAttachment.blocked ||
                  !chat.draft.trim()
                }
              >
                Send
              </Button>
              {chat.busy && (
                <Button type="button" variant="secondary" onClick={chat.stop}>
                  Stop
                </Button>
              )}
            </div>
          </form>
          <div className="actions examples">
            {[
              "Find Italian restaurants in San Francisco",
              "Help me choose a recipe with chickpeas",
            ].map((example) => (
              <Button
                variant="secondary"
                key={example}
                disabled={chat.busy}
                onClick={() => chat.setDraft(example)}
              >
                {example}
              </Button>
            ))}
          </div>

          {!chat.id && !chat.loading && <RecipeDiscovery />}
        </div>
      </div>
    </PageShell>
  );
}
