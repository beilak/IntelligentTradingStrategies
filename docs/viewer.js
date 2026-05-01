const DOCS = {
  ru: [
    ["README.md", "Оглавление"],
    ["01-product-overview.md", "Назначение и роли"],
    ["02-installation-and-launch.md", "Установка и запуск"],
    ["03-system-architecture.md", "Архитектура"],
    ["04-data-hub.md", "Data Hub"],
    ["05-strategy-lab.md", "Strategy Lab"],
    ["06-ga-lab.md", "GA Lab"],
    ["07-model-development-guide.md", "Руководство модельера"],
    ["08-testing-methodology.md", "Методики тестирования"],
    ["09-api-reference.md", "API"],
    ["10-operations-and-delivery.md", "Эксплуатация"],
    ["11-scientific-basis.md", "Научная база"],
    ["12-glossary.md", "Глоссарий"],
  ],
  en: [
    ["README.md", "Contents"],
    ["01-product-overview.md", "Purpose and Roles"],
    ["02-installation-and-launch.md", "Installation and Launch"],
    ["03-system-architecture.md", "Architecture"],
    ["04-data-hub.md", "Data Hub"],
    ["05-strategy-lab.md", "Strategy Lab"],
    ["06-ga-lab.md", "GA Lab"],
    ["07-model-development-guide.md", "Modeler Guide"],
    ["08-testing-methodology.md", "Testing Methodology"],
    ["09-api-reference.md", "API"],
    ["10-operations-and-delivery.md", "Operations"],
    ["11-scientific-basis.md", "Scientific Basis"],
    ["12-glossary.md", "Glossary"],
  ],
};

const content = document.querySelector("#content");
const nav = document.querySelector("#docs-nav");
const rawLink = document.querySelector("#raw-link");
const sidebarToggle = document.querySelector("#sidebar-toggle");
const langRu = document.querySelector("#lang-ru");
const langEn = document.querySelector("#lang-en");
const pdfLink = document.querySelector("#pdf-link");

let activeLanguage = currentLanguage();

langRu.addEventListener("click", () => setLanguage("ru"));
langEn.addEventListener("click", () => setLanguage("en"));

sidebarToggle.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-open");
});

nav.addEventListener("click", () => {
  document.body.classList.remove("sidebar-open");
});

window.addEventListener("popstate", () => {
  activeLanguage = currentLanguage();
  renderNav();
  loadCurrentDocument();
});

renderNav();
loadCurrentDocument();

function renderNav() {
  nav.innerHTML = docsForLanguage().map(
    ([file, title]) => `<a href="/docs/?lang=${activeLanguage}&file=${encodeURIComponent(file)}" data-file="${escapeAttr(file)}">${escapeHtml(title)}</a>`,
  ).join("");
  langRu.classList.toggle("active", activeLanguage === "ru");
  langEn.classList.toggle("active", activeLanguage === "en");
  pdfLink.href = `/docs/pdf/its_documentation_${activeLanguage}.pdf`;
  pdfLink.title = activeLanguage === "en" ? "Download complete documentation as PDF" : "Скачать всю документацию в PDF";
  pdfLink.setAttribute("download", `its_documentation_${activeLanguage}.pdf`);
}

async function loadCurrentDocument() {
  const file = currentFile();
  setActiveNav(file);
  rawLink.href = rawMarkdownUrl(file);
  content.innerHTML = `<p class="loading">${activeLanguage === "en" ? "Loading documentation..." : "Загрузка документации..."}</p>`;

  try {
    const response = await fetch(rawMarkdownUrl(file), {
      headers: { Accept: "text/markdown,text/plain,*/*" },
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const markdown = await response.text();
    content.innerHTML = renderMarkdown(markdown);
    document.title = `${titleFor(file)} - ITS Documentation`;
    bindDocumentLinks();
  } catch (error) {
    const message = activeLanguage === "en" ? "Failed to load file" : "Не удалось загрузить файл";
    content.innerHTML = `<p class="error">${message} ${escapeHtml(file)}.</p>`;
  }
}

function currentFile() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("file") || "README.md";
  return docFiles().has(requested) ? requested : "README.md";
}

function currentLanguage() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("lang") || localStorage.getItem("its-docs-language") || "ru";
  return requested === "en" ? "en" : "ru";
}

function setLanguage(language) {
  activeLanguage = language === "en" ? "en" : "ru";
  localStorage.setItem("its-docs-language", activeLanguage);
  const file = currentFile();
  history.pushState(null, "", `/docs/?lang=${activeLanguage}&file=${encodeURIComponent(file)}`);
  renderNav();
  loadCurrentDocument();
}

function docsForLanguage() {
  return DOCS[activeLanguage];
}

function docFiles() {
  return new Set(docsForLanguage().map(([file]) => file));
}

function rawMarkdownUrl(file) {
  return activeLanguage === "en" ? `/docs/raw/en/${file}` : `/docs/raw/${file}`;
}


