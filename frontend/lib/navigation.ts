/**
 * Resolve the post-login destination from the `next` query parameter.
 *
 * The value is fully attacker-controlled, so it must never be able to leave the
 * origin. Rejecting only a leading `//` is not enough: browsers normalise
 * backslashes to forward slashes, so `/\evil.com` and `/\/evil.com` resolve to
 * the protocol-relative `//evil.com` and turn the login button into an open
 * redirect.
 *
 * Accepted: a single leading `/`, no backslashes, and only characters that are
 * legal in a URL path. Everything else falls back to the dashboard.
 */
export function safeNext(raw: string | null | undefined): string {
  const fallback = "/dashboard";
  if (!raw) return fallback;

  // Must be a single-slash-rooted absolute path. `//host` and `/\host` are out.
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) {
    return fallback;
  }
  // Any backslash anywhere can be normalised into a path separator by the
  // browser, so reject the character rather than trying to normalise it.
  if (raw.includes("\\")) return fallback;

  // Reject control characters (header/URL injection) and anything that could
  // change the scheme or host once the browser parses it.
  if (/[\u0000-\u001f\u007f]/.test(raw)) return fallback;
  if (raw.includes(":")) return fallback;

  return raw;
}