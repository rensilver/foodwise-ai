"use client";
import { useState } from "react";
import { Button } from "../../components/ui/button";
export function MealWorkspace() {
  const [draft, setDraft] = useState("");
  return <main id="main" className="workspace"><h1>What sounds good?</h1><p className="note">Synthetic teaching catalog</p><p>Choose a place to eat or something to cook. Explore the sources behind each suggestion.</p><fieldset className="category-choice"><legend>Find a meal</legend>{["Eat out", "Cook", "Both"].map((label) => <label key={label}><input name="category" type="radio" defaultChecked={label === "Both"} />{label}</label>)}</fieldset><div className="actions">{["Find Italian restaurants in San Francisco", "Help me choose a recipe with chickpeas"].map((example) => <Button variant="secondary" key={example} onClick={() => setDraft(example)}>{example}</Button>)}</div><form className="composer stack" onSubmit={(event) => event.preventDefault()}><label htmlFor="message">Message</label><textarea id="message" rows={3} maxLength={2000} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Tell us what you feel like eating…" /><Button type="submit" disabled={!draft.trim()}>Send</Button></form></main>;
}