function setActiveNav(file) {
  nav.querySelectorAll("a").forEach((link) => {
    link.classList.toggle("active", link.dataset.file === file);
  });
}

function titleFor(file) {
  return docsForLanguage().find(([item]) => item === file)?.[1] || file;
}

function bindDocumentLinks() {
  content.querySelectorAll("a[href]").forEach((link) => {
    const url = new URL(link.href, window.location.origin);
    if (url.origin !== window.location.origin || url.pathname !== "/docs/") {
      return;
    }
    const file = url.searchParams.get("file");
    if (!file || !docFiles().has(file)) {
      return;
    }
    link.addEventListener("click", (event) => {
      event.preventDefault();
      history.pushState(null, "", `/docs/?lang=${activeLanguage}&file=${encodeURIComponent(file)}`);
      loadCurrentDocument();
    });
  });
}

function renderMarkdown(markdown) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i += 1;
      continue;
    }

    const fence = line.match(/^```([A-Za-z0-9_-]*)?\s*$/);
    if (fence) {
      const language = fence[1] || "";
      const code = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1;
      html.push(
        `<pre><code class="language-${escapeAttr(language)}">${escapeHtml(code.join("\n"))}</code></pre>`,
      );
      continue;
    }

    if (isTableStart(lines, i)) {
      const tableLines = [lines[i], lines[i + 1]];
      i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        tableLines.push(lines[i]);
        i += 1;
      }
      html.push(renderTable(tableLines));
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2].trim();
      html.push(`<h${level} id="${escapeAttr(slugify(text))}">${inlineMarkdown(text)}</h${level}>`);
      i += 1;
      continue;
    }

    if (/^\s*[-*_]{3,}\s*$/.test(line)) {
      html.push("<hr>");
      i += 1;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quote = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, ""));
        i += 1;
      }
      html.push(`<blockquote>${renderMarkdown(quote.join("\n"))}</blockquote>`);
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*+]\s+/, ""));
        i += 1;
      }
      html.push(`<ul>${items.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i += 1;
      }
      html.push(`<ol>${items.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("")}</ol>`);
      continue;
    }

    const paragraph = [];
    while (i < lines.length && lines[i].trim() && !isBlockStart(lines, i)) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
  }

  return html.join("\n");
}

function isBlockStart(lines, index) {
  const line = lines[index];
  return (
    /^```/.test(line) ||
    /^(#{1,6})\s+/.test(line) ||
    /^\s*[-*_]{3,}\s*$/.test(line) ||
    /^\s*>\s?/.test(line) ||
    /^\s*[-*+]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    isTableStart(lines, index)
  );
}

function isTableStart(lines, index) {
  return (
    index + 1 < lines.length &&
    lines[index].includes("|") &&
    /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1])
  );
}

function renderTable(lines) {
  const headers = splitTableRow(lines[0]);
  const rows = lines.slice(2).map(splitTableRow);
  return [
    "<table>",
    "<thead><tr>",
    headers.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join(""),
    "</tr></thead>",
    "<tbody>",
    rows.map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`).join(""),
    "</tbody></table>",
  ].join("");
}

function splitTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function inlineMarkdown(text) {
  const code = [];
  let value = text.replace(/`([^`]+)`/g, (_, snippet) => {
    const token = `@@CODE_${code.length}@@`;
    code.push(`<code>${escapeHtml(snippet)}</code>`);
    return token;
  });

  value = escapeHtml(value);
  value = value.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, target) => {
    const src = resolveAssetUrl(unescapeHtml(target.trim()));
    return `<img src="${escapeAttr(src)}" alt="${escapeAttr(unescapeHtml(alt))}" loading="lazy">`;
  });
  value = value.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, target) => {
    const href = resolveLinkUrl(unescapeHtml(target.trim()));
    return `<a href="${escapeAttr(href)}">${inlineMarkdown(unescapeHtml(label))}</a>`;
  });
  value = value.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  value = value.replace(/\*([^*]+)\*/g, "<em>$1</em>");

  code.forEach((html, index) => {
    value = value.replace(`@@CODE_${index}@@`, html);
  });
  return value;
}

function resolveLinkUrl(target) {
  if (/^(https?:|mailto:|#)/i.test(target)) {
    return target;
  }
  const [path] = target.split("#");
  if (path.endsWith(".md") && docFiles().has(path)) {
    return `/docs/?lang=${activeLanguage}&file=${encodeURIComponent(path)}`;
  }
  return target;
}

function resolveAssetUrl(target) {
  if (/^(https?:|data:|\/)/i.test(target)) {
    return target;
  }
  const basePath = activeLanguage === "en" ? "/docs/en/" : "/docs/";
  return new URL(target, `${window.location.origin}${basePath}`).pathname;
}

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/"/g, "&quot;");
}

function unescapeHtml(value) {
  return String(value)
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}
