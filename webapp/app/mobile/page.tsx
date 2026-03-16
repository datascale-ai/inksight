import { cookies } from "next/headers";
import { MobileAppShowcase } from "@/components/mobile/mobile-app-showcase";
import { normalizeLocale } from "@/lib/i18n";

export default async function MobilePage() {
  const locale = normalizeLocale((await cookies()).get("ink_locale")?.value);

  return <MobileAppShowcase locale={locale} />;
}
