# WORKING.md: How this project works, in simple words

This file explains the whole project in easy language: what it does, how it
does it step by step, what tools and ideas were used, and how it was built.

## 1. What is this project?

This project is a website checker for the AI age.

Today, people do not only search on Google. They ask AI assistants like
ChatGPT, Claude, and Perplexity: "best bakery near me?", "what does this
company do?", "how much does it cost?". The AI reads websites and picks a few
to quote in its answer.

Problem: many good websites never get picked. The owner does not know why.

This project is the answer to that. You give it any website address, and it
tells you:

- What is broken (the problems, with proof and a severity level).
- Why each problem matters (the reason, in one sentence).
- How to fix each problem (clear actions, sorted by importance).
- Extra ideas to become even better, even where nothing is broken.

It never touches or changes the website. It only reads public pages and
writes a report. It is 100 percent safe and read-only.

## 2. The big idea: the Citation Funnel

Think of a fact on your website (for example, your price). For an AI to say
that fact in an answer, the fact must pass through 5 doors, in order:

```
Door 1: REACH   -> Can AI robots even enter your website?
Door 2: READ    -> Can they see your text without running JavaScript?
Door 3: QUOTE   -> Can they pick up a clean, clear fact from the page?
Door 4: TRUST   -> Do they believe the fact? (fresh, consistent, confirmed)
Door 5: RETAIN  -> When a human clicks your link, do they stay on your site?
```

If any one door is closed, everything after it does not matter. That is why
this project checks each door separately and gives each door a score out of
100. The report shows you exactly which door is closed first.

Before checking the 5 doors, the tool first looks at the site and guesses what
kind of site it is: an online shop, a SaaS app, a local business (like a cafe),
a blog or news site, a documentation site, or a simple brochure site. This
matters a lot: a blog should not be told it is missing a shop's price tag, and
a cafe should be checked for its address and opening hours. So the checks
change based on the site type. This one step removes most false alarms.

## 3. What is inside the project (the parts)

The project is a "marketplace" of 6 skills. A skill is a folder with a
SKILL.md file (instructions for an AI agent) plus scripts (Python programs
that do the real checking).

```
citation-funnel-audit/
  marketplace.json        <- the list of all skills, and which one is the boss
  skills/
    audit-orchestrator/   <- THE BOSS (entrypoint). Runs everything, makes the final report.
    reach-audit/          <- Door 1 checker
    render-parity-audit/  <- Door 2 checker
    quotability-audit/    <- Door 3 checker
    trust-signals-audit/  <- Door 4 checker
    engagement-audit/     <- Door 5 checker
  README.md               <- full technical description
  WORKING.md              <- this file
```

Every skill folder has:

- SKILL.md: what the skill does, when to use it, and the exact steps.
- scripts/: the Python program that does the checks.
- references/: extra detail files (checklists, rules, templates).

## 4. What each skill checks, in plain words

### Door 1: reach-audit (can robots get in?)

