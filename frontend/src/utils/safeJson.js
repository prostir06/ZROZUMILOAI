/**
 * Безпечний парсинг JSON з fetch Response.
 * @param {Response} response - fetch-відповідь
 * @param {*} [fallback=null] - значення при помилці парсингу
 * @returns {Promise<*>}
 */
export async function safeJson(response, fallback = null) {
  try {
    return await response.json();
  } catch {
    return fallback;
  }
}
