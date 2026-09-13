const fs = require("fs");
const path = require("path");

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

function wardToXml(ward) {
  return `    <ward>
${ward.code ? `      <code>${escapeXml(ward.code)}</code>` : ""}
${ward.name ? `      <name>${escapeXml(ward.name)}</name>` : ""}
${ward.fullName ? `      <fullName>${escapeXml(ward.fullName)}</fullName>` : ""}
${ward.slug ? `      <slug>${escapeXml(ward.slug)}</slug>` : ""}
${ward.type ? `      <type>${escapeXml(ward.type)}</type>` : ""}
    </ward>`;
}

function provinceToXml(province) {
  let xml = `  <province>
    <code>${escapeXml(province.code)}</code>
    <name>${escapeXml(province.name)}</name>
    <slug>${escapeXml(province.slug)}</slug>
    <type>${escapeXml(province.type)}</type>
    <isCentral>${province.isCentral}</isCentral>
    <fullName>${escapeXml(province.fullName)}</fullName>
`;
  if (province.wards && province.wards.length) {
    xml += `    <wards>\n${province.wards
      .map(wardToXml)
      .join("\n")}\n    </wards>\n`;
  }
  xml += `  </province>`;
  return xml;
}

function treeToXml(tree) {
  return `<provinces>
${tree.map(provinceToXml).join("\n")}
</provinces>`;
}

const treePath = path.join(__dirname, "..", "json", "tree.json");
const outputDir = path.join(__dirname, "..", "xml");
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}
const xmlPath = path.join(outputDir, "tree.xml");

const tree = JSON.parse(fs.readFileSync(treePath, "utf8"));
const xml = treeToXml(tree);

fs.writeFileSync(xmlPath, xml, "utf8");
console.log("tree.xml generated.");
