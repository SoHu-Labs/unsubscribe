# Spark deep-link — device check (R5 / F2)

Readdle Spark opens messages via **`readdle-spark://openmessage?messageId=<url-encoded RFC822 Message-ID>`**. The digest builds these URLs in **`src/email_digest/spark_link.py`**; CI locks URL encoding in **`tests/test_spark_link.py`** (Slice **D**).

This page is for **manual** verification on a Mac or iOS device where Spark is installed. No automated test replaces a real tap.

## Quick check (copy-paste)

1. From the repo (any machine with the package installed):

   ```bash
   python -m email_digest digest spark-check
   ```

   Optional: use a Message-ID you know exists in **your** Spark mailbox:

   ```bash
   python -m email_digest digest spark-check --message-id '<your-id@host>'
   ```

2. Copy the single line of stdout (starts with **`readdle-spark://`**).

3. On the device: paste into Safari address bar (macOS/iOS) or open from a notes app that treats the line as a link.

4. **Pass:** Spark foregrounds and shows a message (or a sensible Spark error if the id is not in the mailbox — the important part is that Spark **handles** the scheme and query shape).

5. **Fail / regression:** Spark does nothing, another app intercepts, or the URL is mangled (spaces, double encoding). Then:

   - Capture Spark version + OS version.
   - Note whether the id was wrapped in angle brackets in Gmail vs in the URL.
   - Open an issue or patch **`spark_link.py`** and extend **`tests/test_spark_link.py`** so CI matches Readdle’s current contract.

## What not to treat as failure

- **Unknown message:** A synthetic **`@example.com`** id will not open a real message; you are validating **scheme + encoding**, not mailbox membership.
- **Wrong message:** If Spark opens *a* message but not the one you expected, compare the **exact** RFC822 **`Message-ID`** header from Gmail (`digest candidates` JSON includes **`rfc_message_id`**) with the **`messageId=`** query parameter after decode.

## Related

- **`README.md`** — credentials / Spark note.
- **`docs/IMPLEMENTATION_PLAN_EMAIL_SUMMARIES.md`** — **Slice M4**, **Slice D**, **Remaining scope → R5**.
