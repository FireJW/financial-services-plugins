/**
 * visual-style-engine.mjs
 *
 * Pure-function module: style matrix lookup, prompt segment builders,
 * and full prompt assembly for social-card cover image generation.
 * Zero side effects, zero API calls.
 */

// ── Style Matrix ───────────────────────────────────────────────────
export const STYLE_MATRIX = [
  {
    domain: "macro",
    hasScene: true,
    visualDirection: "documentary-photo",
    colorHints: ["desaturated warm", "muted", "subtle grain"],
    moodHints: ["tense", "watchful", "documentary"],
    safeZoneStrategy: "atmospheric-fade",
  },
  {
    domain: "macro",
    hasScene: false,
    visualDirection: "abstract-metaphor",
    colorHints: ["deep blue", "dark amber", "minimal"],
    moodHints: ["ominous", "contemplative", "strategic"],
    safeZoneStrategy: "dark-gradient",
  },
  {
    domain: "tech",
    hasScene: true,
    visualDirection: "product-closeup",
    colorHints: ["cool white", "clean", "high contrast"],
    moodHints: ["precise", "forward-looking", "editorial"],
    safeZoneStrategy: "soft-bokeh",
  },
  {
    domain: "tech",
    hasScene: false,
    visualDirection: "tech-abstract",
    colorHints: ["deep navy", "electric blue", "purple"],
    moodHints: ["futuristic", "cerebral", "expansive"],
    safeZoneStrategy: "dark-gradient",
  },
  {
    domain: "growth",
    hasScene: true,
    visualDirection: "lifestyle-texture",
    colorHints: ["warm golden", "soft", "natural light"],
    moodHints: ["intimate", "reflective", "unhurried"],
    safeZoneStrategy: "soft-bokeh",
  },
  {
    domain: "growth",
    hasScene: false,
    visualDirection: "minimal-metaphor",
    colorHints: ["cream", "muted earth", "paper texture"],
    moodHints: ["quiet", "thoughtful", "spacious"],
    safeZoneStrategy: "paper-texture",
  },
];

// ── Lookup ──────────────────────────────────────────────────────────
const FALLBACK_ROW = STYLE_MATRIX[1]; // macro + noScene (abstract-metaphor)

/**
 * Find the style row matching { domain, hasScene }.
 * Falls back to abstract-metaphor for unknown domains.
 */
export function lookupStyle({ domain, hasScene }) {
  return (
    STYLE_MATRIX.find((r) => r.domain === domain && r.hasScene === hasScene) ??
    FALLBACK_ROW
  );
}

// ── Negative Prompt ─────────────────────────────────────────────────
export const NEGATIVE_PROMPT = `Do NOT include any text, typography, titles, captions, labels, watermarks, or logos.
Do NOT include any UI elements, buttons, frames, or decorative borders.
Do NOT render the image as a poster, magazine cover, or advertisement layout.
No stock photo aesthetics (over-lit, over-posed, generic).
No HDR over-processing, artificial lens flare, chromatic aberration.
No oversaturated or neon colors.
No 3D rendering, CGI look, video game aesthetic.
No cartoon, illustration, or anime style.
No multiple exposure or collage composition.`;

// ── Anti-Slop Map ───────────────────────────────────────────────────
export const ANTI_SLOP = {
  "documentary-photo": "NOT dramatic, NOT cinematic, NOT heroic.",
  "abstract-metaphor": "NOT fantasy, NOT sci-fi, NOT surreal.",
  "product-closeup": "NOT advertisement, NOT product rendering, NOT catalog.",
  "tech-abstract": "NOT cyberpunk, NOT neon, NOT gaming aesthetic.",
  "lifestyle-texture": "NOT Instagram filter, NOT over-edited, NOT staged.",
  "minimal-metaphor":
    "NOT minimalist poster, NOT graphic design, NOT flat illustration.",
};

// ── Safe Zone Prompts ───────────────────────────────────────────────
export const SAFE_ZONE_PROMPTS = {
  "atmospheric-fade":
    "The bottom 30% transitions into atmospheric haze or soft out-of-focus foreground, maintaining visual continuity but low information density.",
  "dark-gradient":
    "The bottom 30% fades into deep shadow or dark gradient, creating a natural dark zone suitable for light-colored text overlay.",
  "soft-bokeh":
    "The bottom 30% falls into shallow depth-of-field bokeh, with soft diffused shapes maintaining visual interest at low density.",
  "paper-texture":
    "The bottom 30% transitions into a clean, muted surface — paper texture, linen, or soft gradient — that feels intentional rather than empty.",
};

// ── Medium Lines ────────────────────────────────────────────────────
export const MEDIUM_LINES = {
  "documentary-photo":
    "Editorial photojournalism. Vertical 3:4 frame. Natural available light. Slight film grain.",
  "abstract-metaphor":
    "Abstract editorial photograph. Vertical 3:4 frame. Moody studio or environmental light.",
  "product-closeup":
    "Product editorial photograph. Vertical 3:4 frame. Clean studio or environmental light. Shallow depth of field.",
  "tech-abstract":
    "Abstract technology photograph. Vertical 3:4 frame. Cool ambient light with subtle glow.",
  "lifestyle-texture":
    "Lifestyle editorial photograph. Vertical 3:4 frame. Warm natural light. Soft focus.",
  "minimal-metaphor":
    "Minimal still-life photograph. Vertical 3:4 frame. Soft directional light. Paper or linen texture.",
};

// ── Segment Builders ────────────────────────────────────────────────

/**
 * Segment 1 — medium & framing.
 */
export function buildMediumSegment(visualDirection) {
  return (
    MEDIUM_LINES[visualDirection] ??
    MEDIUM_LINES["abstract-metaphor"]
  );
}

/**
 * Segment 3 — safe-zone composition instruction.
 */
export function buildSafeZoneSegment(safeZoneStrategy) {
  const detail =
    SAFE_ZONE_PROMPTS[safeZoneStrategy] ??
    SAFE_ZONE_PROMPTS["dark-gradient"];
  return `Composition: Place the main subject in the upper 65-70% of the frame. ${detail} Do NOT leave the bottom blank or empty — it should have visual content, just at lower density.`;
}

/**
 * Segment 4 — color palette, mood, and anti-slop guard.
 */
export function buildMoodSegment({ colorHints, moodHints, visualDirection }) {
  const colors = colorHints.join(", ");
  const moods = moodHints.join(", ");
  const slop = ANTI_SLOP[visualDirection] ?? "";
  return `Color palette: ${colors}. Mood: ${moods}. ${slop}`;
}

// ── Full Prompt Assembly ────────────────────────────────────────────

/**
 * Assemble the complete 5-segment image-gen prompt.
 *
 * @param {object}  opts
 * @param {string}  opts.subjectSegment   - Segment 2 (the scene / subject)
 * @param {object}  opts.classification   - { domain, hasScene }
 * @returns {string} Final prompt
 */
export function assemblePrompt({ subjectSegment, classification }) {
  const style = lookupStyle(classification);

  const seg1 = buildMediumSegment(style.visualDirection);
  const seg2 = subjectSegment;
  const seg3 = buildSafeZoneSegment(style.safeZoneStrategy);
  const seg4 = buildMoodSegment(style);
  const seg5 = NEGATIVE_PROMPT;

  return `${seg1}\n\n${seg2}\n\n${seg3}\n\n${seg4}\n\n${seg5}`;
}
