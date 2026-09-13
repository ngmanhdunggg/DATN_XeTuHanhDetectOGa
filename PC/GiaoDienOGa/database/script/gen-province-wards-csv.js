const fs = require("fs");
const path = require("path");

const provinces = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "json", "provinces.json"), "utf8")
);
const wards = JSON.parse(
  fs.readFileSync(path.join(__dirname, "..", "json", "wards.json"), "utf8")
);

provinces.forEach((province) => {
  const fileName = `${province.code}-${province.slug}.csv`;
  const dirPath = path.join(__dirname, "..", "csv", "single");
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
  const filePath = path.join(dirPath, fileName);

  const filteredWards = wards.filter((w) => w.provinceCode === province.code);

  const header = "code,name,fullName,slug,type,provinceCode\n";
  const lines = filteredWards.map((w) =>
    [
      w.code,
      `"${w.name.replace(/"/g, '""')}"`,
      `"${w.fullName.replace(/"/g, '""')}"`,
      w.slug,
      w.type,
      w.provinceCode,
    ].join(",")
  );

  fs.writeFileSync(filePath, header + lines.join("\n"), "utf8");
  console.log("Generated", fileName);
});
