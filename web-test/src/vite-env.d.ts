/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LOCAL_API_URL?: string;
  readonly VITE_STAGING_API_URL?: string;
  readonly VITE_MOCK_MODE?: string;
  readonly VITE_CONSOLE_ENABLED?: string;
  readonly VITE_DENIED_HOSTS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
