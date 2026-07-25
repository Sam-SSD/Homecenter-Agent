/**
 * Base URL del backend HTTP (api/servidor.py). No existía ninguna convención
 * de URL en el repo: Expo inyecta EXPO_PUBLIC_* en build time, así que basta
 * un .env en mobile/ (ver .env.example) para apuntar a otra máquina.
 *
 * Default: localhost:8000, que es donde corre `uvicorn api.servidor:app`
 * arrancado desde la raíz del repo, con la app en `expo start --web`.
 */
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';
