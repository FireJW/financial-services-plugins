# Case: Index To Article

Use this case when the user wants a draft, note, or article built from a live
evidence pack instead of from free-form opinion.

## Default Routing

1. Build the evidence pack first with `news-index`, `x-index`, or both.
2. Convert that into a brief or article-ready package.
3. Draft from the structured brief, not straight from raw observations.
4. If the piece is macro-first, use `macro_note_workflow.py`.
5. If the piece is article-first, use the article draft flow and keep citations
   attached to key claims.

## Writing Gate

Do not draft until the evidence pack clearly separates:

- confirmed facts
- unresolved facts
- inference only
- image evidence vs text evidence

## Image Handling

- Keep image paths and source links with the draft package.
- Prefer directly sourced screenshots or selected images from the evidence pack.
- Do not imply that a decorative image proves the thesis.

## Review Rule

When the article makes non-trivial claims:

1. run a structured review pass
2. soften or remove claims that overreach the evidence
3. preserve the strongest line of argument, but not unsupported certainty

## Feedback Loop

If the user gives editing feedback:

- extract what changed in structure, tone, and evidence handling
- update the reusable writing memory or workflow memory
- avoid treating one-off wording edits as universal rules unless the user makes
  the preference explicit

## Platform-Ready Formatting (Chinese)

When the article targets WeChat or Toutiao, the final output must be
platform-ready plain text, not raw markdown:

- **No markdown bold** (`**text**`): platform renderers handle it
  inconsistently. Use plain text for emphasis.
- **No heading markers** (`##`, `###`): titles are plain text lines.
- **No horizontal rules** (`---`): remove all separators.
- **No numbered list prefixes** (`1. 2. 3.`): state items directly.
- **No metadata blockquote** at the top (analysis time, data sources).
- **No title repetition** in the body (`# Title`): the title is filled
  separately in the platform editor.
- **Source label**: use `来源：` not `信源说明：`.
- **No toolchain exposure**: never mention "索引管线", "交叉验证",
  "本地索引" or similar internal pipeline terms.

## Voice Preferences (Chinese)

- Open with a direct statement (`就在昨天，…`), not a template hook
  (`说一件昨天发生的事`).
- Drop filler words: `就是做 Claude 的` → `做 Claude 的`.
- Use `消息` to introduce a source naturally.
- Prefer `接下来关注什么` over `接下来盯什么` (slightly more formal).
- Add `有` for spoken flow: `需要盯的三个` → `需要盯的有三个`.
- Simplify numbered labels: `坑一` → `一`.
