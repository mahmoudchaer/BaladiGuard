import { LegalDocumentPage } from '@/pages/LegalDocumentPage';

export function PrivacyPage() {
  return <LegalDocumentPage documentId="privacy" titleKey="privacy.title" showPublicScope />;
}

export function TermsPage() {
  return <LegalDocumentPage documentId="terms" titleKey="legal.termsTitle" />;
}

export function AcceptableUsePage() {
  return <LegalDocumentPage documentId="acceptable-use" titleKey="legal.acceptableUseTitle" />;
}
