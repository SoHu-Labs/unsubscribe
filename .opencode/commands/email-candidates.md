---
description: List Gmail candidates matching a topic
---
List Gmail candidates for topic $ARGUMENTS:
!`mamba run -n email-digest python -m email_digest digest candidates $ARGUMENTS --max-results 10`
