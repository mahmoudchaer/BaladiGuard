import { getApp, getApps, initializeApp } from 'firebase/app';
import {
  type ConfirmationResult,
  getAuth,
  RecaptchaVerifier,
  signInWithPhoneNumber,
} from 'firebase/auth';
import { jsonRequest } from '@/services/api';
import type { CitizenProfile, OtpVerifyOptions } from '@/types/citizen';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const firebasePhoneAuthEnabled =
  import.meta.env.VITE_CITIZEN_OTP_DELIVERY_CHANNEL === 'firebase' &&
  Object.values(firebaseConfig).every((value) => typeof value === 'string' && value.length > 0);

let confirmation: ConfirmationResult | null = null;
let verifier: RecaptchaVerifier | null = null;

function firebaseAuth() {
  if (!firebasePhoneAuthEnabled) throw new Error('Firebase phone authentication is unavailable.');
  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  return getAuth(app);
}

function e164Phone(phone: string, region: string): string {
  const compact = phone.replace(/[\s()-]/g, '');
  if (compact.startsWith('+')) return compact;
  if (region === 'LB') return `+961${compact.replace(/^0/, '')}`;
  return `+${compact}`;
}

export async function startFirebasePhoneOtp(phone: string, region: string): Promise<void> {
  const target = document.getElementById('firebase-recaptcha');
  if (!target) throw new Error('Phone verification is not ready. Refresh and try again.');
  verifier?.clear();
  verifier = new RecaptchaVerifier(firebaseAuth(), target, { size: 'invisible' });
  try {
    confirmation = await signInWithPhoneNumber(firebaseAuth(), e164Phone(phone, region), verifier);
  } catch (error) {
    verifier.clear();
    verifier = null;
    throw error;
  }
}

export async function completeFirebasePhoneOtp(
  challengeId: string,
  code: string,
  purpose: 'LOGIN_OR_SIGNUP' | 'CHANGE_PHONE',
  options: OtpVerifyOptions,
): Promise<CitizenProfile> {
  if (!confirmation) throw new Error('Request a new verification code.');
  const credential = await confirmation.confirm(code);
  const idToken = await credential.user.getIdToken(true);
  confirmation = null;
  verifier?.clear();
  verifier = null;
  return jsonRequest(
    '/citizen/auth/firebase/complete',
    {
      method: 'POST',
      headers: { 'X-Citizen-Session-Mode': 'cookie' },
      body: JSON.stringify({
        challengeId,
        idToken,
        purpose,
        acceptLegal: options.acceptLegal,
        legalLocale: options.legalLocale,
      }),
    },
    'Unable to verify that code.',
  );
}
