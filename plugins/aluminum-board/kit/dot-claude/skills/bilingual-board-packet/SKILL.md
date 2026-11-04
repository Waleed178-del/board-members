---
name: bilingual-board-packet
description: Write board decision packets, verdict summaries and Telegram or email texts in Arabic first and English second, in the board's direct style. Use whenever writing packets/*.md, summary_ar fields, or any outbound draft.
---

# Bilingual Board Writing | الكتابة الثنائية لمجلس الإدارة

## Structure
Use `templates/decision_packet.md`. Every section: Arabic paragraph, then English paragraph. Tables carry both
labels in the header row (`القرار / Decision`).

## Arabic style
- Modern Standard Arabic, short sentences, active voice. One idea per sentence.
- Start with the decision or the block, then the reason, then the number.
  Good: "البوابة G1 مغلقة. السبب: بيانات العلامات الكهربائية غير موثقة. المطلوب: توثيق من رئيس الصيانة."
- Keep technical terms in English inside Arabic text when there is no settled Arabic term: L/C, INCOTERMS, PLC, VFD, FAT, SAT.
- Standard terms: الشروط الجزائية (liquidated damages), ضمان حسن التنفيذ (performance bond), ضمان الدفعة المقدمة
  (advance payment guarantee), المحتجزات (retention), الاعتماد المستندي (L/C), مركز التحويل (substation),
  أعمال رأسمالية قيد التنفيذ (CWIP), مصاريف التأسيس (pre operating expenses), الإهلاك (depreciation).

## Numbers and dates
Western digits, ISO dates (2026-11-30), currency code on every amount (USD 1,250,000), percentages with %.

## Hard Truth line
Every packet and every summary opens with one sentence of الحقيقة الصعبة: the unavoidable fact, cost or trade off.
No praise, no softening words ("نأمل", "ربما بشكل بسيط"). Calibrate: say known, inferred, unverified.

## Length limits
- `summary_ar` / `summary_en`: 2 to 4 sentences each.
- Telegram: under 1,500 characters. Link the packet for detail.
- Email: subject line names gate, subject and decision needed: `[G2] equipment_contract: 3 vetoes, board vote needed by 2026-12-05`.
