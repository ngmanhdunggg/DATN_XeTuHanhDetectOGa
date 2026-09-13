const fs = require("fs");
const path = require("path");

const inputPath = path.join(__dirname, "..", "json", "wards.json");
const outputDir = path.join(__dirname, "..", "xml");
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}
const outputPath = path.join(outputDir, "wards.xml");

const wards = JSON.parse(fs.readFileSync(inputPath, "utf8"));

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
  '<?xml version="1.0" encoding="UTF-8"?>\n<wards>\n' +
  wards
    .map(
      (w) =>
        `  <ward>\n` +
        `    <code>${escapeXml(w.code)}</code>\n` +
        `    <slug>${escapeXml(w.slug)}</slug>\n` +
        `    <type>${escapeXml(w.type)}</type>\n` +
        `    <provinceCode>${escapeXml(w.provinceCode)}</provinceCode>\n` +
        `    <name>${escapeXml(w.name)}</name>\n` +
        `    <fullName>${escapeXml(w.fullName)}</fullName>\n` +
        "  </ward>"
    )
    .join("\n") +
  "\n</wards>\n";

fs.writeFileSync(outputPath, xml, "utf8");
console.log("Generated wards.xml");
