# Method and design choices

## Why account timelines matter

A deal record is often an incomplete unit of analysis. Conversations may be associated with a parent company, another deal, or a contact. Put related calls in order at the account level before scoring behavior. Include unrecorded calls in the sequence. Do not claim an objection was absent from an entire sales cycle when the relevant meeting was not recorded.

The CSV interface makes the choice of CRM explicit. An adapter should map its own associations into `account,id,date,title,internal,external,transcript,recorded,source`. It should store any CRM credentials outside the repo and log what was skipped.

## Evidence before synthesis

1. Preserve original recordings and raw transcripts separately. Review automated transcription and speaker labels.
2. Measure only what the transcript format actually supports. Word share is a proxy, not speaking time; punctuation is a rough question count.
3. Write specific observations with verbatim quotes. Separate observed facts, inferred motivation, and open questions.
4. Verify each quote against one speaker turn. A matching quote supports only the words quoted, not every interpretation attached to it.
5. Invite the account owner to correct missing context. Record disagreement rather than smoothing it away.
6. When aggregating across accounts, count accounts as well as calls. One highly active account should not masquerade as a market trend.
7. Select a small coaching behavior, practice it, then compare later calls. Do not equate an improved metric with a won deal.

## Review questions

- What prompted the customer to engage now? How did they find us?
- What problem, cost, timeline, and decision process did they state in their own words?
- Which stakeholders were present or missing? What changed between calls?
- Did the team answer the customer's actual question? Did it demonstrate value relevant to the stated problem?
- What objections or alternative solutions came up? What evidence supports the handling assessment?
- Was a next step mutual, dated, and owned?
- What went well? What one behavior would be worth practicing next?

These can be mapped to your team's framework. If you use ACE, SPICED, BANT, or a mutual action plan, credit their respective creators and define your scoring rubric before analysis. Avoid scoring a topic as absent when the recording is incomplete.

## Extension points

- **CRM adapter:** inventory account, deal, company, contact, and meeting associations. Export CSV with source IDs. Warn about ambiguous account mappings.
- **Demand and competitor lens:** capture only explicit customer statements about discovery source, alternatives, and language. Have a reviewer challenge broad claims.
- **Training kit:** create drills from repeated, verified patterns and link back to call examples. Set a follow up date and owner.
- **Model workflow:** validate JSON shape, quote locations, redaction, prompt version, provider, and human reviewer. Do not treat an agent generated score as ground truth.
- **Report access:** reports can contain personal and commercial information. Apply your team's retention and access rules.

