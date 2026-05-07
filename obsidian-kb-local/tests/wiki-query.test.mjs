import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { parseFrontmatter, validateWikiFrontmatter } from "../src/frontmatter.mjs";
import {
  buildQuerySynthesisNote,
  buildWikiQueryPrompt,
  selectRelevantWikiNotes
} from "../src/wiki-query.mjs";

test("wiki query ranks direct, graph, and monetary-liquidity expansion results", () => {
  const notes = [
    note("Direct Match", "Monetary Policy", "Money supply drives liquidity in this note.", {
      relativePath: "08-ai-kb/20-wiki/sources/Direct-Match.md",
      compiled_from: ["08-ai-kb/10-raw/books/direct.md"]
    }),
    note("Support Node", "Monetary Policy", "Money matters for this concept.\n\n## Related\n\n- [[08-ai-kb/20-wiki/sources/Direct-Match|Direct Match]]", {
      relativePath: "08-ai-kb/20-wiki/concepts/Support-Node.md",
      compiled_from: ["08-ai-kb/10-raw/books/direct.md"]
    }),
    note("Quantitative Easing", "Monetary Policy", "Central bank liquidity programs expand credit creation and reserves."),
    note("Dealer of Last Resort", "Central Bank Plumbing", "The dealer-of-last-resort framework explains Fed liquidity backstops.")
  ];

  const selected = selectRelevantWikiNotes(notes, "money supply", { limit: 4 });
  assert.equal(selected[0].note.title, "Direct Match");
  assert.ok(selected.find((entry) => entry.note.title === "Support Node").retrieval.graphScore > 0);
  assert.equal(
    selected.find((entry) => entry.note.title === "Quantitative Easing").retrieval.intentLabel,
    "monetary-liquidity"
  );
  assert.ok(
    selected
      .find((entry) => entry.note.title === "Dealer of Last Resort")
      .retrieval.expansionMatches.includes("dealer of last resort")
  );
});

test("wiki query prompt and synthesis note include selected note context", () => {
  const selectedNotes = [
    {
      score: 42,
      retrieval: {
        mode: "direct+graph",
        directScore: 30,
        graphScore: 8,
        matchedTerms: ["money", "supply"],
        signals: ["title:phrase"]
      },
      excerpt: "Money supply affects liquidity.",
      note: note("Money Supply", "Money Supply", "Money supply affects liquidity.", {
        relativePath: "08-ai-kb/20-wiki/concepts/Money-Supply.md"
      })
    }
  ];

  const prompt = buildWikiQueryPrompt("Q={{QUERY}}\nT={{TOPIC}}\nN={{NOTE_CONTEXT}}", {
    query: "What is money supply?",
    topic: "Money Supply",
    selectedNotes
  });
  assert.match(prompt, /Q=What is money supply\?/);
  assert.match(prompt, /score: 42/);
  assert.match(prompt, /retrieval: direct\+graph/);
  assert.match(prompt, /terms=money, supply/);

  const result = buildQuerySynthesisNote(
    {
      machineRoot: "08-ai-kb",
      vaultPath: path.join(process.cwd(), ".tmp-unused")
    },
    {
      query: "What is money supply?",
      topic: "Money Supply",
      answer: "## Answer\n\nMoney supply is the stock of money available in the economy.",
      selectedNotes,
      timestamp: "2026-04-05T09:00:00+08:00"
    }
  );

  const frontmatter = parseFrontmatter(result.content);
  assert.doesNotThrow(() => validateWikiFrontmatter(frontmatter));
  assert.deepEqual(frontmatter.compiled_from, ["08-ai-kb/20-wiki/concepts/Money-Supply.md"]);
  assert.match(result.path, /20-wiki\/syntheses\/Q&A-Money-Supply/i);
  assert.match(result.content, /\[\[08-ai-kb\/20-wiki\/concepts\/Money-Supply\|Money Supply\]\]/);
});

function note(title, topic, body, extra = {}) {
  return {
    relativePath: extra.relativePath || `08-ai-kb/20-wiki/concepts/${title.replace(/\s+/g, "-")}.md`,
    title,
    content: `# ${title}\n\n${body}\n`,
    frontmatter: {
      wiki_kind: "concept",
      topic,
      compiled_at: "2026-04-05T09:00:00+08:00",
      kb_date: "2026-04-05",
      compiled_from: extra.compiled_from || []
    }
  };
}
