# Optional off-site probe (only when the runtime has web search)

Corroboration and entity ambiguity live off site, so scripts cannot fully test
them. If and only if the agent runtime provides a web search tool, run this
probe after the script modules. If not, skip silently; the report is complete
without it.

## Procedure

1. Search the exact brand name alone, and the brand name plus its category
   (for example "Acme" and "Acme bakery Portland").
2. Record what the top results are about:
   - If most results for the bare name are a different entity (another
     company, a dictionary word, a celebrity), the brand has a name collision.
     Add finding `F-OFFSITE-001`, severity medium, evidence listing what the
     name currently resolves to, action: always pair the name with a
     distinguishing qualifier in titles and schema, obtain a Wikidata entry,
     and expand sameAs coverage.
3. Compare the site's self-description with how the top independent sources
   describe the brand (category, location, offerings):
   - If they materially disagree (old address, discontinued product, renamed
     company), add finding `F-OFFSITE-002`, severity high, evidence quoting
     both sides, action: update the authoritative external listings (business
     profiles, directories, Wikipedia if eligible) to match the site, since
     assistants trust cross-source agreement over any single page.
4. Check whether the brand has any independent coverage at all (news, reviews,
   directories):
   - If the only search results are the brand's own properties, add
     `F-OFFSITE-003`, severity medium: a claim that exists in one place is
     fragile. Action: pursue listings and coverage in the venues assistants
     actually quote for the category (review platforms, industry directories,
     local press).

## Rules

- Read-only research. Never post, submit, or edit anything anywhere.
- Maximum 4 searches; this is a probe, not an investigation.
- Findings from this probe must quote their sources in the evidence field.
