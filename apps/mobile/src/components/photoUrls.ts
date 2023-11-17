export function ownedPhotoThumbnail(uri: string, apiBase: string) {
  try {
    const url = new URL(uri);
    const api = new URL(apiBase);
    if (
      (url.protocol === "https:" || url.protocol === "http:") &&
      url.origin === api.origin &&
      url.href === uri &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash &&
      /^\/v1\/media\/[A-Za-z0-9_-]+\/display$/.test(url.pathname)
    ) {
      return `${url.origin}${url.pathname.slice(0, -"/display".length)}/thumbnail`;
    }
  } catch {
    /* External or malformed URLs are left as provided. */
  }
  return null;
}
