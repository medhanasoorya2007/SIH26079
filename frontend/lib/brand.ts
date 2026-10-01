/** Product name shown in the UI. The API and exported results still use the internal
 * method key "BustGuard"; always pass method names through displayName() before showing them. */
export const BRAND = "Predicta";
export const MODEL_KEY = "BustGuard";

export const displayName = (method: string) => (method === MODEL_KEY ? BRAND : method);