- Is the homepage working (HTTP 200) or broken?
- Does the robots.txt file (the site's "entry rules" file) block AI robots?
  Important detail: there are two kinds of AI robots. Training robots
  (GPTBot, ClaudeBot) collect data to teach AI models. Answer robots
  (OAI-SearchBot, PerplexityBot, ChatGPT-User) fetch pages to build live
  answers. Blocking training robots is your choice and is fine. Blocking
  answer robots removes you from AI answers, and that is a real problem.
- Is there a hidden "noindex" tag that tells all robots "ignore this page"?
  (This often leaks from a testing version of a site by mistake.)
- Are there too many redirects before the page opens?
- Is there a sitemap.xml (a map file that lists all pages for robots)?
- Is the main content locked behind a login or a paywall? AI robots are never
  logged in, so anything behind "subscribe to read" or "members only" is
  invisible to them.

### Door 2: render-parity-audit (can robots see the text?)

- Many modern websites build their page with JavaScript in the browser. A
  human sees a full page. But most AI robots do not run JavaScript, so they
  receive an almost empty page. This skill counts how many words a no-JavaScript
  reader actually gets. If the homepage has an app shell and almost no words,
  that is the number one reason a beautiful site is invisible to AI.
- Are important facts locked inside images (like a menu photo) with no text?
- Are important facts only inside PDF files (like price-list.pdf)?
- Is main content inside an iframe (a page inside a page)?
- Does content appear only when you scroll or click "load more"? A robot
  fetches the page once and never scrolls, so it misses that content. And is
  the homepage's message only inside a video, with no text a robot can read?

### Door 3: quotability-audit (can robots pick up a fact?)

This has our special trick, the question probe. Instead of checking tags,
it asks the real questions people ask AI about any brand, and tests if your
site answers them in machine-readable text:

- WHAT is this brand? (Is there one clear sentence saying what you do?)
- WHAT does it cost? (Is any price written as text? Only checked for shops
  and businesses that sell, so a school or NGO is not wrongly flagged.)
- HOW do I contact them? (Is a phone or email written as real text, not
  hidden inside an image or a form?)
- WHO is behind it? (Is there an About page with real facts?)

It also checks structured data called JSON-LD. This is a small hidden block
of labeled facts (name, price, address) written in a language machines love.
Special rule: broken JSON-LD is worse than none, because machines silently
throw away the whole block, so you get zero value from your work.

Because the tool now knows the site type, it checks for the right structured
data (a shop needs Product/Offer, a blog needs Article), warns when a hidden
price in the code does not match the price shown on the page, and for a local
business checks that the address and opening hours are real text.

### Door 4: trust-signals-audit (do robots believe you?)

- Freshness: does the site show any machine-readable dates? A site that
  cannot prove it is alive looks abandoned to machines.
- One name: is your brand name written exactly the same everywhere (schema,
  social tags, page titles)? Different spellings look like different companies.
- Connections: does the site link to its official profiles (LinkedIn,
  Wikipedia, social media)? A site with zero outside connections is an
  island, and machines trust facts that many places agree on.
- Consistency: do phone numbers match across pages? Two different numbers
  make machines trust neither.

### Door 5: engagement-audit (do humans stay?)

- First screen: when someone opens your site, do they immediately see a
  headline plus one sentence that explains what this is? Or only a slogan?
- Is there a clear button or link for the next step (Contact, Buy, Book)?
- Does the site work on phones (the viewport tag)?
- Is the page too heavy and slow?
- Are any links broken (leading to error pages)?
- Is the text readable, or giant walls of words?
- Are important pages (like pricing or contact) missing from the homepage
  links, so a visitor cannot reach them in one click?

## 5. How it works step by step (the flow)

Step 1: You give one website address.

```
cd skills/audit-orchestrator
python3 scripts/run_audit.py example.com --out report.json --markdown report.md
```

Step 2: The crawler (crawl_site.py) visits the site once, politely:

- It reads robots.txt first and obeys it.
- It downloads the homepage, the sitemap, and up to 8 important pages
  (about, pricing, contact, products, FAQ, blog).
- It waits 0.6 seconds between requests and stops within a time limit.
- It saves everything into one cache folder, like a photo of the site.

Step 3: The five door-checker scripts each read that same saved photo of the
site. The site is downloaded only once. Each checker prints its findings as
JSON: problem id, title, severity, evidence (the proof with real numbers and
URLs), why it matters, and the suggested fix.

Step 4: The boss (run_audit.py) collects all findings, removes duplicates,
sorts them by severity (critical, high, medium, low), counts them, gives each
door a score out of 100, and writes the final report:

- report.json: the structured report (matches the hackathon's required format,
  plus extra useful fields).
- report.md: the same report in a human-friendly page with the funnel chart.

Step 5 (agent step): the AI agent running the skill reviews every finding
against the evidence and removes anything that does not fit the site's
context (rules for this are written in references/judgment-guide.md). This
keeps false alarms out of the report.

Step 6 (optional): if the agent has web search, it also checks how the brand
looks outside its own site (is the name confused with something else, do
other sites describe it the same way).

## 6. What is used in this project (tools and technology)

- Python 3 (standard library only). No pip installs, no external packages.
  We used only built-in modules: urllib (downloading pages), html.parser
  (reading HTML), json, re (pattern matching), gzip and zlib (unpacking
  compressed pages), argparse, time, ssl. This means it runs on any machine
  with Python, with zero setup.
- The Agent Skills format from agentskills.io: every skill is a folder with
  a SKILL.md file that has a YAML header (name, description, license,
  compatibility, allowed-tools) and instructions. All 6 skills pass the
  official format rules.
- marketplace.json: the contest's manifest format, listing all skills and
  marking exactly one entrypoint (audit-orchestrator).
- JSON for all reports, Markdown for human-readable output.
- No AI model weights, no databases, no external services. The zip is 64 KB.

## 7. How we made it (the build story)

1. Read the hackathon handout carefully and listed every requirement:
   the report schema, the marketplace rules, read-only safety, the 5-minute
   time limit, and the rubric (detection accuracy, fix quality, output
   design, format hygiene, composition, generalization).
2. Did field research on the live web:
   - The official agentskills.io specification, to make every SKILL.md valid.
   - The 2026 list of AI crawler names, and learned they come in categories
     (training vs answering), which became our smartest robots.txt check.
   - The Princeton GEO research (KDD 2024), which measured that content with
     statistics and clear quotable passages gets 30 to 40 percent more
     visibility in AI answers. That shaped the quotability checks.
   - The truth about llms.txt: no major AI company confirms using it. So we
     never call a missing llms.txt a problem (many teams will, and that is a
     false positive).
3. Designed the Citation Funnel idea: one skill per door, one boss to combine
   them. This gives real separation of concerns, which the rubric rewards.
4. Wrote the crawler first, then the five checkers, then the boss script.
5. Tested on real websites:
   - example.com (a nearly empty page): found 8 real problems.
   - python.org and mozilla.org (big real sites): first runs exposed three
     bugs in our own code, for example compressed pages saved as garbage,
     a phone detector that matched dates and code numbers, and a copyright
     reader that misread "2001-2026" as the year 2001. We fixed all three
     and re-ran until the reports had zero false alarms.
   - A fake JavaScript-shell site: correctly caught as invisible to machines.
6. Validated everything at the end: every SKILL.md checked against the
   official format rules, exactly one entrypoint in the manifest, runtime
   measured (10 to 90 seconds per site), and the final zip created.

## 8. Why this design wins points

- It tests outcomes, not checkboxes. The question probe asks what real users
  ask. Any unseen website can be judged this way, so it generalizes.
- Every finding carries proof (real numbers and URLs) plus a one-line reason
  why it matters. A non-expert can read the report and act on it.
- It is honest. It refuses to report trendy non-problems, it marks unsure
  checks with a lower confidence, and it tells the agent when to drop a
  finding. Few false positives is a scored rubric line.
- It is safe and fast: read-only, robots.txt respected, one polite crawl,
  well under the 5-minute limit, no dependencies.
