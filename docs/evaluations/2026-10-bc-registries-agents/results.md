# Results: agents with and without hrono on BC Registries

Run 2026-10-11, tree `bcreg` as built in stage 1 (`../2026-10-bc-registries/`,
536 leaves), hrono at `f7797f3`. The protocol is in [README.md](README.md),
and the generated tables are in `data/runs/results.md`.

## Summary

1. **On a large, unknown codebase, hrono does not make the agent better.**
   - **Change localization (40 real commits):** the agent found 76.8% of
     the files the commit really modified with the code alone, and 78.0%
     with hrono (+1.2 points, CI −2.2 to +4.7, p 0.45). On 29 of the 40 it
     returned the same result either way.
   - **Architecture questions (36):** fact coverage was 0.692 with the code
     alone and 0.649 with hrono (−0.043, CI −0.088 to +0.004, p 0.056).
     hrono was worse on 19 questions, better on 7 and tied on 10.
2. **hrono makes the agent stop earlier, not know more.**
   - On architecture questions it took 8 turns instead of 12 and 17% fewer
     output tokens, and it cost 10% less ($0.121 against $0.134).
   - The answers were less complete, mostly on flow questions, where
     coverage was 0.606 against 0.680.
   - On localization it read 20% more context and cost 14% more.
3. **The tree does not hold the architecture.**
   - With only hrono and no code, the agent covered 0.498 of the facts. A
     model with nothing at all covered 0.398, and the agent with the code
     covered 0.692. The knowledge base adds a third of what reading the code
     adds.
   - The `tree` agent had nothing else to use, yet it opened 0.3 briefs per
     question and ran recall 4.9 times. Agents treat hrono as a search
     engine, not a map.
4. **This is a property of the tree, not the protocol.** The top level of
   `bcreg` is organised by kind of file, not by part of the system: template
   and asset library, Postman collections, Vue front ends, fixtures, database
   migrations, and notebooks, models and tests. Its briefs open by
   describing themselves ("condensed notes", "fragments, mostly truncated").
   - A question like "how does a filing get paid and applied" crosses
     legal-api, pay-api, the payment queue and the filer. No brief tells
     that story, because clustering by embedding similarity never puts those
     files together.
   - This confirms findings E17 and E19 from stage 1, and shows they are what
     blocks hrono's value, not cosmetic issues.

## Change localization (40 items, paired)

| Metric | repo | hrono | hrono − repo [95% CI] | p |
|---|---|---|---|---|
| File recall | 0.768 | 0.780 | +0.012 [−0.022, +0.047] | 0.45 |
| Precision | 0.681 | 0.697 | +0.016 [−0.027, +0.063] | 0.61 |
| F1 | 0.708 | 0.720 | +0.012 [−0.017, +0.043] | 0.64 |
| Turns | 12 | 10 | −2 | 0.007 |
| Wall s | 20 | 26 | +6 | <0.001 |
| Context read (tokens) | 152k | 183k | +31k | <0.001 |
| API-equiv. $ | 0.099 | 0.113 | +0.014 | 0.007 |

By repository, recall without and with hrono was:

| Repository | Without hrono | With hrono |
|---|---|---|
| lear | 0.81 | 0.82 |
| sbc-auth | 0.72 | 0.79 |
| sbc-pay | 0.81 | 0.79 |
| business-filings-ui (4 items) | 0.64 | 0.61 |

Both arms do well because a change request carries domain words, such as
"restoration", "continuation" or "pre-authorized debit", that grep finds.

## Architecture questions (36)

| Arm | Fact coverage [95% CI] | Errors / answer | Turns | Recall calls | Brief reads | $ / question |
|---|---|---|---|---|---|---|
| none (no tools) | 0.398 [0.355, 0.440] | 1.36 | 1 | – | – | – |
| tree (hrono only, no code) | 0.498 [0.453, 0.541] | 0.44 | 6.6 | 4.9 | 0.3 | 0.111 |
| hrono (code + hrono) | 0.649 [0.608, 0.690] | 0.14 | 7.9 | 1.0 | 1.0 | 0.121 |
| repo (code only) | 0.692 [0.643, 0.738] | 0.11 | 12.2 | – | – | 0.134 |

By kind, coverage without and with hrono was:

| Kind | Questions | Without hrono | With hrono |
|---|---|---|---|
| flow | 14 | 0.680 | 0.606 |
| concept | 12 | 0.715 | 0.670 |
| change | 10 | 0.681 | 0.686 |

In the hrono arm, "Brief reads 1.0" is almost always
`head -60 root.md`. The agent obeyed the instruction to start from the knowledge
base, ran one recall, glanced at the root and went back to grep. Root's
children (the template library, Postman collections and so on) give it no
route toward a flow such as "filing paid → applied".

## What this means for hrono

- **Cluster by what the code does, not by what it looks like.** MiniLM
  embeddings over sections put HTML templates with HTML templates and
  migrations with migrations. For agents, the useful tree is organised by
  feature and flow (filings, payments, auth, sync) and by service. Leads to
  test:
  - embed the condensed text rather than the raw source;
  - group by directory or service before clustering;
  - weight call and import edges into the clustering.
- **Briefs must state the system, not describe the notes.** The sentence
  that should begin a brief is "legal-api accepts a filing, asks pay-api for
  an invoice, and the payment queue applies it once paid…", not "This group
  is a set of condensed notes…". The brief prompt should ask for components,
  responsibilities and the flows between them, with paths.
- **Keep test, fixture, vendored and template bulk out of the top of the
  tree.** Today they own most of root's children.
- **Recall is the part agents actually use.** Making it better at
  conceptual queries is the cheapest win (see the SWE-QA run's 15%
  abstention rate).
- **A measurement to rerun after each fix:** this harness, unchanged. Set 2
  plus the `tree` arm is the direct test of whether the tree carries the
  architecture. The target is for the `tree` arm to approach the `repo`
  arm, and for the hrono arm to beat `repo` on flow questions.

## Threats to validity

- **One sample per question per arm, and one judge.** The judge is Opus and
  the agents are Sonnet. A difference of about 4 points of coverage is at the
  edge of what 36 questions resolve.
- **The questions were written and checked by Opus exploring the code with
  grep.** That favours facts grep can reach. The questions were not taken
  from hrono, which keeps the comparison fair to the baseline but not
  necessarily to a tree.
- **The `none` arm's 0.40 is high for an unknown codebase.** The judge gives
  0.5 for vague but plausibly right statements, and BC registry domain
  conventions can be guessed. Its 1.36 errors per answer shows how much of
  it is guessing.
- **The hrono arm was told to start from hrono.** A free choice was not
  re-tested, because in the SWE-QA run agents left free used it 1 time in 48.
- **The tree is stage 1's, with known open findings (E17, E19, E20).** These
  results measure that tree, not hrono's ceiling.
