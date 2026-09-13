const fs = require("fs");
const path = require("path");

const inputPath = path.join(__dirname, "..", "json", "wards.json");
const outputDir = path.join(__dirname, "..", "csv");
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}
const outputPath = path.join(outputDir, "wards.csv");

const wards = JSON.parse(fs.readFileSync(inputPath, "utf8"));

const header = "code,name,fullName,slug,type,provinceCode\n";
const lines = wards.map((w) =>
  [
    w.code,
    `"${w.name.replace(/"/g, '""')}"`,
    `"${w.fullName.replace(/"/g, '""')}"`,
    w.slug,
    w.type,
    w.provinceCode,
  ].join(",")
);

fs.writeFileSync(outputPath, header + lines.join("\n"), "utf8");
console.log("Generated wards.csv");
