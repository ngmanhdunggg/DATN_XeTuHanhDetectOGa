const fs = require("fs");
const path = require("path");

const provinces = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "json", "provinces.json"), "utf8")
);
const wards = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "json", "wards.json"), "utf8")
);

// Sắp xếp provinces theo code tăng dần (01 -> 34)
provinces.sort((a, b) => Number(a.code) - Number(b.code));

const provinceMap = {};
provinces.forEach((p) => {
  provinceMap[p.code] = { ...p, wards: [] };
});

wards.forEach((w) => {
  if (provinceMap[w.provinceCode]) {
    // Chỉ lấy các trường cần thiết cho ward
    const { code, name, fullName, slug, type } = w;
    provinceMap[w.provinceCode].wards.push({
      code,
      name,
      fullName,
      slug,
      type,
    });
  }
});

const tree = provinces.map((p) => provinceMap[p.code]);

const outputDir = path.join(__dirname, "..", "json");
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}
fs.writeFileSync(
  path.join(outputDir, "tree.json"),
  JSON.stringify(tree, null, 2),
  "utf8"
);

console.log("Generated tree.json");
