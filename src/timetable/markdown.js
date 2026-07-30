import createDOMPurify from "dompurify";
import { Marked } from "marked";

const FIXED_REDACTION_BLOCK = "████";
const ALLOWED_MARKDOWN_TAGS = [
  "p",
  "br",
  "strong",
  "em",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "ul",
  "ol",
  "li",
  "blockquote",
  "code",
  "pre",
  "a",
];
const FORBIDDEN_RAW_TAGS = [
  "script",
  "style",
  "iframe",
  "img",
  "svg",
  "math",
  "object",
  "embed",
  "form",
  "input",
  "button",
  "template",
];
const SAFE_LINK_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);
const markdown = new Marked({
  breaks: true,
  gfm: true,
});
const purifier = createDOMPurify(window);

function safeLink(value) {
  if (!value) return null;
  try {
    const url = new URL(value, window.location.href);
    return SAFE_LINK_PROTOCOLS.has(url.protocol) ? url : null;
  } catch {
    return null;
  }
}

function constrainLinks(fragment) {
  for (const anchor of fragment.querySelectorAll("a")) {
    const url = safeLink(anchor.getAttribute("href"));
    if (!url) {
      anchor.replaceWith(document.createTextNode(anchor.textContent || ""));
      continue;
    }
    anchor.setAttribute("href", url.href);
    const external = url.protocol === "mailto:" || url.origin !== window.location.origin;
    if (external) {
      anchor.setAttribute("target", "_blank");
      anchor.setAttribute("rel", "noopener noreferrer");
    } else {
      anchor.removeAttribute("target");
      anchor.removeAttribute("rel");
    }
  }
}

function preserveStructuralLineBreaks(fragment) {
  for (const lineBreak of fragment.querySelectorAll("br")) {
    lineBreak.after(document.createTextNode("\n"));
  }

  for (const node of [...fragment.childNodes]) {
    if (node.nodeType === Node.TEXT_NODE && !node.nodeValue.trim()) {
      node.remove();
    }
  }
  const blocks = [...fragment.childNodes];
  blocks.slice(1).forEach((block) => {
    block.before(document.createTextNode("\n\n"));
  });
}

function decorateFixedRedactions(fragment) {
  const walker = document.createTreeWalker(fragment, NodeFilter.SHOW_TEXT);
  const redactedTextNodes = [];
  let current = walker.nextNode();
  while (current) {
    if (current.nodeValue?.includes(FIXED_REDACTION_BLOCK)) {
      redactedTextNodes.push(current);
    }
    current = walker.nextNode();
  }

  for (const textNode of redactedTextNodes) {
    const replacement = document.createDocumentFragment();
    const parts = textNode.nodeValue.split(FIXED_REDACTION_BLOCK);
    parts.forEach((part, index) => {
      if (part) replacement.append(document.createTextNode(part));
      if (index >= parts.length - 1) return;
      const block = document.createElement("span");
      block.className = "redaction-block";
      block.setAttribute("aria-hidden", "true");
      block.textContent = FIXED_REDACTION_BLOCK;
      replacement.append(block);
    });
    textNode.replaceWith(replacement);
  }
}

function sanitizedMarkdownFragment(source, { decorateRedactions = true } = {}) {
  const rendered = markdown.parse(String(source || ""));
  const fragment = purifier.sanitize(rendered, {
    ALLOWED_TAGS: ALLOWED_MARKDOWN_TAGS,
    ALLOWED_ATTR: ["href"],
    ALLOW_DATA_ATTR: false,
    ALLOW_UNKNOWN_PROTOCOLS: false,
    FORBID_TAGS: FORBIDDEN_RAW_TAGS,
    RETURN_DOM_FRAGMENT: true,
  });
  preserveStructuralLineBreaks(fragment);
  constrainLinks(fragment);
  if (decorateRedactions) decorateFixedRedactions(fragment);
  return fragment;
}

export function markdownToPlainText(source) {
  const fragment = sanitizedMarkdownFragment(source, { decorateRedactions: false });
  return (fragment.textContent || "").replace(/\s+/g, " ").trim();
}

export function renderMarkdownInto(element, source, { compact = false } = {}) {
  const fragment = sanitizedMarkdownFragment(source);
  if (compact) {
    for (const link of fragment.querySelectorAll("a")) {
      const label = document.createElement("span");
      label.className = "markdown-link-label";
      label.textContent = link.textContent || "";
      link.replaceWith(label);
    }
  }
  element.classList.add("markdown-content");
  element.classList.toggle("markdown-content--compact", compact);
  element.replaceChildren(fragment);

  for (const link of element.querySelectorAll("a")) {
    link.addEventListener("pointerdown", (event) => event.stopPropagation());
    link.addEventListener("click", (event) => event.stopPropagation());
  }
}

export function clearMarkdownRendering(element) {
  element.classList.remove("markdown-content", "markdown-content--compact");
}
