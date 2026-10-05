import type { Schema, StreamEvent } from "../../lib/api/client";
import { Recommendations } from "../recommendations/recommendations";
export function ConversationHistory({
  history,
  events,
}: {
  history?: Schema["HistoryResponse"];
  events: StreamEvent[];
}) {
  const currentFinal = events.filter((e) =>
    ["clarification", "recommendations", "error"].includes(e.event),
  );
  return (
    <section aria-label="Conversation history">
      {history?.messages.map((message) => (
        <div key={message.id}>
          {message.role === "user" ? (
            <p className="message">
              <strong>You</strong>
              <br />
              {message.content}
            </p>
          ) : (
            <Response event={message.payload as StreamEvent | undefined} />
          )}
        </div>
      ))}
      {currentFinal
        .filter(
          (event) =>
            !history?.messages.some(
              (m) => m.run_id === event.run_id && m.role === "assistant",
            ),
        )
        .map((event) => (
          <Response key={event.run_id} event={event} />
        ))}
    </section>
  );
}
function Response({ event }: { event?: StreamEvent }) {
  if (!event) return null;
  if (event.event === "clarification")
    return <p className="notice">{event.question}</p>;
  if (event.event === "error")
    return (
      <p className="notice error" role="alert">
        The request could not be completed ({event.code}). Edit your request and
        send when ready.
      </p>
    );
  if (event.event === "recommendations")
    return <Recommendations event={event} />;
  return null;
}
