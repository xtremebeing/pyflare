/**
 * Validates API key from request header
 */
export function validateApiKey(
  apiKey: string | null | undefined,
  env: Env,
): boolean {
  if (!apiKey) {
    return false;
  }

  // Simple API key validation
  // In production, you might want to use KV or D1 for multiple keys
  return apiKey === env.API_KEY;
}
