import { LegalDocumentScreen } from '@/features/legal/LegalDocumentScreen';

export default function PrivacyNoticeScreen() {
  return (
    <LegalDocumentScreen
      documentId="privacy"
      titleKey="privacy.title"
      showHubLinks
      showScopeNotice
    />
  );
}
