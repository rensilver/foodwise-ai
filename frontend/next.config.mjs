const backendVariables = [
  "GROQ_API_KEY", "GROQ_MODEL", "GROQ_VISION_MODEL", "TAVILY_API_KEY",
  "DATABASE_URL", "MCP_SERVER_URL", "MEDIA_ROOT", "ADMIN_PASSWORD_HASH",
];

/** Backend configuration must never enter the frontend process. */
export default function nextConfig() {
  // Next loads dotenv before invoking this function, for both dev and build.
  // Reject unknown public names too: secrets may have arbitrary aliases.
  if (Object.keys(process.env).some((name) => name.startsWith("NEXT_PUBLIC_"))) {
    throw new Error(
      "Remove NEXT_PUBLIC_* variables from the frontend environment and dotenv files. " +
      "foodwise-ai currently needs no public environment settings. " +
      "Keep provider keys, database URLs and administrator hashes in backend configuration.",
    );
  }
  // Client components also render on the server: unprefixed secrets can leak
  // through rendered HTML even when they are absent from browser JavaScript.
  const misplaced = backendVariables.filter((name) => name in process.env);
  if (misplaced.length > 0) {
    throw new Error(
      `Remove backend settings from the frontend environment and dotenv files: ${misplaced.join(", ")}. ` +
      "Keep them in the backend process; see backend/README.md and frontend/README.md.",
    );
  }
  // Never spread process.env or expose backend settings through `env` here.
  return {};
}
