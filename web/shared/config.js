let cachedConfig;

export async function getConfig() {
  if (cachedConfig) return cachedConfig;
  const response = await fetch("/config.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Application configuration is unavailable.");
  const config = await response.json();
  for (const key of ["region", "userPoolId", "clientId", "cognitoDomain", "apiBase", "rawBucketUrl"]) {
    if (typeof config[key] !== "string" || !config[key]) {
      throw new Error(`Application configuration is missing ${key}.`);
    }
  }
  cachedConfig = config;
  return config;
}
