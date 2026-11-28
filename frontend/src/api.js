export function apiFetch(input, init = {}) {
  const headers = new Headers(init.headers || {});
  if (!headers.has("X-Requested-With")) {
    headers.set("X-Requested-With", "XMLHttpRequest");
  }
  return fetch(input, {
    credentials: "include",
    ...init,
    headers,
  });
}
