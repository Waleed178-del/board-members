# حزمة قرار مجلس الإدارة | Board Decision Packet

| البند / Field | القيمة / Value |
|---|---|
| المرجع / Packet ID | `<YYYYMMDD>_<gate>_<subject>` |
| البوابة / Gate | `G?` اسم البوابة / gate name |
| الموضوع / Subject | `<subject_id>` |
| التاريخ / Date | YYYY-MM-DD |
| رأس السلسلة / Chain head | `<first 12 chars from status>` |
| جودة البيانات / Data quality | VERIFIED / UNVERIFIED_INPUTS |

## 1. الحقيقة الصعبة | Hard Truth

> One to three sentences. The unavoidable fact, trade off or hidden cost. Arabic then English.

## 2. القرار المطلوب | Decision Required

- **القرار / Decision**: what exactly the board approves or rejects.
- **مفتاح الموافقة / Approval key**: `<key>` · النصاب / quorum `N` · الأدوار الإلزامية / required roles `...`
- **الموعد النهائي / Deadline**: date and the cost of each day of delay.

## 3. أحكام الوكلاء | Agent Verdicts

| الوكيل / Agent | الحكم / Status | جودة البيانات | أهم النتائج / Key findings (codes) | الملف / Verdict file |
|---|---|---|---|---|
| tech-spec-auditor | | | | |
| legal-counsel | | | | |
| fin-acct-controller | | | | |
| ops-logistics-coord | | | | |
| hr-planner | | | | |

### الفيتو النشط | Active Vetoes
List every CRITICAL finding: code, detail, file:line, exact fix.

### التعارضات بين الأقسام | Cross Department Conflicts
Where two agents disagree, state both positions. Do not resolve by averaging.

## 4. مخاطر المسارين | Cross Track Risk (Civil A vs Equipment B)

- أثر على المسار الحرج / Critical path effect: days.
- التعرض المالي / Financial exposure: amount + currency (demurrage, idle experts, idle crews, FX).

## 5. الأثر المالي والمحاسبي | Financial and Accounting Effect

| التاريخ | النوع | التصنيف | مدين | دائن | المبلغ | العملة | سعر الصرف |
|---|---|---|---|---|---|---|---|

## 6. أوراق التفاوض | Negotiation Leverage
Redlines to request from the counterparty, ordered CRITICAL first (English).

## 7. أوامر التنفيذ للأعضاء | Human Commands (run in your own terminal)

```bash
python3 engine/board.py approve <key> --member <id> --decision APPROVE --evidence packets/<this file>.md
```

```bash
python3 engine/board.py attest <flag> --member <id> --evidence <signed document>
```

## 8. حالة البوابة بعد هذه الحزمة | Gate status after this packet
Paste `python3 engine/board.py check-gate <G>` output.
