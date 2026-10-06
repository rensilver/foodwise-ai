"use client";
import { PageShell } from "../../components/layout/page-shell";
import type { Schema } from "../../lib/api/client";
import { Button } from "../../components/ui/button";
import { ConfirmDialog } from "../../components/ui/confirm-dialog";
import { CatalogFacts } from "../recommendations/catalog-presentation";
import { CatalogEditor } from "./catalog-editor";
import { useAdminCatalog } from "./use-admin-catalog";
export function AdminWorkspace() {
  const {
    session,
    password,
    setPassword,
    category,
    draft,
    setDraft,
    record,
    latest,
    description,
    setDescription,
    entries,
    query,
    setQuery,
    busy,
    error,
    message,
    perform,
    loadEntries,
    login,
    logout,
    select,
    preview,
    save,
    remove,
    newEntry,
    changeCategory,
    adoptLatest,
  } = useAdminCatalog();
  return (
    <PageShell active="admin">
      <h1>Catalog administration</h1>
      <p>
        Maintain the local teaching catalog. Administrator access is separate
        from your conversation.
      </p>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {!session ? (
        <form
          className="stack composer"
          onSubmit={(e) => {
            e.preventDefault();
            void login();
          }}
        >
          <label>
            Administrator password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={busy}
            />
          </label>
          <Button disabled={busy || !password}>Sign in</Button>
        </form>
      ) : (
        <div className="actions">
          <p className="note">
            Signed in until{" "}
            <time dateTime={session.expires_at}>{session.expires_at}</time>.
          </p>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => {
              void logout();
            }}
          >
            Sign out
          </Button>
        </div>
      )}
      <section className="stack">
        <h2>{record ? `Edit ${record.data.name}` : "Create an entry"}</h2>
        <label>
          Entry category
          <select
            value={category}
            disabled={busy || !!record}
            onChange={(e) => {
              changeCategory(e.target.value as Schema["Category"]);
            }}
          >
            <option value="restaurant">Restaurant</option>
            <option value="recipe">Recipe</option>
          </select>
        </label>
        <div className="actions">
          <Button
            variant="secondary"
            disabled={busy || !session}
            onClick={() => {
              newEntry();
            }}
          >
            New entry
          </Button>
        </div>
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            void perform(() => loadEntries());
          }}
        >
          <label>
            Find entry by name
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={200}
            />
          </label>
          <Button variant="secondary" disabled={busy || !session}>
            Find entries
          </Button>
        </form>
        {entries.length > 0 && (
          <label>
            Existing entry
            <select
              value={record?.data.id ?? ""}
              disabled={busy || !session}
              onChange={(e) => {
                if (e.target.value) void select(e.target.value);
              }}
            >
              <option value="">Select an entry to edit</option>
              {entries.map((entry) => (
                <option key={entry.data.id} value={entry.data.id}>
                  {entry.data.name} (v{entry.version})
                </option>
              ))}
            </select>
          </label>
        )}
        <p className="note">
          Search by name to narrow the list (up to 100 entries). All entries are
          available through catalog browsing.
        </p>
        <details>
          <summary>Extract fields from a description</summary>
          <label>
            Unstructured description
            <textarea
              rows={4}
              maxLength={65536}
              value={description}
              disabled={busy || !session}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <Button
            variant="secondary"
            disabled={busy || !session || !description.trim()}
            onClick={() => {
              void preview();
            }}
          >
            Preview fields
          </Button>
          <p className="note">
            Preview does not save. Existing unsaved form fields are replaced
            when you request a new preview.
          </p>
        </details>
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <CatalogEditor
            category={category}
            draft={draft}
            onChange={setDraft}
            disabled={busy || !session}
          />
          <Button
            disabled={busy || !session || !!latest || !draft.name?.trim()}
          >
            {record
              ? "Save changes"
              : category === "restaurant"
                ? "Create restaurant"
                : "Create recipe"}
          </Button>
        </form>
        {latest && (
          <section className="notice stack">
            <h3>
              Latest record: {latest.data.name}, version {latest.version}
            </h3>
            <CatalogFacts category={category} data={latest.data} full />
            <div className="actions">
              <Button
                variant="secondary"
                disabled={!session || busy}
                onClick={() => {
                  adoptLatest(false);
                }}
              >
                Keep my draft with latest version
              </Button>
              <Button
                variant="secondary"
                disabled={!session || busy}
                onClick={() => {
                  adoptLatest(true);
                }}
              >
                Load latest record and discard my draft
              </Button>
            </div>
          </section>
        )}
        {record && (
          <ConfirmDialog
            trigger={`Delete ${record.data.name}`}
            title={`Delete ${record.data.name}?`}
            busy={busy || !session}
            onConfirm={remove}
          >
            This deletes the entry and its searchable documents and vectors.{" "}
            {category === "restaurant"
              ? "Linked synthetic reviews and their retrieval content are also deleted. "
              : ""}
            Unreferenced catalog images are queued for cleanup; raw provenance
            is retained.
          </ConfirmDialog>
        )}
      </section>
    </PageShell>
  );
}
