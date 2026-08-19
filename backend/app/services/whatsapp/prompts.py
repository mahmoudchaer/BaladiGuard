"""Deterministic outbound prompts for WhatsApp intake (issue #296)."""

from __future__ import annotations

from app.schemas.whatsapp_conversation import WhatsAppConversation
from app.services.whatsapp.states import ConversationState


def prompt_for(state: ConversationState, conversation: WhatsAppConversation) -> str:
    lang = conversation.language
    if state == "welcome":
        return _t(
            lang,
            en=(
                "Welcome to BaladiGuard municipal reporting on WhatsApp.\n"
                "We collect a description, location, and one photo to create an official report.\n"
                "Your WhatsApp number is used only for account matching "
                "(no app login code is sent).\n"
                "Commands anytime: help | back | cancel | restart\n"
                "Reply YES to continue."
            ),
            ar=(
                "أهلاً بك في بلاادي غارد عبر واتساب.\n"
                "نجمع وصفاً وموقعاً وصورة واحدة لإنشاء بلاغ رسمي.\n"
                "يُستخدم رقم واتساب للمطابقة فقط (بدون رمز دخول).\n"
                "الأوامر: مساعدة | رجوع | إلغاء | إعادة\n"
                "أرسل YES للمتابعة."
            ),
        )
    if state == "language":
        return _t(
            lang,
            en="Choose language: reply EN or AR.",
            ar="اختر اللغة: أرسل EN أو AR.",
        )
    if state == "description":
        return _t(
            lang,
            en="Describe the problem in your own words (at least a short sentence).",
            ar="صف المشكلة بجملة قصيرة على الأقل.",
        )
    if state == "location":
        return _t(
            lang,
            en=(
                "Share a WhatsApp location pin, or type an address we can validate.\n"
                "If we suggest a resolved address, reply YES to confirm or send a new pin/address."
            ),
            ar=(
                "أرسل موقع واتساب أو اكتب عنواناً للتحقق.\n"
                "إذا اقترحنا عنواناً، أرسل YES للتأكيد أو أرسل موقعاً جديداً."
            ),
        )
    if state == "photo":
        return _t(
            lang,
            en="Send one report photo (JPEG/PNG/WebP, max 5MB).",
            ar="أرسل صورة واحدة للبلاغ (JPEG/PNG/WebP بحد أقصى 5MB).",
        )
    if state == "optional_name":
        return _t(
            lang,
            en="Optional: send your full name, or reply SKIP to continue without a name.",
            ar="اختياري: أرسل اسمك الكامل، أو SKIP للمتابعة بدون اسم.",
        )
    if state == "review":
        snap = conversation.collected_snapshot()
        return _t(
            lang,
            en=(
                "Review your report:\n"
                f"- Description: {snap['description']}\n"
                f"- Location: {snap['addressText']}\n"
                f"- Photo: {'attached' if snap['hasPhoto'] else 'missing'}\n"
                f"- Name: {snap['optionalName'] or '(skipped)'}\n"
                "Reply CONFIRM to submit, or BACK to edit."
            ),
            ar=(
                "مراجعة البلاغ:\n"
                f"- الوصف: {snap['description']}\n"
                f"- الموقع: {snap['addressText']}\n"
                f"- الصورة: {'مرفقة' if snap['hasPhoto'] else 'غير موجودة'}\n"
                f"- الاسم: {snap['optionalName'] or '(تم التخطي)'}\n"
                "أرسل CONFIRM للإرسال أو BACK للتعديل."
            ),
        )
    if state == "submitting":
        return _t(lang, en="Submitting your report…", ar="جارٍ إرسال بلاغك…")
    if state == "completed":
        return success_receipt(conversation)
    if state == "cancelled":
        return _t(
            lang,
            en="Report cancelled. Send any message to start again.",
            ar="تم إلغاء البلاغ. أرسل أي رسالة للبدء من جديد.",
        )
    if state == "expired":
        return _t(
            lang,
            en="This conversation expired. Send any message to start again.",
            ar="انتهت صلاحية المحادثة. أرسل أي رسالة للبدء من جديد.",
        )
    return help_text(lang)


def help_text(lang: str) -> str:
    return _t(
        lang,
        en=(
            "BaladiGuard WhatsApp creates municipal reports only.\n"
            "Commands: help | back | cancel | restart\n"
            "Follow the current step prompt."
        ),
        ar=(
            "واتساب بلاادي غارد لإنشاء بلاغات بلدية فقط.\n"
            "الأوامر: مساعدة | رجوع | إلغاء | إعادة\n"
            "اتبع تعليمات الخطوة الحالية."
        ),
    )


def success_receipt(conversation: WhatsAppConversation, *, deep_link: str | None = None) -> str:
    lang = conversation.language
    link_line = f"\nTrack: {deep_link}" if deep_link else ""
    return _t(
        lang,
        en=(
            f"Report submitted.\n"
            f"Ticket: {conversation.ticket_number}\n"
            f"Status: SUBMITTED{link_line}\n"
            "Do not share internal IDs. Use the tracking link or your citizen app history."
        ),
        ar=(
            f"تم إرسال البلاغ.\n"
            f"الرقم: {conversation.ticket_number}\n"
            f"الحالة: SUBMITTED{link_line}\n"
            "لا تشارك المعرفات الداخلية. استخدم رابط التتبع أو سجل التطبيق."
        ),
    )


def inactive_account_message(lang: str = "en") -> str:
    return _t(
        lang,
        en=(
            "Unable to continue with this WhatsApp number. "
            "Contact municipal support if you need help."
        ),
        ar="تعذر المتابعة بهذا الرقم. تواصل مع دعم البلدية عند الحاجة.",
    )


def _t(lang: str, *, en: str, ar: str) -> str:
    return ar if lang == "ar" else en
