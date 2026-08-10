# Staff assistant backend

`POST /v1/staff-assistant/query` is a read-only, staff-Bearer-protected endpoint.
It deliberately uses no model provider, network call, prompt, or client-supplied ticket
data: every count and ticket reference is derived from persisted tickets after
`staff_can_access_ticket` enforces municipality and department scope.

Supported deterministic intents are high-priority summaries (English, Arabic, French,
and mixed-language terms) and repeated-area summaries. Unsupported or ambiguous questions
return bounded guidance with zero references. Responses contain `asOf`, count, categories,
areas, safe ticket/filter references, and never include contact data, image keys, ticket
descriptions, account/session fields, prompts, or provider output.

Run the regression coverage with:

```bash
cd backend
python -m pytest tests/test_staff_assistant.py -q
```
