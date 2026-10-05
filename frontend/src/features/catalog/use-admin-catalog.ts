"use client";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Schema } from "../../lib/api/client";
import {
  draftFromFields,
  recipeFields,
  restaurantFields,
  type Draft,
} from "./catalog-editor";
export function useAdminCatalog() {
  const [session, setSession] = useState<Schema["LoginResponse"]>();
  const [password, setPassword] = useState("");
  const [category, setCategory] = useState<Schema["Category"]>("restaurant");
  const [draft, setDraft] = useState<Draft>({});
  const [record, setRecord] = useState<Schema["CatalogDetail"]>();
  const [latest, setLatest] = useState<Schema["CatalogDetail"]>();
  const [description, setDescription] = useState("");
  const [entries, setEntries] = useState<Schema["CatalogDetail"][]>([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (!session) return;
    const deadline = Math.max(0, Date.parse(session.expires_at) - Date.now());
    const timer = setTimeout(
      () => {
        setSession(undefined);
        setError(
          "Administrator session expired. Sign in to continue; your draft is preserved.",
        );
      },
      Math.min(deadline, 2_147_483_647),
    );
    return () => clearTimeout(timer);
  }, [session]);
  async function loadEntries(selected = category, search = query) {
    const params = new URLSearchParams({ limit: "100" });
    if (search.trim()) params.set("q", search.trim());
    const page = await api(
      selected === "restaurant" ? "/api/v1/restaurants" : "/api/v1/recipes",
      "get",
      { query: params },
    );
    setEntries(page.items);
  }
  function failure(e: unknown) {
    if (e instanceof ApiError && [401, 403].includes(e.status)) {
      setSession(undefined);
      setError(
        "Administrator session is unavailable. Sign in again; your draft is preserved.",
      );
    } else
      setError(
        e instanceof Error
          ? e.message
          : "The operation failed. Your draft is preserved.",
      );
  }
  const locked = useRef(false);
  async function perform(action: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      failure(e);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  async function login() {
    await perform(async () => {
      const grant = await api("/api/v1/admin/session", "post", {
        body: { password },
      });
      setSession(grant);
      setPassword("");
      setMessage("Signed in.");
      await loadEntries();
    });
    setPassword("");
  }
  async function logout() {
    if (!session) return;
    await perform(async () => {
      await api("/api/v1/admin/session", "delete", {
        csrf: session.csrf_token,
      });
      setSession(undefined);
      setMessage("Signed out.");
    });
  }
  async function select(id: string) {
    await perform(async () => {
      const detail = await api(
        category === "restaurant"
          ? "/api/v1/restaurants/{entity_id}"
          : "/api/v1/recipes/{entity_id}",
        "get",
        { params: { entity_id: id } },
      );
      setRecord(detail);
      setDraft(draftFromFields(detail.data));
      setLatest(undefined);
      setDescription("");
    });
  }
  async function preview() {
    if (!session) return;
    await perform(async () => {
      const result = await api("/api/v1/admin/extractions/preview", "post", {
        csrf: session.csrf_token,
        body: { category, text: description },
      });
      if (result.status !== "validated" || !result.fields)
        throw new Error(
          "Preview could not be validated. Edit the description or enter fields manually.",
        );
      setDraft(draftFromFields(result.fields));
      setMessage(
        "Preview ready. Review the fields and use the separate save action to commit.",
      );
    });
  }
  async function save() {
    if (!session) return;
    await perform(async () => {
      try {
        let saved: Schema["CatalogSnapshot"];
        if (category === "restaurant")
          saved = record
            ? await api("/api/v1/admin/restaurants/{entity_id}", "patch", {
                params: { entity_id: record.data.id },
                csrf: session.csrf_token,
                body: {
                  expected_version: record.version,
                  fields: restaurantFields(draft),
                },
              })
            : await api("/api/v1/admin/restaurants", "post", {
                csrf: session.csrf_token,
                body: { fields: restaurantFields(draft) },
              });
        else
          saved = record
            ? await api("/api/v1/admin/recipes/{entity_id}", "patch", {
                params: { entity_id: record.data.id },
                csrf: session.csrf_token,
                body: {
                  expected_version: record.version,
                  fields: recipeFields(draft),
                },
              })
            : await api("/api/v1/admin/recipes", "post", {
                csrf: session.csrf_token,
                body: { fields: recipeFields(draft) },
              });
        setRecord({ ...saved, citations: [], images: [], synthetic: true });
        setLatest(undefined);
        setDraft(draftFromFields(saved.data));
        setMessage(`Saved ${saved.data.name}, version ${saved.version}.`);
        await loadEntries();
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && record) {
          setError(
            "This entry changed since you loaded it. Your draft is preserved. Review the latest record before saving.",
          );
          const current = await api(
            category === "restaurant"
              ? "/api/v1/restaurants/{entity_id}"
              : "/api/v1/recipes/{entity_id}",
            "get",
            { params: { entity_id: record.data.id } },
          );
          setLatest(current);
          return;
        }
        throw e;
      }
    });
  }
  async function remove() {
    if (!record || !session) return;
    await perform(async () => {
      await api(
        category === "restaurant"
          ? "/api/v1/admin/restaurants/{entity_id}"
          : "/api/v1/admin/recipes/{entity_id}",
        "delete",
        {
          params: { entity_id: record.data.id },
          csrf: session.csrf_token,
          body: {
            expected_version: record.version,
            confirm_id: record.data.id,
          },
        },
      );
      setMessage(`Deleted ${record.data.name}.`);
      setRecord(undefined);
      setLatest(undefined);
      setDraft({});
      await loadEntries();
    });
  }
  function newEntry() {
    setRecord(undefined);
    setLatest(undefined);
    setDraft({});
    setDescription("");
    setError("");
    setMessage("");
  }
  function changeCategory(selected: Schema["Category"]) {
    setCategory(selected);
    setDraft({});
    setLatest(undefined);
    if (session) void perform(() => loadEntries(selected));
  }
  function adoptLatest(discardDraft: boolean) {
    if (!latest) return;
    setRecord(latest);
    if (discardDraft) setDraft(draftFromFields(latest.data));
    setLatest(undefined);
    setError("");
    setMessage(
      discardDraft
        ? ""
        : "Latest version selected. Your draft is unchanged. Review every field before saving.",
    );
  }
  return {
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
  };
}
