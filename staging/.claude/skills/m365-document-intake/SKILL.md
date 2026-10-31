---
name: m365-document-intake
description: Bring a document from SharePoint, OneDrive, Outlook or Teams into the repository so it can become hashed evidence for a verdict. Use whenever a contract, quote, drawing, bank letter, packing list or site report lives in Microsoft 365.
---

# Microsoft 365 Document Intake | استيراد المستندات من Microsoft 365

## Why
The engine can only hash files inside this repository. A verdict that cites a SharePoint link proves nothing,
because the file behind the link can change. Every document an agent reviews must first be copied into the repo.

## Procedure
1. Find the file with the official Microsoft 365 connector (claude.ai): `sharepoint_search`,
   `sharepoint_folder_search`, `outlook_email_search` (attachments), `chat_message_search` (Teams), then
   `read_resource` to fetch the content.
2. File it by type and date:
   | Type | Destination |
   |---|---|
   | Contracts, amendments, offers | `contracts/<counterparty>/<YYYYMMDD>_<name>.<ext>` |
   | Specs, drawings, datasheets | `specs/<topic>/<YYYYMMDD>_<name>.<ext>` |
   | Packing lists, invoices, receipts | `specs/shipments/<shipment>_{packing,invoice,received}.csv` |
   | Bank letters, SWIFT copies | `finance/<YYYYMMDD>_<name>.<ext>` |
   | Site reports, photos | `site/<YYYYMMDD>_<name>.<ext>` |
3. Write a sidecar `<file>.source.md` with: original location (site, library, path or message id), author,
   last modified time from Microsoft 365, who imported it, today's date. Never edit the imported file. Corrections
   create a new dated file.
4. If the content was converted (PDF to text, Excel to CSV), keep the original too and say so in the sidecar.
5. Data typed by a person or pulled from a chat is unverified until a named human confirms it. Put `[[UNVERIFIED]]`
   as the first line of any CSV or text you assembled yourself. The engine will refuse decisions on it until a human
   removes the marker.
6. Commit the import before running the review, so the evidence hash is anchored in git history.

## Never
- Never cite a URL as evidence.
- Never paste vendor bank details from email into any payment document without a human call back check.
