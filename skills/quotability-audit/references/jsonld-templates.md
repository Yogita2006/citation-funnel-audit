# JSON-LD starter templates

Copy, fill, and place in a `<script type="application/ld+json">` block.
Validate before shipping: invalid JSON-LD is silently discarded whole.

## Organization (homepage, sitewide)

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "BRAND NAME (one canonical spelling, used everywhere)",
  "url": "https://www.example.com/",
  "logo": "https://www.example.com/logo.png",
  "description": "One plain sentence: what the brand does, for whom, where.",
  "sameAs": [
    "https://www.linkedin.com/company/example",
    "https://www.wikidata.org/wiki/QXXXXX",
    "https://github.com/example"
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "telephone": "+1-555-000-0000",
    "contactType": "customer service",
    "email": "hello@example.com"
  }
}
```

For a physical business use `LocalBusiness` (or its subtype) instead, adding
`address` (PostalAddress), `geo`, `openingHoursSpecification`, `telephone`.

## Product page

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Product name",
  "description": "What it is and what problem it solves, in one sentence.",
  "image": "https://www.example.com/product.jpg",
  "brand": {"@type": "Brand", "name": "BRAND NAME"},
  "offers": {
    "@type": "Offer",
    "price": "49.00",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock",
    "url": "https://www.example.com/product"
  }
}
```

## FAQ page

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "The question exactly as a customer would ask it?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "A direct 2 to 4 sentence answer with a concrete number or fact."
      }
    }
  ]
}
```

## Article or blog post

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Title",
  "datePublished": "2026-01-15",
  "dateModified": "2026-06-02",
  "author": {"@type": "Person", "name": "Full Name", "url": "https://www.example.com/team/full-name"},
  "publisher": {"@type": "Organization", "name": "BRAND NAME"}
}
```

Rules that prevent wasted effort: dates must be true (never freshen a date
without changing content), the visible page must state everything the markup
claims, and `name` in every block must be the one canonical brand string.
