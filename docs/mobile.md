The mobile client is a React Native app built with Expo and TypeScript. This document is for developers running or extending the Android client.

# Mobile architecture

`mobile/App.tsx` contains the sign-in flow, bottom-tab navigation and the initial live-data screens. `mobile/src/api.ts` owns typed API calls, access-token refresh and secure token persistence through Expo SecureStore. The app calls the FastAPI backend directly; Mono keys remain server-side.

The app currently includes OTP sign-in, BVN verification for synthetic demo identities, Mono hosted-link initiation, mock demo account linking, refresh/sync, overview, transactions, recurring payments, insights, consent revocation and sign-out. Financial values arrive in integer kobo and are formatted as naira only at the UI edge. The backend defaults to local development OTP and does not send SMS.

## Run on Android

Install Node.js LTS, Android Studio and an Android emulator. From `mobile/`:

```powershell
npm install
npx expo start --android
```

For Expo Go, run the Expo Go app in the emulator. To test the `cashlens://mono/callback` custom scheme, use a native development build instead:

```powershell
npx expo run:android
```

Android emulator requests to the computer use `http://10.0.2.2:8080`. Set `EXPO_PUBLIC_API_BASE_URL` in `mobile/.env` to point to another backend. This value is a public API address, not a secret. Do not put Mono keys or JWT secrets in Expo variables.

The hosted bank-link flow requires a reachable HTTPS backend and a configured Mono webhook. After Mono authorises the account, return to the app and check link status; the backend activates the link from the webhook. The callback scheme requires a development or standalone build and is not guaranteed in Expo Go.

## Related docs

- [API guide](api.md)
- [Mono integration](mono-integration.md)
- [Consent and privacy](consent-and-privacy.md)
- [Known gaps](KNOWN_GAPS.md)
