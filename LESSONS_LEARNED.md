# Lessons learned

## Gmail `list_messages` must not serialize per-row `get` calls

**Symptom:** Long silence (often **30s+**) after the “Previously kept” list before any new candidate appeared—much larger than “a few messages × body prefetch.”

**Cause:** `users.messages.list` only returns IDs. The implementation loaded each row with **two** sequential `users.messages.get` calls (`metadata` + `minimal`). With `maxResults=50`, that is **up to 100 back-to-back HTTP round trips** before the UI could show candidates. Parallel body prefetch for the walkthrough runs **after** this phase, so it could not hide the delay.

**Fix:** Fan out row fetches with a **thread pool** (capped workers, **thread-local** `googleapiclient.discovery.build`—shared service objects are not thread-safe). Keep a **`max_workers == 1`** path for tiny scans and test mocks.

**Takeaway:** Count **API calls × latency**, not just “number of emails shown.” Any O(n) sequential `get` after `list` deserves parallelization or batching when n can be tens.
