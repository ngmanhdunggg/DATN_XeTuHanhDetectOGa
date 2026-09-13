const fs = require("fs");
const path = require("path");

const inputPath = path.join(__dirname, "..", "json", "provinces.json");
const outputDir = path.join(__dirname, "..", "xml");
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}
const outputPath = path.join(outputDir, "provinces.xml");

const provinces = JSON.parse(fs.readFileSync(inputPath, "utf8"));

function escapeXml(str) {
  return str.replace(
    /[<>&'"]/g,
    (c) =>
      ({
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
        "'": "&apos;",
        '"': "&quot;",
      }[c])
  );
}

const xml =
  '<?xml version="1.0" encoding="UTF-8"?>\n<provinces>\n' +
  provinces
    .map(
      (p) =>
        `  <province>\n` +
        `    <code>${escapeXml(p.code)}</code>\n` +
        `    <slug>${escapeXml(p.slug)}</slug>\n` +
        `    <type>${escapeXml(p.type)}</type>\n` +
        `    <isCentral>${p.isCentral}</isCentral>\n` +
        `    <name>${escapeXml(p.name)}</name>\n` +
        `    <fullName>${escapeXml(p.fullName)}</fullName>\n` +
        "  </province>"
    )
    .join("\n") +
  "\n</provinces>\n";

fs.writeFileSync(outputPath, xml, "utf8");
console.log("Generated provinces.xml");
